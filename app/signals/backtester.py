import logging
from collections import defaultdict

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

LOOKAHEAD_HOURS = 24
MIN_WINDOW_SIZE = 30
STEP_SIZE = 8
MOVEMENT_THRESHOLD = 0.001


def run_backtest(company_ids: list[int] | None = None) -> dict:
    if not company_ids:
        companies = Company.query.filter_by(active=True).all()
        company_ids = [c.id for c in companies]

    historical_detectors = [
        TechnicalDetector(),
        VolumeDetector(),
        FundamentalsDetector(),
    ]
    article_detectors = [
        ArticleSentimentDetector(),
        MentionVelocityDetector(),
        ComentionDetector(),
        SourceBreadthDetector(),
    ]

    # Key: (signal_name, direction) -> {correct, incorrect, total}
    signal_results = defaultdict(lambda: {"correct": 0, "incorrect": 0, "total": 0})

    processed = 0
    for cid in company_ids:
        company = Company.query.get(cid)
        if not company:
            continue

        prices = (
            PriceHistory.query.filter_by(company_id=cid)
            .order_by(PriceHistory.timestamp)
            .all()
        )
        if len(prices) < MIN_WINDOW_SIZE + LOOKAHEAD_HOURS:
            continue

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
            ]
        )
        df.set_index("timestamp", inplace=True)

        fund_data = _load_fundamentals(cid, company.symbol)
        insider_data = _load_insider_trades(cid, company.symbol)

        _backtest_company(cid, company.symbol, df, fund_data, insider_data, historical_detectors, article_detectors, signal_results)
        processed += 1

        if processed % 50 == 0:
            logger.info("Backtested %d / %d companies", processed, len(company_ids))

    accuracy_map = _compute_accuracy(signal_results)
    _persist_accuracy(accuracy_map, signal_results)

    logger.info(
        "Backtest complete: %d companies, %d signal+direction pairs scored",
        processed, len(accuracy_map),
    )
    return {
        "companies_tested": processed,
        "signal_scores": {
            f"{name}|{direction}": round(acc, 4)
            for (name, direction), acc in accuracy_map.items()
        },
    }


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


def _backtest_company(
    company_id: int,
    symbol: str,
    df: pd.DataFrame,
    fund_data: dict,
    insider_data: list,
    historical_detectors: list,
    article_detectors: list,
    signal_results: dict,
):
    total_rows = len(df)

    for end_idx in range(MIN_WINDOW_SIZE, total_rows - LOOKAHEAD_HOURS, STEP_SIZE):
        window_df = df.iloc[:end_idx].copy()
        lookahead_df = df.iloc[end_idx : end_idx + LOOKAHEAD_HOURS]

        if lookahead_df.empty:
            continue

        price_at_signal = window_df["close"].iloc[-1]
        price_after = lookahead_df["close"].iloc[-1]
        actual_change_pct = (price_after - price_at_signal) / price_at_signal

        window_time = window_df.index[-1]
        if hasattr(window_time, 'to_pydatetime'):
            window_time = window_time.to_pydatetime()

        fundamentals_state = {}
        if fund_data:
            fund_with_insiders = dict(fund_data)
            fund_with_insiders["insider_trades"] = insider_data
            fundamentals_state = {company_id: fund_with_insiders}

        state: EngineState = {
            "company_ids": [company_id],
            "price_data": {company_id: {"symbol": symbol, "df": window_df}},
            "news_data": {},
            "fundamentals_data": fundamentals_state,
            "insider_data": {},
            "signals": [],
            "predictions": [],
            "iteration": 0,
            "max_iterations": 1,
            "confidence_threshold": 0.5,
        }

        for detector in historical_detectors:
            try:
                signals = detector.detect(state)
            except Exception:
                continue
            _score_signals(signals, actual_change_pct, signal_results)

        for detector in article_detectors:
            try:
                signals = detector.detect(state, before=window_time)
            except Exception:
                continue
            _score_signals(signals, actual_change_pct, signal_results)


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


def _compute_accuracy(signal_results: dict) -> dict[tuple[str, str], float]:
    accuracy = {}
    for key, counts in signal_results.items():
        total = counts["total"]
        if total >= 5:
            accuracy[key] = counts["correct"] / total
        else:
            accuracy[key] = 0.5
    return accuracy


def _persist_accuracy(accuracy_map: dict, signal_results: dict):
    for (name, direction), accuracy in accuracy_map.items():
        signal = Signal.query.filter_by(name=name, direction=direction).first()
        if not signal:
            signal = Signal(
                name=name,
                signal_type=_infer_type(name),
                direction=direction,
                description=f"Auto-detected: {name} ({direction})",
                historical_accuracy=accuracy,
                sample_size=signal_results[(name, direction)]["total"],
                active=True,
            )
            db.session.add(signal)
        else:
            signal.historical_accuracy = accuracy
            signal.sample_size = signal_results[(name, direction)]["total"]

    db.session.commit()
    logger.info("Persisted accuracy for %d signal+direction pairs", len(accuracy_map))


def _infer_type(name: str) -> str:
    name_lower = name.lower()
    if any(k in name_lower for k in ("rsi", "macd", "bollinger")):
        return "technical"
    if any(k in name_lower for k in ("volume", "divergence", "spike")):
        return "volume"
    if any(k in name_lower for k in ("sentiment", "news")):
        return "sentiment"
    if any(k in name_lower for k in ("insider", "52-week", "near")):
        return "fundamentals"
    return "pattern"
