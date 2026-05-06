import logging
import os
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.signals.state import EngineState

logger = logging.getLogger(__name__)

PREDICT_PROMPT = """You are a senior portfolio analyst. Based on the following aggregated signals for {symbol}, write a concise prediction.

Direction: {direction} (confidence: {confidence:.1%})
Bullish signals ({bullish_count}): {bullish_names}
Bearish signals ({bearish_count}): {bearish_names}

Write a 2-3 sentence prediction explaining the outlook and key drivers. Be specific about what the signals suggest."""


def predict_node(state: EngineState) -> EngineState:
    predictions = state.get("predictions", [])
    if not predictions:
        return state

    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    llm = None
    if api_key:
        llm = ChatOpenAI(
            model=os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-14B-Instruct"),
            openai_api_key=api_key,
            openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
            temperature=0.3,
            max_tokens=300,
        )
    else:
        logger.info("No LLM API key configured — using signal-only reasoning")

    for pred in predictions:
        signals = state.get("signals", [])
        company_signals = [s for s in signals if s["company_id"] == pred["company_id"]]

        bullish = [s for s in company_signals if s["direction"] == "bullish"]
        bearish = [s for s in company_signals if s["direction"] == "bearish"]

        if llm:
            try:
                prompt = PREDICT_PROMPT.format(
                    symbol=pred["symbol"],
                    direction=pred["direction"],
                    confidence=pred["confidence"],
                    bullish_count=len(bullish),
                    bullish_names=", ".join(s["signal_name"] for s in bullish) or "none",
                    bearish_count=len(bearish),
                    bearish_names=", ".join(s["signal_name"] for s in bearish) or "none",
                )
                response = llm.invoke([
                    SystemMessage(content="You are a financial prediction system. Be concise and data-driven."),
                    HumanMessage(content=prompt),
                ])
                text = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip()
                pred["reasoning"] = text
                continue
            except Exception:
                logger.exception("Failed to generate reasoning for %s", pred["symbol"])

        signal_summary = ", ".join(s["signal_name"] for s in company_signals)
        pred["reasoning"] = f"{pred['direction'].title()} outlook based on {len(company_signals)} signals: {signal_summary}."

    return state
