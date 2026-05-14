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
- Mention directional accuracy at most once per conversation unless the user explicitly asks about model accuracy/statistics
- Any response that includes TickerBets information MUST include this disclaimer verbatim:
  Tickerbets provides experimental, model-based price estimates derived from historical data patterns. These outputs are not financial advice, investment recommendations, or guarantees of future performance, and should not be the sole basis for trading decisions."""

MAX_TOOL_CALLS = 5
TICKERBETS_RE = re.compile(r"\bticker[\s-]?bets?\b", re.IGNORECASE)
OVERLAY_RE = re.compile(
    r"\b(agree|disagree|correct|likely|right|wrong|overlay|reconcile|compare|consistent|line\s*up|align)\b",
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

    llm = ChatOpenAI(
        model="Qwen/Qwen3-14B",
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

        for _ in range(MAX_TOOL_CALLS + 1):
            response = llm_with_tools.invoke(lc_messages)

            if not response.tool_calls or tool_calls_made >= MAX_TOOL_CALLS:
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

                result = tool_fn.invoke(tc["args"])
                lc_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                tool_calls_made += 1

        text = response.content or ""
        text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

        return jsonify({"response": text})

    except Exception as e:
        logger.exception("Linky chat failed")
        return jsonify({"error": str(e)}), 502
