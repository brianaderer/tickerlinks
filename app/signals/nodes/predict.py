import logging
import os
import re
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from app.signals.state import EngineState
from app.signals.llm_utils import parse_llm_json
from app.signals.research import research_company

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior portfolio analyst with access to a research tool that searches an article database. Today is {today}.

For each company you analyze, you will receive:
- Technical and fundamental signals with confidence scores
- Recent price action data
- Fundamentals snapshot (P/E, beta, insider trades)

You MUST call the research_company tool at least once to search for relevant articles before making your prediction. Use the signal context to guide what you search for.

After reviewing all available data, return your final assessment as a JSON object:
{{
    "direction": "bullish" or "bearish",
    "confidence": 0.0 to 1.0,
    "magnitude": 0.0 to 1.0,
    "reasoning": "2-3 sentence explanation"
}}

MAGNITUDE represents how much attention this prediction deserves:
- High magnitude (0.7-1.0): Strong signal alignment, clear catalysts, high conviction — act on this
- Medium magnitude (0.4-0.7): Mixed but leaning signals, some uncertainty
- Low magnitude (0.0-0.4): Conflicting signals canceling out, low conviction, noise

Consider signal PURITY when setting magnitude: if bullish and bearish signals are roughly equal, that may indicate volatility rather than a clear direction. Decide whether conflicting signals represent genuine uncertainty (low magnitude) or a volatile situation worth watching (higher magnitude).

Do NOT wrap your response in markdown code fences. Return raw JSON only."""


def _format_signals(pred: dict, state: EngineState) -> str:
    signals = state.get("signals", [])
    company_signals = [s for s in signals if s["company_id"] == pred["company_id"]]
    if not company_signals:
        return "No signals detected."

    bullish = [s for s in company_signals if s["direction"] == "bullish"]
    bearish = [s for s in company_signals if s["direction"] == "bearish"]

    lines = [f"Aggregate: {pred['direction']} ({pred['confidence']:.1%} confidence)"]
    lines.append(f"Bullish ({len(bullish)}):")
    for s in bullish:
        lines.append(f"  - {s['signal_name']} (confidence: {s['confidence']:.2f}, type: {s['signal_type']})")
    lines.append(f"Bearish ({len(bearish)}):")
    for s in bearish:
        lines.append(f"  - {s['signal_name']} (confidence: {s['confidence']:.2f}, type: {s['signal_type']})")
    return "\n".join(lines)


def _format_price(company_id: int, state: EngineState) -> str:
    price_info = state.get("price_data", {}).get(company_id)
    if not price_info or price_info.get("df") is None or price_info["df"].empty:
        return "No price data available."

    df = price_info["df"]
    latest = df.iloc[-1]
    lines = [f"Latest close: ${latest['close']:.2f}"]

    if len(df) >= 2:
        prev = df.iloc[-2]
        day_change = (latest["close"] - prev["close"]) / prev["close"] * 100
        lines.append(f"1-day change: {day_change:+.2f}%")

    if len(df) >= 7:
        week_ago = df.iloc[-7]
        week_change = (latest["close"] - week_ago["close"]) / week_ago["close"] * 100
        lines.append(f"7-day change: {week_change:+.2f}%")

    if len(df) >= 30:
        month_ago = df.iloc[-30]
        month_change = (latest["close"] - month_ago["close"]) / month_ago["close"] * 100
        lines.append(f"30-day change: {month_change:+.2f}%")

    high_52w = df["high"].max()
    low_52w = df["low"].min()
    lines.append(f"Period high: ${high_52w:.2f} | Period low: ${low_52w:.2f}")
    pct_from_high = (latest["close"] - high_52w) / high_52w * 100
    lines.append(f"Distance from period high: {pct_from_high:.1f}%")

    return "\n".join(lines)


def _format_fundamentals(company_id: int, state: EngineState) -> str:
    fund_info = state.get("fundamentals_data", {}).get(company_id)
    if not fund_info:
        return "No fundamentals data available."

    lines = []
    latest = fund_info.get("latest")
    if latest:
        if latest.get("pe_trailing"):
            lines.append(f"P/E (trailing): {latest['pe_trailing']:.1f}")
        if latest.get("beta"):
            lines.append(f"Beta: {latest['beta']:.2f}")
        if latest.get("fifty_two_week_high"):
            lines.append(f"52w high: ${latest['fifty_two_week_high']:.2f}")
        if latest.get("fifty_two_week_low"):
            lines.append(f"52w low: ${latest['fifty_two_week_low']:.2f}")

    insider_trades = fund_info.get("insider_trades", [])
    if insider_trades:
        buys = sum(1 for t in insider_trades if "purchase" in (t.get("transaction_type") or "").lower())
        sells = sum(1 for t in insider_trades if "sale" in (t.get("transaction_type") or "").lower())
        lines.append(f"Recent insider activity: {buys} buys, {sells} sells (last {len(insider_trades)} transactions)")

    return "\n".join(lines) if lines else "No fundamentals data available."


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def predict_node(state: EngineState) -> EngineState:
    predictions = state.get("predictions", [])
    if not predictions:
        return state

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        logger.info("No LLM API key — using signal-only reasoning")
        for pred in predictions:
            signals = state.get("signals", [])
            company_signals = [s for s in signals if s["company_id"] == pred["company_id"]]
            signal_summary = ", ".join(s["signal_name"] for s in company_signals)
            pred["reasoning"] = f"{pred['direction'].title()} outlook based on {len(company_signals)} signals: {signal_summary}."
            pred["magnitude"] = pred["confidence"] * 0.5
        return state

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.3,
        max_tokens=1000,
    )
    llm_with_tools = llm.bind_tools([research_company])

    for pred in predictions:
        try:
            signal_context = _format_signals(pred, state)
            price_context = _format_price(pred["company_id"], state)
            fundamentals_context = _format_fundamentals(pred["company_id"], state)

            messages = [
                SystemMessage(content=SYSTEM_PROMPT.format(today=today)),
                HumanMessage(content=(
                    f"Analyze {pred['symbol']}.\n\n"
                    f"SIGNALS:\n{signal_context}\n\n"
                    f"PRICE ACTION:\n{price_context}\n\n"
                    f"FUNDAMENTALS:\n{fundamentals_context}\n\n"
                    f"Use the research_company tool to search for relevant article coverage, "
                    f"then produce your final JSON assessment."
                )),
            ]

            for _ in range(2):
                response = llm_with_tools.invoke(messages)
                if not response.tool_calls:
                    break
                messages.append(response)
                for tc in response.tool_calls:
                    logger.info("Research tool call for %s: %s", pred["symbol"], tc["args"])
                    result = research_company.invoke(tc["args"])
                    messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

            text = _strip_think_tags(response.content)
            parsed = parse_llm_json(text)

            if parsed:
                if "direction" in parsed:
                    pred["direction"] = parsed["direction"]
                if "confidence" in parsed:
                    pred["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))
                pred["magnitude"] = max(0.0, min(1.0, float(parsed.get("magnitude", 0.5))))
                pred["reasoning"] = _strip_think_tags(parsed.get("reasoning", ""))
            else:
                pred["reasoning"] = _strip_think_tags(text)
                pred["magnitude"] = pred["confidence"] * 0.5

        except Exception:
            logger.exception("Failed to generate prediction for %s", pred["symbol"])
            signals = state.get("signals", [])
            company_signals = [s for s in signals if s["company_id"] == pred["company_id"]]
            signal_summary = ", ".join(s["signal_name"] for s in company_signals)
            pred["reasoning"] = f"{pred['direction'].title()} outlook based on {len(company_signals)} signals: {signal_summary}."
            pred["magnitude"] = pred["confidence"] * 0.5

    return state
