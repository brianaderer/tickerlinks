import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI

from app.extensions import db
from app.models import Company, SignalDigest
from app.signals.state import EngineState
from app.sse import sse_publish

logger = logging.getLogger(__name__)

MIN_MATCHES_FOR_DIGEST = 2

DIGEST_PROMPT = """You are a concise market signal analyst. Given the following signal matches for {symbol} ({company_name}), synthesize a 1-2 sentence digest that weighs the signals against each other and gives a net assessment.

Signals detected:
{signals_text}

Net direction from aggregation: {direction} at {confidence:.0%} confidence

Write a crisp 1-2 sentence digest. No preamble, no bullet points — just the assessment."""


def digest_node(state: EngineState) -> EngineState:
    raw_signals = state.get("signals", [])
    predictions = state.get("strong_predictions", []) + state.get("weak_predictions", [])

    if not raw_signals:
        return state

    by_company = defaultdict(list)
    for sig in raw_signals:
        by_company[sig["company_id"]].append(sig)

    pred_map = {p["company_id"]: p for p in predictions}

    llm = _get_llm()
    if not llm:
        logger.warning("No LLM configured, skipping digest generation")
        return state

    now = datetime.now(timezone.utc)
    generated = 0

    for company_id, signals in by_company.items():
        if len(signals) < MIN_MATCHES_FOR_DIGEST:
            continue

        company = Company.query.get(company_id)
        if not company:
            continue

        pred = pred_map.get(company_id, {})
        direction = pred.get("direction", _infer_direction(signals))
        confidence = pred.get("confidence", 0.5)

        signals_text = "\n".join(
            f"- {s['signal_name']} ({s['direction']}, {s['confidence']:.0%})"
            for s in signals
        )

        prompt = DIGEST_PROMPT.format(
            symbol=company.symbol,
            company_name=company.name or company.symbol,
            signals_text=signals_text,
            direction=direction,
            confidence=confidence,
        )

        try:
            response = llm.invoke(prompt)
            digest_text = _clean_response(response.content)
        except Exception:
            logger.exception("Failed to generate digest for %s", company.symbol)
            continue

        match_names = [s["signal_name"] for s in signals]

        digest = SignalDigest(
            company_id=company_id,
            direction=direction,
            net_confidence=round(confidence, 4),
            match_count=len(signals),
            digest=digest_text,
            matches=match_names,
            generated_at=now,
        )
        db.session.add(digest)
        generated += 1

        sse_publish("signals", "ticker_digest", {
            "symbol": company.symbol,
            "direction": direction,
            "net_confidence": round(confidence, 4),
            "match_count": len(signals),
            "digest": digest_text,
            "matches": match_names,
        })

    db.session.commit()
    logger.info("Generated %d ticker digests", generated)
    return state


def _get_llm() -> ChatOpenAI | None:
    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return None
    return ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.3,
        max_tokens=200,
    )


def _clean_response(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def _infer_direction(signals: list[dict]) -> str:
    bullish = sum(1 for s in signals if s["direction"] == "bullish")
    bearish = sum(1 for s in signals if s["direction"] == "bearish")
    if bullish > bearish:
        return "bullish"
    elif bearish > bullish:
        return "bearish"
    return "neutral"
