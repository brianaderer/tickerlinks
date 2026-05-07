import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.signals.llm_utils import parse_llm_json

logger = logging.getLogger(__name__)

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        api_key = os.environ.get("DEEPINFRA_API_KEY", "")
        if not api_key:
            return None
        _llm = ChatOpenAI(
            model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
            openai_api_key=api_key,
            openai_api_base=os.environ.get(
                "LLM_API_BASE", "https://api.deepinfra.com/v1/openai"
            ),
            temperature=0.2,
            max_tokens=1000,
        )
    return _llm


SYSTEM_PROMPT = """You are a financial news analyst. You read articles and produce two things:

1. A concise summary (2-3 sentences max) capturing the key facts and implications.

2. Exactly 5 topic threads. Each topic is a short phrase (under 15 words) that identifies a broader narrative or trend this article could be part of. Think of these as threads that might connect this article to others — recurring patterns, emerging shifts, or developing stories across the market.

Good topic examples:
- "AI infrastructure spending accelerating beyond analyst forecasts"
- "Consumer staples margin pressure from commodity inflation"
- "Big tech pivoting cloud revenue toward enterprise AI workloads"

Bad topic examples (too generic):
- "Stock market news"
- "Company earnings"
- "Technology sector"

Return ONLY a JSON object:
{
    "summary": "2-3 sentence summary here.",
    "topics": [
        "Topic thread 1",
        "Topic thread 2",
        "Topic thread 3",
        "Topic thread 4",
        "Topic thread 5"
    ]
}"""


def summarize_article(title: str, summary: str = "", full_text: str = "") -> dict:
    llm = _get_llm()
    if not llm:
        return {"summary": "", "topics": []}

    body = full_text[:4000] if full_text else summary[:4000]

    user_msg = f"""Title: {title}

Content:
{body}"""

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        result = parse_llm_json(response.content)
        if result:
            topics = result.get("topics", [])
            if len(topics) > 5:
                topics = topics[:5]
            return {
                "summary": result.get("summary", ""),
                "topics": topics,
            }
    except Exception:
        logger.exception("Summary agent failed for: %s", title[:60])

    return {"summary": "", "topics": []}
