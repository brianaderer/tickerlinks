import json
import os
import re

from flask import Blueprint, request, jsonify
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.sse.publisher import sse_publish

bp = Blueprint("chat", __name__)

SYSTEM_PROMPT = """You are Linky, a concise market intelligence assistant for StockLynx.
You have access to real-time signal data, price movements, article sentiment, and predictions.
Answer questions about tickers, signals, predictions, and market conditions.
Be direct, cite specific data points when available, and keep responses under 4 sentences unless more detail is requested.
Strip any <think> tags from your output — respond only with the final answer."""


@bp.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    messages = body.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return jsonify({"error": "LLM not configured"}), 503

    lc_messages = _build_context(messages)

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.4,
        max_tokens=800,
        streaming=True,
    )

    sse_publish("chat", "thinking", {})

    try:
        full_text = ""
        inside_think = False

        for chunk in llm.stream(lc_messages):
            token = chunk.content
            if not token:
                continue

            if "<think>" in token:
                inside_think = True
                token = token.split("<think>")[0]
            if "</think>" in token:
                inside_think = False
                token = token.split("</think>")[-1]
            if inside_think:
                continue
            if not token:
                continue

            full_text += token
            sse_publish("chat", "token", {"text": token})

        full_text = re.sub(r"<think>.*?</think>", "", full_text, flags=re.DOTALL).strip()
        sse_publish("chat", "done", {"text": full_text})

        return jsonify({"response": full_text})

    except Exception as e:
        sse_publish("chat", "error", {"error": str(e)})
        return jsonify({"error": str(e)}), 502


def _build_context(messages: list[dict]) -> list:
    lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]

    _inject_data_context(lc_messages)

    for msg in messages[-10:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))

    return lc_messages


def _inject_data_context(lc_messages: list):
    from app.models import Signal, SignalMatch, Prediction, Report
    from app.articles.indices import all_indices

    try:
        matches = SignalMatch.query.order_by(SignalMatch.detected_at.desc()).limit(10).all()
        if matches:
            sig_text = "Recent signal matches:\n"
            for m in matches:
                sig_text += f"- {m.signal.name} on {m.company.symbol} ({m.direction}, {m.confidence:.0%}) at {m.detected_at.strftime('%Y-%m-%d %H:%M')}\n"
            lc_messages.append(SystemMessage(content=sig_text))

        preds = Prediction.query.order_by(Prediction.created_at.desc()).limit(5).all()
        if preds:
            pred_text = "Latest predictions:\n"
            for p in preds:
                pred_text += f"- {p.company.symbol}: {p.direction} ({p.confidence:.0%})\n"
            lc_messages.append(SystemMessage(content=pred_text))

        weights = Signal.query.filter_by(active=True).all()
        if weights:
            w_text = "Signal weights (operative accuracy):\n"
            for s in weights:
                w_text += f"- {s.name} ({s.direction}): {s.operative_accuracy:.2%}\n"
            lc_messages.append(SystemMessage(content=w_text))

        report = Report.query.order_by(Report.generated_at.desc()).first()
        if report and report.summary:
            lc_messages.append(SystemMessage(content=f"Latest report summary:\n{report.summary[:500]}"))

        indices = all_indices()
        if indices:
            idx_text = "Article indices snapshot:\n"
            for key, val in indices.items():
                if isinstance(val, dict):
                    idx_text += f"- {key}: {json.dumps(val)[:200]}\n"
            lc_messages.append(SystemMessage(content=idx_text[:800]))
    except Exception:
        pass
