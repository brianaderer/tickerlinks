import hashlib
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone

from app.models import Signal
from app.signals.state import EngineState

logger = logging.getLogger(__name__)

DEFAULT_WEIGHT = 0.5
MIN_SIGNAL_TYPES = 2
MAX_PREDICTIONS = 10
RECENCY_TYPES = {"article_sentiment", "mention_velocity", "comention", "source_breadth"}

FRESHNESS_HALF_LIFE_HOURS = 24


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

        bullish_score = 0.0
        bearish_score = 0.0

        for s in company_signals:
            accuracy = weight_map.get((s["signal_name"], s["direction"]), DEFAULT_WEIGHT)
            contrib = s["confidence"]
            weight = abs(accuracy - 0.5) * 2.0

            freshness = _freshness_multiplier(s.get("source_at", ""))
            contrib *= freshness

            if accuracy < 0.5:
                s["antisignal"] = True
                s["antisignal_accuracy"] = round(weight * 100)
                s["original_direction"] = s["direction"]
                if s["direction"] == "bullish":
                    bearish_score += contrib * weight
                else:
                    bullish_score += contrib * weight
            else:
                if s["direction"] == "bullish":
                    bullish_score += contrib * weight
                else:
                    bearish_score += contrib * weight
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

        n_bullish = sum(1 for s in company_signals if s["direction"] == "bullish")
        n_bearish = sum(1 for s in company_signals if s["direction"] == "bearish")

        predictions.append({
            "company_id": company_id,
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "signal_score": signal_score,
            "fingerprint": fingerprint,
            "bullish_signals": n_bullish,
            "bearish_signals": n_bearish,
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


def _freshness_multiplier(source_at: str) -> float:
    if not source_at:
        return 1.0
    try:
        ts = datetime.fromisoformat(source_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        return math.exp(-0.693 * age_hours / FRESHNESS_HALF_LIFE_HOURS)
    except (ValueError, TypeError):
        return 1.0


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
