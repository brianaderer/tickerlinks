from app.signals.nodes.predict import _fallback_reasoning, _looks_like_fallback_reasoning


def test_fallback_reasoning_marks_antisignal_as_contrarian():
    pred = {"company_id": 1, "direction": "bullish", "confidence": 0.86}
    state = {
        "signals": [
            {
                "company_id": 1,
                "signal_name": "Insider Cluster Sell",
                "direction": "bearish",
                "confidence": 0.85,
                "antisignal": True,
            },
            {
                "company_id": 1,
                "signal_name": "Article Sentiment Bullish",
                "direction": "bullish",
                "confidence": 0.57,
            },
            {
                "company_id": 1,
                "signal_name": "Multi-Source Coverage",
                "direction": "bullish",
                "confidence": 0.80,
            },
        ],
    }

    _fallback_reasoning(pred, state)
    reasoning = pred["reasoning"]

    assert "effective scoring leaning bullish" in reasoning
    assert "Insider Cluster Sell (bullish" in reasoning
    assert "Contrarian adjustment applied to Insider Cluster Sell" in reasoning


def test_looks_like_fallback_reasoning_detects_legacy_template():
    assert _looks_like_fallback_reasoning("Bullish outlook based on 3 signals: A, B, C.")
    assert _looks_like_fallback_reasoning(
        "Bullish near-term setup from 3 active signals, with effective scoring leaning bullish (bullish 1.0 vs bearish 0.2)."
    )
