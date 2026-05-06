import logging
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Signal, SignalMatch, Prediction
from app.signals.state import EngineState

logger = logging.getLogger(__name__)


def output_node(state: EngineState) -> EngineState:
    raw_signals = state.get("signals", [])
    predictions = state.get("strong_predictions", []) + state.get("weak_predictions", [])

    _persist_signals(raw_signals)
    _persist_predictions(predictions, raw_signals)

    logger.info(
        "Output: persisted %d signal matches and %d predictions",
        len(raw_signals), len(predictions),
    )
    return state


def _persist_signals(raw_signals: list[dict]):
    now = datetime.now(timezone.utc)
    signal_cache = {}

    for sig_data in raw_signals:
        sig_name = sig_data["signal_name"]

        direction = sig_data["direction"]
        cache_key = (sig_name, direction)

        if cache_key not in signal_cache:
            signal_obj = Signal.query.filter_by(name=sig_name, direction=direction).first()
            if not signal_obj:
                signal_obj = Signal(
                    name=sig_name,
                    signal_type=sig_data["signal_type"],
                    direction=direction,
                    description=f"Auto-detected: {sig_name} ({direction})",
                    active=True,
                )
                db.session.add(signal_obj)
                db.session.flush()
            signal_cache[cache_key] = signal_obj

        match = SignalMatch(
            signal_id=signal_cache[cache_key].id,
            company_id=sig_data["company_id"],
            confidence=sig_data["confidence"],
            direction=sig_data["direction"],
            context=sig_data.get("context", {}),
            detected_at=now,
        )
        db.session.add(match)

    db.session.commit()


def _persist_predictions(predictions: list[dict], raw_signals: list[dict]):
    now = datetime.now(timezone.utc)
    target = now + timedelta(days=7)

    for pred in predictions:
        prediction = Prediction(
            company_id=pred["company_id"],
            direction=pred["direction"],
            confidence=pred["confidence"],
            reasoning=pred.get("reasoning", ""),
            target_date=target,
            created_at=now,
        )
        db.session.add(prediction)
        db.session.flush()

        company_matches = SignalMatch.query.filter_by(
            company_id=pred["company_id"], detected_at=now
        ).all()
        for match in company_matches:
            prediction.signal_matches.append(match)

    db.session.commit()
