import logging
import os
import re
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from app.sse.publisher import sse_publish
from app.api.linky_tools import LINKY_TOOLS

logger = logging.getLogger(__name__)

bp = Blueprint("chat", __name__)

SYSTEM_PROMPT = """You are Linky, the AI market intelligence assistant for TickerLinks. Today is {today}.

The user is currently viewing: {page_context}

You have tools to look up company profiles (fundamentals, signals, predictions, price action), search articles in the database, check trending topics, read the latest market brief, review the signal accuracy rubric, and fetch TickerBets short-horizon model estimates. Use them to give specific, data-backed answers.

RULES:
- Be conversational but precise — cite tickers, numbers, and dates
- Keep responses focused unless the user asks for depth
- If the user is on a company page, you already know which ticker they're looking at
- Use tools proactively — don't guess when you can look up real data
- Use the ticker_bets tool with latitude when the user asks for near-term price targets/moves (1-10 days), date-specific estimates, or wants a quant check against narrative predictions
- When users ask for "most bullish/bearish" or leaderboard-style TickerBets questions across stocks, call ticker_bets_rankings (do not infer rankings from a single-symbol tool call)
- When the user asks if TickerBets is likely correct/right/wrong or asks to compare/overlay with other sources, call ticker_bets_overlay and provide a direct verdict (supports/mixed/conflicts) with concrete evidence
- Do not respond with phrases like "I don't agree/disagree" when asked for an evaluation; use tools and give the requested judgment
- Never fabricate data points — if a tool returns nothing, say so
- Do NOT wrap output in <think> tags or any XML
- When answering a follow-up, BUILD on previous context — do NOT repeat your earlier answer verbatim
- Each reply should add new insight or directly answer the new question
- If the user uses follow-up pronouns like "them/those/these", resolve them to the most recent ticker set in context instead of substituting a new list
- Mention directional accuracy at most once per conversation unless the user explicitly asks about model accuracy/statistics
- Any response that includes TickerBets information MUST include this disclaimer verbatim:
  Tickerbets provides experimental, model-based price estimates derived from historical data patterns. These outputs are not financial advice, investment recommendations, or guarantees of future performance, and should not be the sole basis for trading decisions."""

MAX_TOOL_CALLS = 5
TICKERBETS_RE = re.compile(r"\bticker[\s-]?bets?\b", re.IGNORECASE)
OVERLAY_RE = re.compile(
    r"\b(agree|disagree|correct|likely|right|wrong|overlay|reconcile|compare|consistent|line\s*up|align|assess|assessment|factor|influence|decision|trust|reliable)\b",
    re.IGNORECASE,
)
RANK_RE = re.compile(
    r"\b(most|top|best|worst|leaderboard|rank|ranking)\b",
    re.IGNORECASE,
)
ACCURACY_STATS_RE = re.compile(
    r"\b(accuracy|r\^?2|r2|rmse|mae|statistics?|confidence of model)\b",
    re.IGNORECASE,
)
FOLLOWUP_REF_RE = re.compile(
    r"\b("
    r"them|those|these|that list|the list|same stocks|same tickers|"
    r"you mentioned|mentioned earlier|mentioned first|earlier ones|first ones"
    r")\b",
    re.IGNORECASE,
)
PREDICTION_FOLLOWUP_RE = re.compile(
    r"\b(price|prices|prediction|predictions|estimate|estimates|target|targets)\b",
    re.IGNORECASE,
)
TICKER_LINE_RE = re.compile(r"^\s*(?:[-*]|\d+\.)?\s*([A-Z]{1,5})\s*[-:]", re.MULTILINE)
SECTOR_OUTLOOK_RE = re.compile(
    r"\b(sector|industry)\b.*\b(outlook|view|setup|looking)\b|\b(outlook|view|setup)\b.*\b(sector|industry)\b",
    re.IGNORECASE,
)
TICKER_TOKEN_RE = re.compile(r"\b[A-Za-z]{1,5}\b")


def _needs_tickerbets_overlay(user_text: str) -> bool:
    return bool(TICKERBETS_RE.search(user_text or "") and OVERLAY_RE.search(user_text or ""))


def _needs_tickerbets_ranking(user_text: str) -> bool:
    return bool(TICKERBETS_RE.search(user_text or "") and RANK_RE.search(user_text or ""))


def _directional_accuracy_already_mentioned(history: list[dict]) -> bool:
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        if re.search(r"directional\s+accuracy", msg.get("content", ""), re.IGNORECASE):
            return True
    return False


def _needs_followup_ticker_resolution(user_text: str) -> bool:
    text = user_text or ""
    return bool(FOLLOWUP_REF_RE.search(text))


def _extract_recent_assistant_tickers(history: list[dict]) -> list[str]:
    from app.models import Company

    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "") or ""
        line_symbols = TICKER_LINE_RE.findall(content)
        if not line_symbols:
            continue
        ordered_unique = []
        seen = set()
        for sym in line_symbols:
            if sym in seen:
                continue
            seen.add(sym)
            ordered_unique.append(sym)
        if not ordered_unique:
            continue

        known_rows = (
            Company.query.with_entities(Company.symbol)
            .filter(Company.active.is_(True), Company.symbol.in_(ordered_unique))
            .all()
        )
        known = {row[0] for row in known_rows}
        filtered = [sym for sym in ordered_unique if sym in known]
        if filtered:
            return filtered[:10]
    return []


def _needs_sector_outlook_grounding(user_text: str) -> bool:
    return bool(SECTOR_OUTLOOK_RE.search(user_text or ""))


def _extract_symbols_from_text(user_text: str) -> list[str]:
    from app.models import Company

    text = user_text or ""
    candidates = {tok.upper() for tok in TICKER_TOKEN_RE.findall(text)}
    if not candidates:
        return []
    rows = (
        Company.query.with_entities(Company.symbol)
        .filter(Company.active.is_(True), Company.symbol.in_(candidates))
        .all()
    )
    return [row[0] for row in rows]


def _needs_direct_tickerbets_grounding(user_text: str) -> bool:
    text = user_text or ""
    if not TICKERBETS_RE.search(text):
        return False
    if _needs_tickerbets_overlay(text) or _needs_tickerbets_ranking(text):
        return False
    return bool(_extract_symbols_from_text(text))


def _extract_response_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    chunks.append(text)
                continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        return "\n".join([c for c in chunks if c]).strip()
    if content is None:
        return ""
    return str(content)


@bp.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    messages = body.get("messages", [])
    page_context = body.get("page_context") or "Unknown page"

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return jsonify({"error": "LLM not configured"}), 503

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    chat_model = os.environ.get("LINKY_MODEL") or os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B")

    llm = ChatOpenAI(
        model=chat_model,
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.3,
        max_tokens=2000,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    llm_with_tools = llm.bind_tools(LINKY_TOOLS)

    lc_messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(today=today, page_context=page_context)),
    ]
    history = messages[-10:]
    for i, msg in enumerate(history):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            # Truncate older assistant messages to avoid the model parroting them
            is_last = i == len(history) - 1
            if not is_last and len(content) > 4000:
                content = content[:4000] + "\n[truncated]"
            lc_messages.append(AIMessage(content=content))

    latest_user_message = next((m.get("content", "") for m in reversed(history) if m.get("role") == "user"), "")
    if _needs_direct_tickerbets_grounding(latest_user_message):
        symbols = _extract_symbols_from_text(latest_user_message)
        if symbols:
            lc_messages.append(SystemMessage(
                content=(
                    f"For this question, call ticker_bets for these symbol(s): {', '.join(symbols)}. "
                    "Do not provide any tickerbets numbers unless they come from tool output."
                )
            ))
    if _needs_followup_ticker_resolution(latest_user_message):
        prior_tickers = _extract_recent_assistant_tickers(history)
        if prior_tickers:
            lc_messages.append(SystemMessage(
                content=(
                    "For this specific follow-up, pronouns like 'them/those/these' refer to this exact ticker set: "
                    f"{', '.join(prior_tickers)}. Keep the same set unless the user explicitly asks to change it."
                )
            ))
            lc_messages.append(SystemMessage(
                content=(
                    "If the user asks for price predictions/estimates for that set, call ticker_bets for those same "
                    "tickers and summarize results for each one."
                )
            ))
    if _needs_sector_outlook_grounding(latest_user_message):
        lc_messages.append(SystemMessage(
            content=(
                "For sector/industry outlook questions, ground the answer with tools (get_trends, get_market_brief, "
                "or screen_stocks) before concluding. Do not invent ticker-level prediction numbers."
            )
        ))
    if _needs_tickerbets_ranking(latest_user_message):
        lc_messages.append(SystemMessage(
            content=(
                "For this specific question, call ticker_bets_rankings to produce grounded bullish/bearish results. "
                "Do not infer cross-stock rankings from single-stock outputs."
            )
        ))
    if _needs_tickerbets_overlay(latest_user_message):
        lc_messages.append(SystemMessage(
            content=(
                "For this specific user question, call ticker_bets_overlay before answering. "
                "Return a direct verdict label (supports/mixed/conflicts) backed by the tool evidence."
            )
        ))
    if _directional_accuracy_already_mentioned(history) and not ACCURACY_STATS_RE.search(latest_user_message or ""):
        lc_messages.append(SystemMessage(
            content=(
                "Directional accuracy has already been mentioned in this conversation. "
                "Do not repeat directional accuracy again unless the user explicitly asks for model metrics/statistics."
            )
        ))

    try:
        tool_map = {t.name: t for t in LINKY_TOOLS}
        tool_calls_made = 0
        must_ground_followup = _needs_followup_ticker_resolution(latest_user_message)
        forced_grounding_retry = False
        response = None

        for _ in range(MAX_TOOL_CALLS + 1):
            if tool_calls_made >= MAX_TOOL_CALLS:
                lc_messages.append(SystemMessage(
                    content=(
                        "Tool-call budget reached. Provide the best possible final answer using the available "
                        "tool outputs and prior context. Do not call any additional tools."
                    )
                ))
                response = llm.invoke(lc_messages)
                break

            response = llm_with_tools.invoke(lc_messages)

            if (
                must_ground_followup
                and not response.tool_calls
                and tool_calls_made == 0
                and not forced_grounding_retry
            ):
                forced_grounding_retry = True
                lc_messages.append(response)
                lc_messages.append(SystemMessage(
                    content=(
                        "You must call ticker_bets for the referenced ticker set before answering. "
                        "Do not provide any predicted numbers without tool output."
                    )
                ))
                continue

            if not response.tool_calls:
                break

            lc_messages.append(response)
            for tc in response.tool_calls:
                if tool_calls_made >= MAX_TOOL_CALLS:
                    lc_messages.append(ToolMessage(
                        content="Tool call limit reached.",
                        tool_call_id=tc["id"],
                    ))
                    continue

                tool_name = tc["name"]
                tool_fn = tool_map.get(tool_name)
                if not tool_fn:
                    lc_messages.append(ToolMessage(
                        content=f"Unknown tool: {tool_name}",
                        tool_call_id=tc["id"],
                    ))
                    continue

                logger.info("Linky tool call: %s(%s)", tool_name, tc["args"])
                sse_publish("chat", "tool_call", {"tool": tool_name, "args": tc["args"]})

                try:
                    result = tool_fn.invoke(tc["args"])
                except Exception as tool_exc:
                    logger.exception("Linky tool failed: %s", tool_name)
                    result = f"Tool {tool_name} failed: {tool_exc}"
                lc_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                tool_calls_made += 1

        if response is None:
            response = llm.invoke(lc_messages)

        text = _extract_response_text(getattr(response, "content", ""))
        text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
        if not text:
            fallback = llm.invoke(
                lc_messages
                + [
                    SystemMessage(
                        content=(
                            "Provide a concise final answer from the available context and tool outputs. "
                            "Do not call tools."
                        )
                    )
                ]
            )
            text = _extract_response_text(getattr(fallback, "content", ""))
            text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
        if not text:
            text = "I'm sorry — I couldn't produce a response just now. Please try again."

        return jsonify({"response": text})

    except Exception as e:
        logger.exception("Linky chat failed")
        return jsonify({"error": str(e)}), 502
