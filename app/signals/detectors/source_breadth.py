import logging

from datetime import datetime

from app.articles.indices import source_breadth
from app.signals.detectors.base import SignalDetector
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)


class SourceBreadthDetector(SignalDetector):
    name = "source_breadth"
    signal_type = "article"

    def __init__(self):
        self.min_sources = 3

    def detect(self, state: EngineState, before: datetime = None) -> list[SignalData]:
        signals = []
        try:
            breadth = source_breadth(before=before)
        except Exception:
            logger.exception("Failed to compute source breadth")
            return signals

        company_map = {
            data.get("symbol"): cid
            for cid, data in state.get("price_data", {}).items()
        }

        for sym, data in breadth.items():
            count = data["unique_sources"]
            if count < self.min_sources:
                continue

            company_id = company_map.get(sym)
            if not company_id:
                continue

            confidence = min(0.8, 0.35 + count * 0.1)

            source_at = data.get("latest_published_at")
            signals.append(SignalData(
                signal_name="Multi-Source Coverage",
                signal_type="article",
                company_id=company_id,
                symbol=sym,
                direction="bullish",
                confidence=confidence,
                source_at=source_at.isoformat() if source_at else "",
                context={
                    "unique_sources": count,
                    "sources": data["sources"],
                },
            ))

        return signals
