import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.models import Company, Fundamentals, PriceHistory, Signal, SignalMatch


HORIZONS = tuple(range(1, 11))
TRAIN_WINDOW_DAYS = 30
PRICE_HISTORY_DAYS = 400
SIGNAL_LOOKBACK_DAYS = 120
FRESHNESS_HALF_LIFE_HOURS = 24
MAX_SIGNAL_AGE_HOURS = 24 * 14
SIGNAL_BUCKETS = ("article", "volume", "technical", "fundamentals", "pattern", "sentiment", "other")


@dataclass
class DatasetBundle:
    as_of: datetime
    window_start: datetime
    window_end: datetime
    company_count: int
    total_samples: int
    frames_by_horizon: dict[int, pd.DataFrame]


def normalize_as_of(raw: datetime | None = None) -> datetime:
    ts = raw or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def build_training_frames(as_of: datetime | None = None) -> DatasetBundle:
    as_of_norm = normalize_as_of(as_of)
    window_start = as_of_norm - timedelta(days=TRAIN_WINDOW_DAYS)
    history_start = as_of_norm - timedelta(days=PRICE_HISTORY_DAYS)

    frames: dict[int, list[dict]] = {h: [] for h in HORIZONS}
    used_companies = 0

    companies = Company.query.filter_by(active=True).order_by(Company.id).all()
    for company in companies:
        hourly = _load_hourly_prices(company.id, history_start, as_of_norm)
        if hourly.empty:
            continue
        if len(hourly) < 24 * 10:
            continue

        feature_frame = _build_company_feature_frame(company, hourly, as_of_norm)
        if feature_frame.empty:
            continue

        candidate_rows = feature_frame.loc[feature_frame.index >= window_start].copy()
        if candidate_rows.empty:
            continue

        per_horizon = _rows_with_targets(candidate_rows, hourly["close"], company)
        had_rows = False
        for horizon, rows in per_horizon.items():
            if rows:
                frames[horizon].extend(rows)
                had_rows = True
        if had_rows:
            used_companies += 1

    by_horizon_df = {
        h: pd.DataFrame(rows).sort_values("as_of") if rows else pd.DataFrame()
        for h, rows in frames.items()
    }
    total_samples = int(sum(len(df) for df in by_horizon_df.values()))
    return DatasetBundle(
        as_of=as_of_norm,
        window_start=window_start,
        window_end=as_of_norm,
        company_count=used_companies,
        total_samples=total_samples,
        frames_by_horizon=by_horizon_df,
    )


def build_latest_feature_row(company: Company, as_of: datetime | None = None) -> dict:
    as_of_norm = normalize_as_of(as_of)
    history_start = as_of_norm - timedelta(days=PRICE_HISTORY_DAYS)
    hourly = _load_hourly_prices(company.id, history_start, as_of_norm)
    if hourly.empty:
        raise ValueError(f"No price history available for {company.symbol}")
    feature_frame = _build_company_feature_frame(company, hourly, as_of_norm)
    if feature_frame.empty:
        raise ValueError(f"No feature rows available for {company.symbol}")

    latest_ts = feature_frame.index.max()
    row = feature_frame.loc[latest_ts].to_dict()
    row["as_of"] = latest_ts.isoformat()
    row["company_id"] = company.id
    row["symbol"] = company.symbol
    row["industry"] = company.industry or "Unknown"
    return _clean_row(row)


def _load_hourly_prices(company_id: int, start: datetime, end: datetime) -> pd.DataFrame:
    prices = (
        PriceHistory.query.filter(
            PriceHistory.company_id == company_id,
            PriceHistory.timestamp >= start,
            PriceHistory.timestamp <= end,
        )
        .order_by(PriceHistory.timestamp.asc())
        .all()
    )
    if not prices:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "timestamp": p.timestamp,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume or 0,
            }
            for p in prices
            if p.close is not None
        ]
    )
    if df.empty:
        return pd.DataFrame()

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").set_index("timestamp")
    hourly = (
        df.resample("1h")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["close"])
    )
    if hourly.empty:
        return pd.DataFrame()
    hourly["volume"] = hourly["volume"].fillna(0.0)
    return hourly


def _build_company_feature_frame(company: Company, hourly: pd.DataFrame, as_of: datetime) -> pd.DataFrame:
    feat = pd.DataFrame(index=hourly.index)
    close = hourly["close"].astype(float)
    volume = hourly["volume"].astype(float)

    feat["current_close"] = close
    feat["ret_1h"] = close.pct_change(1)
    feat["ret_6h"] = close.pct_change(6)
    feat["ret_24h"] = close.pct_change(24)
    feat["ret_72h"] = close.pct_change(72)

    feat["sma_6h"] = close.rolling(6, min_periods=1).mean()
    feat["sma_24h"] = close.rolling(24, min_periods=1).mean()
    feat["sma_72h"] = close.rolling(72, min_periods=1).mean()
    feat["volatility_24h"] = feat["ret_1h"].rolling(24, min_periods=2).std()

    vol_mean_24 = volume.rolling(24, min_periods=1).mean().replace(0.0, pd.NA)
    feat["volume_ratio_24h"] = (volume / vol_mean_24).fillna(1.0)

    high_90d = hourly["high"].rolling(24 * 90, min_periods=1).max()
    low_90d = hourly["low"].rolling(24 * 90, min_periods=1).min()
    high_365d = hourly["high"].rolling(24 * 365, min_periods=1).max()
    low_365d = hourly["low"].rolling(24 * 365, min_periods=1).min()

    feat["dist_3m_high"] = (close / high_90d) - 1.0
    feat["dist_3m_low"] = (close / low_90d) - 1.0

    f52_high, f52_low = _fundamentals_52w_series(company.id, feat.index)
    f52_high = f52_high.fillna(high_365d)
    f52_low = f52_low.fillna(low_365d)
    feat["dist_52w_high"] = (close / f52_high) - 1.0
    feat["dist_52w_low"] = (close / f52_low) - 1.0

    sig_feats = _signal_feature_frame(company.id, feat.index, as_of)
    feat = pd.concat([feat, sig_feats], axis=1)

    feat["hour_of_day"] = feat.index.hour
    feat["day_of_week"] = feat.index.dayofweek
    feat["industry"] = company.industry or "Unknown"

    feat = feat.replace([pd.NA, pd.NaT], float("nan")).fillna(0.0)
    return feat


def _fundamentals_52w_series(company_id: int, index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    rows = (
        Fundamentals.query.filter(
            Fundamentals.company_id == company_id,
            Fundamentals.snapshot_at <= index.max().to_pydatetime(),
        )
        .order_by(Fundamentals.snapshot_at.asc())
        .all()
    )
    if not rows:
        empty = pd.Series(index=index, dtype=float)
        return empty, empty

    fund_df = pd.DataFrame(
        [
            {
                "snapshot_at": f.snapshot_at,
                "fifty_two_week_high": f.fifty_two_week_high,
                "fifty_two_week_low": f.fifty_two_week_low,
            }
            for f in rows
        ]
    )
    fund_df["snapshot_at"] = pd.to_datetime(fund_df["snapshot_at"], utc=True)
    base = pd.DataFrame({"timestamp": index}).sort_values("timestamp")
    merged = pd.merge_asof(
        base,
        fund_df.sort_values("snapshot_at"),
        left_on="timestamp",
        right_on="snapshot_at",
        direction="backward",
    ).set_index("timestamp")
    return merged["fifty_two_week_high"], merged["fifty_two_week_low"]


def _signal_feature_frame(company_id: int, index: pd.DatetimeIndex, as_of: datetime) -> pd.DataFrame:
    start = as_of - timedelta(days=SIGNAL_LOOKBACK_DAYS)
    rows = (
        SignalMatch.query.join(Signal, Signal.id == SignalMatch.signal_id)
        .filter(
            SignalMatch.company_id == company_id,
            SignalMatch.source_at >= start,
            SignalMatch.source_at <= as_of,
        )
        .with_entities(
            SignalMatch.source_at,
            SignalMatch.direction,
            SignalMatch.confidence,
            Signal.signal_type,
        )
        .order_by(SignalMatch.source_at.asc())
        .all()
    )

    columns = ["sig_bull_total", "sig_bear_total"]
    for bucket in SIGNAL_BUCKETS:
        columns.append(f"sig_bull_{bucket}")
        columns.append(f"sig_bear_{bucket}")

    if not rows:
        return pd.DataFrame(0.0, index=index, columns=columns)

    records = [
        {
            "source_at": pd.Timestamp(source_at).tz_convert("UTC") if pd.Timestamp(source_at).tzinfo else pd.Timestamp(source_at, tz="UTC"),
            "direction": direction,
            "confidence": float(confidence),
            "signal_type": signal_type or "other",
        }
        for source_at, direction, confidence, signal_type in rows
        if source_at is not None
    ]
    records.sort(key=lambda r: r["source_at"])

    pointer = 0
    active: list[dict] = []
    out = []
    for ts in index:
        ts_utc = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
        while pointer < len(records) and records[pointer]["source_at"] <= ts_utc:
            active.append(records[pointer])
            pointer += 1

        row = {col: 0.0 for col in columns}
        next_active: list[dict] = []
        for ev in active:
            age_hours = (ts_utc - ev["source_at"]).total_seconds() / 3600.0
            if age_hours < 0:
                continue
            if age_hours > MAX_SIGNAL_AGE_HOURS:
                continue

            decay = math.exp(-0.693 * age_hours / FRESHNESS_HALF_LIFE_HOURS)
            score = ev["confidence"] * decay
            direction = str(ev["direction"] or "").lower()
            bucket = _signal_bucket(ev["signal_type"])

            if direction == "bullish":
                row["sig_bull_total"] += score
                row[f"sig_bull_{bucket}"] += score
            elif direction == "bearish":
                row["sig_bear_total"] += score
                row[f"sig_bear_{bucket}"] += score
            next_active.append(ev)
        active = next_active
        out.append(row)

    return pd.DataFrame(out, index=index)


def _signal_bucket(raw_type: str) -> str:
    t = (raw_type or "").lower()
    if t in SIGNAL_BUCKETS:
        return t
    return "other"


def _rows_with_targets(
    features: pd.DataFrame,
    close_series: pd.Series,
    company: Company,
) -> dict[int, list[dict]]:
    by_horizon: dict[int, list[dict]] = {h: [] for h in HORIZONS}
    close_series = close_series.sort_index()
    idx = close_series.index

    for ts, row in features.iterrows():
        base = row.to_dict()
        base["as_of"] = ts.isoformat()
        base["company_id"] = company.id
        base["symbol"] = company.symbol
        base["industry"] = company.industry or "Unknown"

        for horizon in HORIZONS:
            target_ts = ts + timedelta(days=horizon)
            pos = idx.searchsorted(target_ts)
            if pos >= len(idx):
                continue
            target_close = float(close_series.iloc[pos])
            row_with_target = dict(base)
            row_with_target["target_close"] = target_close
            by_horizon[horizon].append(_clean_row(row_with_target))

    return by_horizon


def _clean_row(row: dict) -> dict:
    cleaned = {}
    for key, value in row.items():
        if isinstance(value, float) and (pd.isna(value) or math.isinf(value)):
            cleaned[key] = 0.0
        else:
            cleaned[key] = value
    return cleaned
