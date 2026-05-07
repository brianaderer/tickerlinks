import logging
from collections import defaultdict

from app.models import Signal
from app.signals.state import EngineState

logger = logging.getLogger(__name__)

DEFAULT_WEIGHT = 0.5
MIN_SIGNAL_TYPES = 2
MIN_WEIGHTED_SCORE = 1.5


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

        signal_types = set(s["signal_type"] for s in company_signals)
        if len(signal_types) < MIN_SIGNAL_TYPES:
            continue
        if total_score < MIN_WEIGHTED_SCORE:
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

        predictions.append({
            "company_id": company_id,
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
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

    predictions.sort(key=lambda p: p["confidence"], reverse=True)
    state["predictions"] = predictions
    logger.info("Aggregated %d predictions from %d signals (weighted)", len(predictions), len(signals))
    return state


def _load_weight_map() -> dict[tuple[str, str], float]:
    """Load operative accuracy (decay-weighted) from DB as signal weights."""
    signals = Signal.query.filter_by(active=True).all()
    weight_map = {}
    for s in signals:
        key = (s.name, s.direction)
        weight_map[key] = s.operative_accuracy
    return weight_map
