from datetime import datetime, timedelta, timezone

from app.signals.detectors.fundamentals_detector import FundamentalsDetector


def test_insider_cluster_sell_ignores_future_dated_trades():
    det = FundamentalsDetector()
    today = datetime.now(timezone.utc).date()
    future = today + timedelta(days=14)

    trades = [
        {"transaction_type": "Sale", "shares": 1000, "date": future, "filer_name": "A"},
        {"transaction_type": "Sale", "shares": 900, "date": future, "filer_name": "B"},
        {"transaction_type": "Sale", "shares": 800, "date": future, "filer_name": "C"},
    ]

    signals = det._check_insider_cluster(company_id=1, symbol="TMUS", trades=trades)
    assert not any(s["signal_name"] == "Insider Cluster Sell" for s in signals)


def test_insider_cluster_sell_uses_recent_non_future_trades_only():
    det = FundamentalsDetector()
    today = datetime.now(timezone.utc).date()
    recent = today - timedelta(days=3)
    future = today + timedelta(days=14)

    trades = [
        {"transaction_type": "Sale", "shares": 1000, "date": recent, "filer_name": "A"},
        {"transaction_type": "Sale", "shares": 900, "date": recent, "filer_name": "B"},
        {"transaction_type": "Sale", "shares": 800, "date": recent, "filer_name": "C"},
        {"transaction_type": "Sale", "shares": 777, "date": future, "filer_name": "D"},
    ]

    signals = det._check_insider_cluster(company_id=1, symbol="TMUS", trades=trades)
    sell_signals = [s for s in signals if s["signal_name"] == "Insider Cluster Sell"]
    assert len(sell_signals) == 1
    assert sell_signals[0]["context"]["sell_count"] == 3
