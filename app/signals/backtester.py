import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.extensions import db
from app.models import Company, PriceHistory, Fundamentals, InsiderTrade, Signal
from app.signals.detectors.technical import TechnicalDetector
from app.signals.detectors.volume import VolumeDetector
from app.signals.detectors.fundamentals_detector import FundamentalsDetector
from app.signals.detectors.article_sentiment import ArticleSentimentDetector
from app.signals.detectors.mention_velocity import MentionVelocityDetector
from app.signals.detectors.comention import ComentionDetector
from app.signals.detectors.source_breadth import SourceBreadthDetector
from app.signals.state import EngineState

logger = logging.getLogger(__name__)

MOVEMENT_THRESHOLD = 0.001

MORNING_START_UTC = 8   # 4am ET
MORNING_END_UTC = 16    # 12pm ET
AFTERNOON_START_UTC = 16  # 12pm ET
AFTERNOON_END_UTC = 24    # 8pm ET (midnight UTC next day)

HISTORICAL_DETECTORS = [
    TechnicalDetector,
    VolumeDetector,
    FundamentalsDetector,
]
ARTICLE_DETECTORS = [
    ArticleSentimentDetector,
    MentionVelocityDetector,
    ComentionDetector,
    SourceBreadthDetector,
]


def get_due_windows() -> list[dict]:
    now = datetime.now(timezone.utc)

    windows = []
    for day_offset in range(30, -1, -1):
        day = (now - timedelta(days=day_offset)).date()

        morning_start = datetime(day.year, day.month, day.day, MORNING_START_UTC, tzinfo=timezone.utc)
        morning_end = datetime(day.year, day.month, day.day, MORNING_END_UTC, tzinfo=timezone.utc)

        afternoon_start = morning_end
        afternoon_end_day = day + timedelta(days=1) if AFTERNOON_END_UTC == 24 else day
        afternoon_end_hour = 0 if AFTERNOON_END_UTC == 24 else AFTERNOON_END_UTC
        afternoon_end = datetime(afternoon_end_day.year, afternoon_end_day.month, afternoon_end_day.day, afternoon_end_hour, tzinfo=timezone.utc)

        if morning_end <= now:
            windows.append({"start": morning_start, "end": morning_end, "label": f"{day}_morning"})
        if afternoon_end <= now:
            windows.append({"start": afternoon_start, "end": afternoon_end, "label": f"{day}_afternoon"})

    already_computed = _get_computed_labels()
    due = [w for w in windows if w["label"] not in already_computed]

    due.sort(key=lambda w: w["start"])
    return due


def _get_computed_labels() -> set[str]:
    labels = set()
    signals = Signal.query.filter_by(active=True).all()
    for sig in signals:
        for snap in (sig.accuracy_snapshots or []):
            label = snap.get("label", "")
            if label:
                labels.add(label)
    return labels


def run_window_backtest(window: dict) -> dict:
    window_start = window["start"]
    window_end = window["end"]
    label = window["label"]

    logger.info("Running backtest for window %s (%s to %s)", label, window_start, window_end)

    companies = Company.query.filter_by(active=True).all()

    hist_detectors = [cls() for cls in HISTORICAL_DETECTORS]
    art_detectors = [cls() for cls in ARTICLE_DETECTORS]

    signal_results = defaultdict(lambda: {"correct": 0, "incorrect": 0, "total": 0})
    processed = 0

    for company in companies:
        prices = (
            PriceHistory.query.filter(
                PriceHistory.company_id == company.id,
                PriceHistory.timestamp <= window_end,
            )
            .order_by(PriceHistory.timestamp)
            .all()
        )
        if len(prices) < 30:
            continue

        df = pd.DataFrame([
            {
                "timestamp": p.timestamp,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume or 0,
            }
            for p in prices
        ])
        df.set_index("timestamp", inplace=True)

        window_prices = df.loc[
            (df.index >= window_start) & (df.index <= window_end)
        ]
        pre_window = df.loc[df.index < window_start]

        if len(pre_window) < 30 or len(window_prices) < 2:
            continue

        price_at_signal = pre_window["close"].iloc[-1]
        price_after = window_prices["close"].iloc[-1]
        actual_change_pct = (price_after - price_at_signal) / price_at_signal

        fund_data = _load_fundamentals(company.id, company.symbol)
        insider_data = _load_insider_trades(company.id, company.symbol)

        fundamentals_state = {}
        if fund_data:
            fund_with_insiders = dict(fund_data)
            fund_with_insiders["insider_trades"] = insider_data
            fundamentals_state = {company.id: fund_with_insiders}

        state: EngineState = {
            "company_ids": [company.id],
            "price_data": {company.id: {"symbol": company.symbol, "df": pre_window}},
            "news_data": {},
            "fundamentals_data": fundamentals_state,
            "insider_data": {},
            "signals": [],
            "predictions": [],
            "iteration": 0,
            "max_iterations": 1,
            "confidence_threshold": 0.5,
        }

        for detector in hist_detectors:
            try:
                signals = detector.detect(state)
            except Exception:
                continue
            _score_signals(signals, actual_change_pct, signal_results)

        for detector in art_detectors:
            try:
                signals = detector.detect(state, before=window_start)
            except Exception:
                continue
            _score_signals(signals, actual_change_pct, signal_results)

        processed += 1

    _persist_snapshot(signal_results, window_start, window_end, label)

    logger.info("Window %s: tested %d companies, %d signal pairs", label, processed, len(signal_results))
    return {
        "label": label,
        "companies_tested": processed,
        "signal_pairs": len(signal_results),
    }


def _score_signals(signals: list, actual_change_pct: float, signal_results: dict):
    for sig in signals:
        name = sig["signal_name"]
        direction = sig["direction"]
        key = (name, direction)
        signal_results[key]["total"] += 1

        if direction == "bullish" and actual_change_pct > MOVEMENT_THRESHOLD:
            signal_results[key]["correct"] += 1
        elif direction == "bearish" and actual_change_pct < -MOVEMENT_THRESHOLD:
            signal_results[key]["correct"] += 1
        else:
            signal_results[key]["incorrect"] += 1


def _persist_snapshot(signal_results: dict, window_start: datetime, window_end: datetime, label: str):
    for (name, direction), counts in signal_results.items():
        total = counts["total"]
        accuracy = counts["correct"] / total if total > 0 else 0.5

        signal = Signal.query.filter_by(name=name, direction=direction).first()
        if not signal:
            signal = Signal(
                name=name,
                signal_type=_infer_type(name),
                direction=direction,
                description=f"Auto-detected: {name} ({direction})",
                active=True,
                accuracy_snapshots=[],
            )
            db.session.add(signal)
            db.session.flush()

        snapshot = {
            "label": label,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "correct": counts["correct"],
            "incorrect": counts["incorrect"],
            "total": total,
            "accuracy": round(accuracy, 4),
        }
        signal.push_snapshot(snapshot)

    db.session.commit()


def _load_fundamentals(company_id: int, symbol: str) -> dict:
    latest = (
        Fundamentals.query.filter_by(company_id=company_id)
        .order_by(Fundamentals.snapshot_at.desc())
        .first()
    )
    if not latest:
        return {}
    return {
        "symbol": symbol,
        "latest": {
            "current_price": latest.current_price,
            "fifty_two_week_high": latest.fifty_two_week_high,
            "fifty_two_week_low": latest.fifty_two_week_low,
            "pe_trailing": latest.pe_trailing,
            "beta": latest.beta,
        },
        "insider_trades": [],
    }


def _load_insider_trades(company_id: int, symbol: str) -> list[dict]:
    trades = (
        InsiderTrade.query.filter_by(company_id=company_id)
        .order_by(InsiderTrade.transaction_date.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "filer_name": t.filer_name,
            "transaction_type": t.transaction_type,
            "shares": t.shares,
            "date": t.transaction_date,
        }
        for t in trades
    ]


def _infer_type(name: str) -> str:
    name_lower = name.lower()
    if any(k in name_lower for k in ("rsi", "macd", "bollinger")):
        return "technical"
    if any(k in name_lower for k in ("volume", "divergence", "spike")):
        return "volume"
    if any(k in name_lower for k in ("sentiment", "news", "article")):
        return "article"
    if any(k in name_lower for k in ("mention", "co-mention", "source")):
        return "article"
    if any(k in name_lower for k in ("insider", "52-week", "near")):
        return "fundamentals"
    return "pattern"
