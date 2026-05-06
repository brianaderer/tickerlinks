import logging

from datetime import datetime

from app.articles.indices import sentiment_score
from app.signals.detectors.base import SignalDetector
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)


class ArticleSentimentDetector(SignalDetector):
    name = "article_sentiment"
    signal_type = "article"

    def __init__(self):
        self.threshold = 0.3
        self.min_mentions = 2

    def detect(self, state: EngineState, before: datetime = None) -> list[SignalData]:
        signals = []
        try:
            scores = sentiment_score(before=before)
        except Exception:
            logger.exception("Failed to compute sentiment scores")
            return signals

        company_map = {
            data.get("symbol"): cid
            for cid, data in state.get("price_data", {}).items()
        }

        for sym, data in scores.items():
            if data["total_mentions"] < self.min_mentions:
                continue

            score = data["score"]
            if abs(score) < self.threshold:
                continue

            company_id = company_map.get(sym)
            if not company_id:
                continue

            direction = "bullish" if score > 0 else "bearish"
            confidence = min(0.9, 0.4 + abs(score) * 0.5)

            signals.append(SignalData(
                signal_name=f"Article Sentiment {direction.title()}",
                signal_type="article",
                company_id=company_id,
                symbol=sym,
                direction=direction,
                confidence=confidence,
                context={
                    "sentiment_score": score,
                    "bullish": data["bullish"],
                    "bearish": data["bearish"],
                    "neutral": data["neutral"],
                    "total_mentions": data["total_mentions"],
                },
            ))

        return signals
