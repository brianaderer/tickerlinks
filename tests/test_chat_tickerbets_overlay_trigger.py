from app.api.chat import (
    _directional_accuracy_already_mentioned,
    _needs_direct_tickerbets_grounding,
    _needs_followup_ticker_resolution,
    _needs_sector_outlook_grounding,
    _needs_tickerbets_overlay,
    _needs_tickerbets_ranking,
)


def test_overlay_trigger_detects_tickerbets_eval_prompt():
    text = "Based on the data, is TickerBets likely correct for AAPL over 5 days?"
    assert _needs_tickerbets_overlay(text) is True


def test_overlay_trigger_ignores_plain_tickerbets_quote_prompt():
    text = "Give me the 5-day TickerBets estimate for AAPL."
    assert _needs_tickerbets_overlay(text) is False


def test_ranking_trigger_detects_cross_stock_prompt():
    text = "What stocks is Tickerbets most bearish or bullish on in a 5 day view right now?"
    assert _needs_tickerbets_ranking(text) is True


def test_ranking_trigger_ignores_single_symbol_prompt():
    text = "Is TickerBets bullish or bearish on CDW over 5 days?"
    assert _needs_tickerbets_ranking(text) is False


def test_directional_accuracy_mention_detection():
    history = [
        {"role": "user", "content": "how is cdw"},
        {"role": "assistant", "content": "Directional accuracy is 57.7% for this run."},
    ]
    assert _directional_accuracy_already_mentioned(history) is True


def test_followup_resolution_detects_them_prediction_request():
    text = "Can you get price predictions for them?"
    assert _needs_followup_ticker_resolution(text) is True


def test_followup_resolution_detects_you_mentioned_first_phrase():
    text = "No, I meant for the stocks you mentioned first."
    assert _needs_followup_ticker_resolution(text) is True


def test_sector_outlook_grounding_trigger_detects_sector_question():
    assert _needs_sector_outlook_grounding("what is the tech sector outlook") is True


def test_overlay_trigger_detects_assessment_language():
    text = "What factors influence the decision when assessing the TickerBets forecast for IBM?"
    assert _needs_tickerbets_overlay(text) is True


def test_direct_tickerbets_grounding_detects_symbol_queries(monkeypatch):
    monkeypatch.setattr("app.api.chat._extract_symbols_from_text", lambda _text: ["MPWR"])
    assert _needs_direct_tickerbets_grounding("what is the tickerbets 10 days for mpwr") is True
