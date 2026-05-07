import hashlib
import logging
from collections import defaultdict

from app.models import Signal
from app.signals.state import EngineState

logger = logging.getLogger(__name__)

DEFAULT_WEIGHT = 0.5
MIN_SIGNAL_TYPES = 2
MAX_PREDICTIONS = 10
RECENCY_TYPES = {"article_sentiment", "mention_velocity", "comention", "source_breadth"}


def aggregate_node(state: EngineState) -> EngineState:
    signals = state.get("signals", [])
    if not signals:
        state["predictions"] = []
        return state

    weight_map = _load_weight_map()

    by_company = defaultdict(list)
    for sig in signals:
        by_company[sig["company_id"]].append(sig)

    predictions = []
    for company_id, company_signals in by_company.items():
        symbol = company_signals[0].get("symbol", "?")

        signal_types = set(s["signal_type"] for s in company_signals)
        if len(signal_types) < MIN_SIGNAL_TYPES:
            continue

        bullish = [s for s in company_signals if s["direction"] == "bullish"]
        bearish = [s for s in company_signals if s["direction"] == "bearish"]

        bullish_score = sum(
            s["confidence"] * weight_map.get((s["signal_name"], s["direction"]), DEFAULT_WEIGHT)
            for s in bullish
        )
        bearish_score = sum(
            s["confidence"] * weight_map.get((s["signal_name"], s["direction"]), DEFAULT_WEIGHT)
            for s in bearish
        )
        total_score = bullish_score + bearish_score
        if total_score == 0:
            continue

        if bullish_score > bearish_score:
            direction = "bullish"
            confidence = bullish_score / total_score
        elif bearish_score > bullish_score:
            direction = "bearish"
            confidence = bearish_score / total_score
        else:
            continue

        confidence = round(min(confidence, 0.95), 3)

        signal_score = _compute_signal_score(
            company_signals, signal_types, total_score, bullish_score, bearish_score
        )
        fingerprint = _signal_fingerprint(company_signals)

        predictions.append({
            "company_id": company_id,
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "signal_score": signal_score,
            "fingerprint": fingerprint,
            "bullish_signals": len(bullish),
            "bearish_signals": len(bearish),
            "signal_names": [s["signal_name"] for s in company_signals],
            "weights_used": {
                f"{s['signal_name']}|{s['direction']}": round(
                    weight_map.get((s["signal_name"], s["direction"]), DEFAULT_WEIGHT), 4
                )
                for s in company_signals
            },
        })

    predictions.sort(key=lambda p: p["signal_score"], reverse=True)
    state["predictions"] = predictions[:MAX_PREDICTIONS]
    logger.info(
        "Aggregated %d qualifying, top %d by signal_score from %d signals",
        len(predictions), min(len(predictions), MAX_PREDICTIONS), len(signals),
    )
    return state


def _compute_signal_score(
    signals: list[dict],
    signal_types: set[str],
    total_score: float,
    bullish_score: float,
    bearish_score: float,
) -> float:
    type_diversity = len(signal_types)
    directional_purity = abs(bullish_score - bearish_score) / total_score if total_score else 0
    recency_count = sum(1 for s in signals if s.get("signal_type") in RECENCY_TYPES)
    recency_multiplier = 1.0 + 0.5 * (recency_count / max(len(signals), 1))
    return type_diversity * directional_purity * total_score * recency_multiplier


def _signal_fingerprint(signals: list[dict]) -> str:
    parts = sorted(
        f"{s['signal_name']}|{s['direction']}|{round(float(s['confidence']), 1)}"
        for s in signals
    )
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _load_weight_map() -> dict[tuple[str, str], float]:
    signals = Signal.query.filter_by(active=True).all()
    weight_map = {}
    for s in signals:
        key = (s.name, s.direction)
        weight_map[key] = s.operative_accuracy
    return weight_map
