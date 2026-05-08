import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.extensions import db
from app.models import Signal, SignalMatch, Prediction
from app.models.signal_match import prediction_match
from app.signals.state import EngineState
from app.sse import sse_publish

logger = logging.getLogger(__name__)

ARTICLE_DEBOUNCE_HOURS = 24
TICKER_DEBOUNCE_HOURS = 6
ARTICLE_SIGNAL_TYPES = {"article", "sentiment"}
TICKER_SIGNAL_TYPES = {"volume", "technical", "fundamentals", "pattern"}


def output_node(state: EngineState) -> EngineState:
    raw_signals = state.get("signals", [])
    predictions = state.get("strong_predictions", []) + state.get("weak_predictions", [])
    run_id = uuid4().hex

    _persist_signals(raw_signals, run_id)
    _persist_predictions(predictions, run_id)

    logger.info(
        "Output [%s]: persisted %d signal matches and %d predictions",
        run_id[:8], len(raw_signals), len(predictions),
    )
    return state


def _persist_signals(raw_signals: list[dict], run_id: str):
    now = datetime.now(timezone.utc)

    # Delete old signal matches NOT linked to any prediction
    company_ids = list({s["company_id"] for s in raw_signals})
    if company_ids:
        linked_ids = {
            row[0] for row in
            db.session.execute(
                prediction_match.select().with_only_columns(
                    prediction_match.c.signal_match_id
                )
            ).fetchall()
        }
        old_matches = SignalMatch.query.filter(
            SignalMatch.company_id.in_(company_ids)
        ).all()
        old_match_ids = [m.id for m in old_matches if m.id not in linked_ids]

        if old_match_ids:
            SignalMatch.query.filter(SignalMatch.id.in_(old_match_ids)).delete(
                synchronize_session=False
            )
            db.session.flush()

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

        source_at = _resolve_source_at(
            signal_cache[cache_key].id,
            sig_data["company_id"],
            sig_data["direction"],
            sig_data.get("source_at", ""),
            sig_data.get("signal_type", ""),
            now,
        )

        match = SignalMatch(
            signal_id=signal_cache[cache_key].id,
            company_id=sig_data["company_id"],
            confidence=float(sig_data["confidence"]),
            direction=sig_data["direction"],
            context={k: float(v) if hasattr(v, 'item') else v for k, v in (sig_data.get("context") or {}).items()},
            run_id=run_id,
            source_at=source_at,
            detected_at=now,
        )
        db.session.add(match)

        sse_publish("signals", "match_fired", {
            "signal": sig_name,
            "symbol": sig_data.get("symbol", ""),
            "direction": direction,
            "confidence": float(sig_data["confidence"]),
        })

    db.session.commit()


def _resolve_source_at(
    signal_id: int,
    company_id: int,
    direction: str,
    raw_source_at: str,
    signal_type: str,
    now: datetime,
) -> datetime | None:
    new_ts = None
    if raw_source_at:
        try:
            new_ts = datetime.fromisoformat(raw_source_at)
            if new_ts.tzinfo is None:
                new_ts = new_ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            new_ts = None

    if signal_type in ARTICLE_SIGNAL_TYPES:
        debounce = timedelta(hours=ARTICLE_DEBOUNCE_HOURS)
    elif signal_type in TICKER_SIGNAL_TYPES:
        debounce = timedelta(hours=TICKER_DEBOUNCE_HOURS)
    else:
        debounce = timedelta(hours=TICKER_DEBOUNCE_HOURS)

    prev = (
        SignalMatch.query
        .filter_by(signal_id=signal_id, company_id=company_id, direction=direction)
        .filter(SignalMatch.source_at.isnot(None))
        .order_by(SignalMatch.detected_at.desc())
        .first()
    )

    if prev and prev.source_at and (now - prev.detected_at) <= debounce:
        return prev.source_at

    return new_ts or now


def _persist_predictions(predictions: list[dict], run_id: str):
    now = datetime.now(timezone.utc)
    target = now + timedelta(days=7)

    for pred in predictions:
        existing = Prediction.query.filter_by(
            company_id=pred["company_id"]
        ).order_by(Prediction.created_at.desc()).first()

        if existing:
            existing.direction = pred["direction"]
            existing.confidence = float(pred["confidence"])
            existing.magnitude = float(pred["magnitude"]) if pred.get("magnitude") is not None else None
            existing.reasoning = pred.get("reasoning", "")
            existing.target_date = target
            existing.created_at = now
            db.session.flush()
            prediction = existing
        else:
            prediction = Prediction(
                company_id=pred["company_id"],
                direction=pred["direction"],
                confidence=float(pred["confidence"]),
                magnitude=float(pred["magnitude"]) if pred.get("magnitude") is not None else None,
                reasoning=pred.get("reasoning", ""),
                target_date=target,
                created_at=now,
            )
            db.session.add(prediction)
            db.session.flush()

        # Link signal matches from this run by run_id + company_id
        matches = SignalMatch.query.filter_by(
            company_id=pred["company_id"], run_id=run_id
        ).all()
        prediction.signal_matches = matches

    db.session.commit()
