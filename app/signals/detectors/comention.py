import logging

from datetime import datetime

from app.articles.indices import comention_pairs, sentiment_score
from app.signals.detectors.base import SignalDetector
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)


class ComentionDetector(SignalDetector):
    name = "comention"
    signal_type = "article"

    def __init__(self):
        self.min_comentions = 2
        self.divergence_threshold = 0.5

    def detect(self, state: EngineState, before: datetime = None) -> list[SignalData]:
        signals = []
        try:
            pairs = comention_pairs(before=before)
            scores = sentiment_score(before=before)
        except Exception:
            logger.exception("Failed to compute comention data")
            return signals

        company_map = {
            data.get("symbol"): cid
            for cid, data in state.get("price_data", {}).items()
        }

        for pair_key, data in pairs.items():
            if data["count"] < self.min_comentions:
                continue

            if data["divergence_ratio"] < self.divergence_threshold:
                continue

            sym_a, sym_b = pair_key.split("/")

            score_a = scores.get(sym_a, {}).get("score", 0)
            score_b = scores.get(sym_b, {}).get("score", 0)

            spread = score_a - score_b
            if abs(spread) < 0.3:
                continue

            confidence = min(0.8, 0.4 + abs(spread) * 0.3)
            source_at = data.get("latest_published_at")
            source_at_str = source_at.isoformat() if source_at else ""

            favored = sym_a if spread > 0 else sym_b
            disfavored = sym_b if spread > 0 else sym_a

            cid_favored = company_map.get(favored)
            cid_disfavored = company_map.get(disfavored)

            if cid_favored:
                signals.append(SignalData(
                    signal_name="Co-mention Relative Strength",
                    signal_type="article",
                    company_id=cid_favored,
                    symbol=favored,
                    direction="bullish",
                    confidence=confidence,
                    source_at=source_at_str,
                    context={
                        "pair": pair_key,
                        "peer": disfavored,
                        "sentiment_spread": round(spread, 3),
                        "comentions": data["count"],
                    },
                ))

            if cid_disfavored:
                signals.append(SignalData(
                    signal_name="Co-mention Relative Weakness",
                    signal_type="article",
                    company_id=cid_disfavored,
                    symbol=disfavored,
                    direction="bearish",
                    confidence=confidence,
                    source_at=source_at_str,
                    context={
                        "pair": pair_key,
                        "peer": favored,
                        "sentiment_spread": round(-spread, 3),
                        "comentions": data["count"],
                    },
                ))

        return signals
