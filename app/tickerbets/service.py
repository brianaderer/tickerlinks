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
    resolved_date = _normalize_target_date(requested_date)
    as_of = normalize_as_of()
    horizon = (resolved_date - as_of.date()).days
    if horizon < 1 or horizon > 5:
        raise ValueError("target_date must be between 1 and 5 days in the future")

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
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d
