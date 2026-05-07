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

SYSTEM_PROMPT = """You are Linky, the AI market intelligence assistant for StockLynx. Today is {today}.

The user is currently viewing: {page_context}

You have tools to look up company profiles (fundamentals, signals, predictions, price action), search articles in the database, check trending topics, read the latest market brief, and review the signal accuracy rubric. Use them to give specific, data-backed answers.

RULES:
- Be conversational but precise — cite tickers, numbers, and dates
- Keep responses focused unless the user asks for depth
- If the user is on a company page, you already know which ticker they're looking at
- Use tools proactively — don't guess when you can look up real data
- Never fabricate data points — if a tool returns nothing, say so
- Do NOT wrap output in <think> tags or any XML
- When answering a follow-up, BUILD on previous context — do NOT repeat your earlier answer verbatim
- Each reply should add new insight or directly answer the new question"""

MAX_TOOL_CALLS = 5


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
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.3,
        max_tokens=2000,
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
            if not is_last and len(content) > 500:
                content = content[:500] + "\n[truncated]"
            lc_messages.append(AIMessage(content=content))

    sse_publish("chat", "thinking", {})

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

        sse_publish("chat", "done", {"text": text})
        return jsonify({"response": text})

    except Exception as e:
        logger.exception("Linky chat failed")
        sse_publish("chat", "error", {"error": str(e)})
        return jsonify({"error": str(e)}), 502
