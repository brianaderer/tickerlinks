import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.signals.detectors.base import SignalDetector
from app.signals.llm_utils import parse_llm_json
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """You are a financial sentiment analyst. Analyze the following news articles about {symbol} and score the overall sentiment.

Articles:
{articles}

Respond with ONLY a JSON object:
{{
    "sentiment_score": <float from -1.0 (very bearish) to 1.0 (very bullish)>,
    "direction": "<bullish|bearish|neutral>",
    "confidence": <float from 0.0 to 1.0>,
    "reasoning": "<brief explanation>"
}}"""


class SentimentDetector(SignalDetector):
    name = "sentiment"
    signal_type = "sentiment"

    def __init__(self):
        self.sentiment_threshold = 0.3
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-14B-Instruct"),
                openai_api_key=os.environ.get("DEEPINFRA_API_KEY", ""),
                openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
                temperature=0.1,
                max_tokens=2000,
            )
        return self._llm

    def detect(self, state: EngineState) -> list[SignalData]:
        signals = []
        for company_id, news_info in state.get("news_data", {}).items():
            symbol = news_info.get("symbol", "?")
            articles = news_info.get("articles", [])
            if not articles:
                continue

            try:
                signal = self._analyze_sentiment(company_id, symbol, articles)
                if signal:
                    signals.append(signal)
            except Exception:
                logger.exception("Sentiment analysis failed for %s", symbol)

        return signals

    def _analyze_sentiment(self, company_id: int, symbol: str, articles: list[dict]) -> SignalData | None:
        batch = articles[:15]
        article_text = "\n".join(
            f"- [{a['published_at']}] {a['title']}: {a.get('summary', '')[:200]}"
            for a in batch
        )
        latest_pub = max(
            (a["published_at"] for a in batch if a.get("published_at")),
            default=None,
        )

        prompt = SENTIMENT_PROMPT.format(symbol=symbol, articles=article_text)
        response = self.llm.invoke([
            SystemMessage(content="You are a financial sentiment analysis system."),
            HumanMessage(content=prompt),
        ])

        result = parse_llm_json(response.content)
        if not result:
            logger.warning("Failed to parse LLM response for %s: %s", symbol, response.content[:200])
            return None

        direction = result.get("direction", "neutral")
        confidence = float(result.get("confidence", 0))
        score = float(result.get("sentiment_score", 0))

        if direction == "neutral" or abs(score) < self.sentiment_threshold:
            return None

        source_at_str = ""
        if latest_pub:
            if isinstance(latest_pub, str):
                source_at_str = latest_pub
            else:
                source_at_str = latest_pub.isoformat()

        return SignalData(
            signal_name=f"News Sentiment {direction.title()}",
            signal_type="sentiment",
            company_id=company_id,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            source_at=source_at_str,
            context={
                "sentiment_score": score,
                "reasoning": result.get("reasoning", ""),
                "article_count": len(articles),
            },
        )
