from app.api.chat import (
    _directional_accuracy_already_mentioned,
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
