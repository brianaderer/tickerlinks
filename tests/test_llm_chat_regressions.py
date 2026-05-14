from types import SimpleNamespace

from app import create_app
import app.api.chat as chat_module


class _FakeTool:
    def __init__(self, name: str, fn):
        self.name = name
        self._fn = fn

    def invoke(self, args):
        return self._fn(args)


class _SequencedLLM:
    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls = []

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        if not self._responses:
            return SimpleNamespace(content="", tool_calls=[])
        nxt = self._responses.pop(0)
        return SimpleNamespace(content=nxt.get("content", ""), tool_calls=nxt.get("tool_calls", []))


def test_followup_reference_forces_tool_grounding(monkeypatch):
    llm = _SequencedLLM(
        [
            {"content": "Ungrounded answer", "tool_calls": []},
            {
                "content": "",
                "tool_calls": [
                    {"id": "tc-1", "name": "ticker_bets", "args": {"symbol": "MPWR", "horizon_days": 5}}
                ],
            },
            {"content": "Grounded answer", "tool_calls": []},
        ]
    )

    tool_calls = []

    def _ticker_bets(args):
        tool_calls.append(args)
        return "TickerBets estimate for MPWR ..."

    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    monkeypatch.setattr(chat_module, "ChatOpenAI", lambda *args, **kwargs: llm)
    monkeypatch.setattr(chat_module, "LINKY_TOOLS", [_FakeTool("ticker_bets", _ticker_bets)])
    monkeypatch.setattr(chat_module, "sse_publish", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_module, "_extract_recent_assistant_tickers", lambda _history: ["MPWR", "NXPI"])

    app = create_app()
    client = app.test_client()
    res = client.post(
        "/api/chat",
        json={
            "messages": [
                {"role": "assistant", "content": "MPWR - bullish\nNXPI - bullish"},
                {"role": "user", "content": "No, I meant for the stocks you mentioned first.."},
            ],
            "page_context": "ChatDrawer",
        },
    )

    assert res.status_code == 200
    body = res.get_json()
    assert body["response"] == "Grounded answer"
    assert len(tool_calls) == 1
    assert tool_calls[0]["symbol"] == "MPWR"
    assert len(llm.calls) >= 2
    assert any(
        "You must call ticker_bets for the referenced ticker set" in getattr(msg, "content", "")
        for msg in llm.calls[1]
    )


def test_sector_outlook_tool_failure_does_not_500(monkeypatch):
    llm = _SequencedLLM(
        [
            {
                "content": "",
                "tool_calls": [
                    {"id": "tc-1", "name": "screen_stocks", "args": {"sort_by": "prediction", "direction": "any"}}
                ],
            },
            {"content": "Sector outlook: mixed with selective strength.", "tool_calls": []},
        ]
    )

    def _boom(_args):
        raise RuntimeError("tool exploded")

    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    monkeypatch.setattr(chat_module, "ChatOpenAI", lambda *args, **kwargs: llm)
    monkeypatch.setattr(chat_module, "LINKY_TOOLS", [_FakeTool("screen_stocks", _boom)])
    monkeypatch.setattr(chat_module, "sse_publish", lambda *args, **kwargs: None)

    app = create_app()
    client = app.test_client()
    res = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "what is the tech sector outlook"}],
            "page_context": "ChatDrawer",
        },
    )

    assert res.status_code == 200
    body = res.get_json()
    assert "Sector outlook" in body["response"]


def test_tool_budget_exhaustion_returns_non_empty_answer(monkeypatch):
    llm = _SequencedLLM(
        [
            {
                "content": "",
                "tool_calls": [
                    {"id": "tc-1", "name": "ticker_bets", "args": {"symbol": "AAPL", "horizon_days": 10}}
                ],
            },
            {"content": "Final synthesized response after tool budget.", "tool_calls": []},
        ]
    )

    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    monkeypatch.setattr(chat_module, "ChatOpenAI", lambda *args, **kwargs: llm)
    monkeypatch.setattr(chat_module, "LINKY_TOOLS", [_FakeTool("ticker_bets", lambda _args: "tool output")])
    monkeypatch.setattr(chat_module, "sse_publish", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_module, "MAX_TOOL_CALLS", 1)

    app = create_app()
    client = app.test_client()
    res = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Can you give me a 10 day comprehensive forecast for AAPL and cohorts?"}],
            "page_context": "ChatDrawer",
        },
    )

    assert res.status_code == 200
    body = res.get_json()
    assert body["response"] == "Final synthesized response after tool budget."
