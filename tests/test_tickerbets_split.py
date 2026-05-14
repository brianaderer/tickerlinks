from datetime import datetime, timedelta, timezone

import pandas as pd

from app.tickerbets.trainer import chronological_split, encode_inference_row


def _row(ts: datetime, close: float):
    return {
        "as_of": ts.isoformat(),
        "company_id": 1,
        "symbol": "AAPL",
        "industry": "Software",
        "current_close": close,
        "ret_1h": 0.001,
        "ret_6h": 0.002,
        "ret_24h": 0.003,
        "ret_72h": 0.004,
        "sma_6h": close,
        "sma_24h": close,
        "sma_72h": close,
        "volatility_24h": 0.01,
        "volume_ratio_24h": 1.0,
        "dist_3m_high": -0.02,
        "dist_3m_low": 0.12,
        "dist_52w_high": -0.03,
        "dist_52w_low": 0.2,
        "sig_bull_total": 0.7,
        "sig_bear_total": 0.2,
        "hour_of_day": ts.hour,
        "day_of_week": ts.weekday(),
        "target_close": close * 1.01,
    }


def test_chronological_split_orders_by_time():
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    rows = [_row(base + timedelta(hours=i), close=100 + i) for i in range(20)]
    frame = pd.DataFrame(list(reversed(rows)))

    train, test = chronological_split(frame, ratio=0.8)

    assert len(train) == 16
    assert len(test) == 4
    assert pd.to_datetime(train.iloc[0]["as_of"], utc=True) < pd.to_datetime(train.iloc[-1]["as_of"], utc=True)
    assert pd.to_datetime(train.iloc[-1]["as_of"], utc=True) < pd.to_datetime(test.iloc[0]["as_of"], utc=True)


def test_encode_inference_row_reindexes_expected_columns():
    row = _row(datetime(2026, 5, 1, tzinfo=timezone.utc), close=101)
    encoded = encode_inference_row(row, ["current_close", "ret_1h", "industry_Software", "industry_nan"])

    assert list(encoded.columns) == ["current_close", "ret_1h", "industry_Software", "industry_nan"]
    assert encoded.iloc[0]["industry_Software"] == 1.0
