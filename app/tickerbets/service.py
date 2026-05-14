import gzip
import json
import tempfile
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from uuid import uuid4

from xgboost import XGBRegressor

from app.extensions import db
from app.models import Company, TickerBetModelRun
from app.storage.s3 import download_bytes, s3_uri, upload_bytes
from app.tickerbets.features import (
    HORIZONS,
    build_latest_feature_row,
    build_training_frames,
    normalize_as_of,
)
from app.tickerbets.trainer import encode_inference_row, train_horizon_models

MIN_HORIZON_DAYS = min(HORIZONS)
MAX_HORIZON_DAYS = max(HORIZONS)


def train_and_store_models(run_id: str | None = None, as_of: datetime | None = None) -> TickerBetModelRun:
    run_id = run_id or uuid4().hex
    as_of_norm = normalize_as_of(as_of)
    run = TickerBetModelRun(
        run_id=run_id,
        status="running",
        started_at=datetime.now(timezone.utc),
        model_family="xgboost",
    )
    db.session.add(run)
    db.session.commit()

    try:
        bundle = build_training_frames(as_of=as_of_norm)
        trained = train_horizon_models(bundle.frames_by_horizon)

        prefix = f"tickerbets/runs/{run_id}"
        dataset_keys: dict[str, str] = {}
        model_keys: dict[str, str] = {}
        feature_columns: dict[str, list[str]] = {}
        metrics: dict[str, dict] = {}
        train_total = 0
        test_total = 0
        sample_total = 0

        for horizon in HORIZONS:
            frame = bundle.frames_by_horizon.get(horizon)
            trained_h = trained.get(horizon)
            if frame is None or frame.empty or trained_h is None:
                continue

            dataset_key = f"{prefix}/dataset_h{horizon}.csv.gz"
            payload = gzip.compress(frame.to_csv(index=False).encode("utf-8"))
            upload_bytes(dataset_key, payload, content_type="application/gzip")
            dataset_keys[str(horizon)] = dataset_key

            model_key = f"{prefix}/model_h{horizon}.json"
            upload_bytes(model_key, _serialize_model(trained_h.model), content_type="application/json")
            model_keys[str(horizon)] = model_key

            feature_columns[str(horizon)] = trained_h.encoded_columns
            metrics[str(horizon)] = trained_h.metrics
            train_total += trained_h.train_count
            test_total += trained_h.test_count
            sample_total += trained_h.sample_count

        if not model_keys:
            raise ValueError("No trainable horizon models were produced")

        datasets_manifest_key = f"{prefix}/datasets_manifest.json"
        upload_bytes(
            datasets_manifest_key,
            json.dumps(dataset_keys, indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

        metadata = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "as_of": as_of_norm.isoformat(),
            "window_start": bundle.window_start.isoformat(),
            "window_end": bundle.window_end.isoformat(),
            "horizons": sorted([int(h) for h in model_keys.keys()]),
            "dataset_keys": dataset_keys,
            "model_keys": model_keys,
            "feature_columns": feature_columns,
            "metrics": metrics,
            "company_count": bundle.company_count,
            "sample_count": sample_total,
            "train_count": train_total,
            "test_count": test_total,
        }
        metadata_key = f"{prefix}/metadata.json"
        upload_bytes(
            metadata_key,
            json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

        run.status = "succeeded"
        run.completed_at = datetime.now(timezone.utc)
        run.training_window_start = bundle.window_start
        run.training_window_end = bundle.window_end
        run.company_count = bundle.company_count
        run.sample_count = sample_total
        run.train_count = train_total
        run.test_count = test_total
        run.feature_columns = feature_columns
        run.metrics = metrics
        run.model_keys = model_keys
        run.dataset_key = datasets_manifest_key
        run.metadata_key = metadata_key
        run.artifact_prefix = s3_uri(prefix)
        run.error = None
        db.session.commit()
    except Exception as exc:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error = str(exc)
        db.session.commit()
        raise

    return run


def latest_successful_run() -> TickerBetModelRun | None:
    return (
        TickerBetModelRun.query.filter_by(status="succeeded")
        .order_by(TickerBetModelRun.completed_at.desc())
        .first()
    )


def generate_bet_prediction(symbol: str, target_date: str | date | datetime, run_id: str | None = None) -> dict:
    company = Company.query.filter_by(symbol=symbol.upper()).first()
    if not company:
        raise ValueError(f"Unknown symbol: {symbol}")

    run = (
        TickerBetModelRun.query.filter_by(run_id=run_id).first()
        if run_id
        else latest_successful_run()
    )
    if not run or run.status != "succeeded":
        raise ValueError("No successful tickerbet model run available")

    requested_date = _parse_target_date(target_date)
    as_of = normalize_as_of()
    horizon, resolved_date = _resolve_horizon_for_target_date(requested_date, as_of.date())

    model_key = (run.model_keys or {}).get(str(horizon))
    encoded_cols = (run.feature_columns or {}).get(str(horizon))
    if not model_key or not encoded_cols:
        raise ValueError(f"No model available for {horizon}-day horizon in run {run.run_id}")

    feature_row = build_latest_feature_row(company, as_of=as_of)
    current_close = float(feature_row.get("current_close", 0.0))
    X = encode_inference_row(feature_row, encoded_cols)
    model = _load_model(run.run_id, horizon, model_key)
    predicted_price = float(model.predict(X)[0])

    delta_abs = predicted_price - current_close
    delta_pct = (delta_abs / current_close) if current_close else 0.0

    return {
        "symbol": company.symbol,
        "requested_target_date": requested_date.isoformat(),
        "resolved_target_date": resolved_date.isoformat(),
        "horizon_days": horizon,
        "as_of": as_of.isoformat(),
        "current_price": round(current_close, 6),
        "predicted_price": round(predicted_price, 6),
        "predicted_delta": round(delta_abs, 6),
        "predicted_delta_pct": round(delta_pct, 6),
        "run_id": run.run_id,
        "metrics": (run.metrics or {}).get(str(horizon), {}),
    }


def _serialize_model(model: XGBRegressor) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".json") as fh:
        model.save_model(fh.name)
        fh.seek(0)
        return fh.read()


@lru_cache(maxsize=32)
def _load_model(run_id: str, horizon: int, model_key: str) -> XGBRegressor:
    payload = download_bytes(model_key)
    if not payload:
        raise ValueError(f"Model artifact missing for run={run_id} horizon={horizon}")

    with tempfile.NamedTemporaryFile(suffix=".json") as fh:
        fh.write(payload)
        fh.flush()
        model = XGBRegressor()
        model.load_model(fh.name)
    return model


def _parse_target_date(raw: str | date | datetime) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw or "").strip()
    if not text:
        raise ValueError("target_date is required")
    if "T" in text:
        text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text).date()
    return date.fromisoformat(text)


def _normalize_target_date(raw: date) -> date:
    d = raw
    while not _is_trading_day(d):
        d += timedelta(days=1)
    return d


def _resolve_horizon_for_target_date(requested_date: date, as_of_date: date) -> tuple[int, date]:
    resolved_date = _normalize_target_date(requested_date)
    valid_dates = available_target_dates(
        as_of=as_of_date,
        min_days_ahead=MIN_HORIZON_DAYS,
        max_days_ahead=MAX_HORIZON_DAYS,
    )
    if resolved_date not in valid_dates:
        raise ValueError(
            f"target_date must be between {MIN_HORIZON_DAYS} and {MAX_HORIZON_DAYS} trading days in the future"
        )
    horizon = valid_dates.index(resolved_date) + MIN_HORIZON_DAYS
    return horizon, resolved_date


def available_target_dates(
    as_of: date | None = None,
    min_days_ahead: int = MIN_HORIZON_DAYS,
    max_days_ahead: int = MAX_HORIZON_DAYS,
) -> list[date]:
    as_of_date = as_of or normalize_as_of().date()
    min_days = max(MIN_HORIZON_DAYS, int(min_days_ahead))
    max_days = min(MAX_HORIZON_DAYS, int(max_days_ahead))
    if max_days < min_days:
        return []

    trading_days: list[date] = []
    cursor = as_of_date
    while len(trading_days) < max_days:
        cursor += timedelta(days=1)
        if _is_trading_day(cursor):
            trading_days.append(cursor)
    return trading_days[min_days - 1:max_days]


def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and not _is_market_holiday(d)


def _is_market_holiday(d: date) -> bool:
    return (
        d in _nyse_holidays(d.year - 1)
        or d in _nyse_holidays(d.year)
        or d in _nyse_holidays(d.year + 1)
    )


@lru_cache(maxsize=16)
def _nyse_holidays(year: int) -> set[date]:
    holidays = {
        _observed_holiday(date(year, 1, 1)),  # New Year's Day
        _nth_weekday_of_month(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday_of_month(year, 2, 0, 3),  # Washington's Birthday
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday_of_month(year, 5, 0),  # Memorial Day
        _observed_holiday(date(year, 7, 4)),  # Independence Day
        _nth_weekday_of_month(year, 9, 0, 1),  # Labor Day
        _nth_weekday_of_month(year, 11, 3, 4),  # Thanksgiving
        _observed_holiday(date(year, 12, 25)),  # Christmas
    }

    if year >= 2022:
        holidays.add(_observed_holiday(date(year, 6, 19)))  # Juneteenth

    return holidays


def _observed_holiday(d: date) -> date:
    if d.weekday() == 5:  # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def _nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + (nth - 1) * 7)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    delta = (last.weekday() - weekday) % 7
    return last - timedelta(days=delta)


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)
