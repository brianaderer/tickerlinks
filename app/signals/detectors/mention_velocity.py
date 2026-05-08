import logging

from datetime import datetime

from app.articles.indices import mention_velocity
from app.signals.detectors.base import SignalDetector
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)


class MentionVelocityDetector(SignalDetector):
    name = "mention_velocity"
    signal_type = "article"

    def __init__(self):
        self.roc_threshold = 1.0
        self.min_count = 3

    def detect(self, state: EngineState, before: datetime = None) -> list[SignalData]:
        signals = []
        try:
            velocity = mention_velocity(before=before)
        except Exception:
            logger.exception("Failed to compute mention velocity")
            return signals

        company_map = {
            data.get("symbol"): cid
            for cid, data in state.get("price_data", {}).items()
        }

        for sym, windows in velocity.items():
            company_id = company_map.get(sym)
            if not company_id:
                continue

            for window_name in ("6h", "24h"):
                w = windows.get(window_name, {})
                count = w.get("count", 0)
                roc = w.get("rate_of_change", 0)

                if count < self.min_count or roc < self.roc_threshold:
                    continue

                confidence = min(0.85, 0.45 + roc * 0.15)

                source_at = windows.get("latest_published_at")
                signals.append(SignalData(
                    signal_name=f"Mention Spike ({window_name})",
                    signal_type="article",
                    company_id=company_id,
                    symbol=sym,
                    direction="bullish",
                    confidence=confidence,
                    source_at=source_at.isoformat() if source_at else "",
                    context={
                        "window": window_name,
                        "count": count,
                        "previous": w.get("previous", 0),
                        "rate_of_change": roc,
                    },
                ))

        return signals
