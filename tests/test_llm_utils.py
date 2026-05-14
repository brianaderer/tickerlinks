from app.signals.llm_utils import parse_llm_json, sanitize_reasoning_text


def test_parse_llm_json_strips_think_and_fences():
    raw = """
<think>internal chain of thought</think>
```json
{"direction":"bullish","confidence":0.72,"reasoning":"Signals align with improving momentum."}
```
"""
    parsed = parse_llm_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["direction"] == "bullish"
    assert parsed["confidence"] == 0.72


def test_parse_llm_json_handles_python_dict_blob():
    raw = "{'direction': 'bearish', 'confidence': 0.81, 'reasoning': 'Deteriorating breadth and weak momentum.'}"
    parsed = parse_llm_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["direction"] == "bearish"
    assert parsed["confidence"] == 0.81


def test_parse_llm_json_extracts_embedded_object():
    raw = "Final answer below:\\n\\n{\"direction\":\"bullish\",\"confidence\":0.63,\"reasoning\":\"Catalysts outweigh risks.\"}\\nThanks."
    parsed = parse_llm_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["reasoning"] == "Catalysts outweigh risks."


def test_sanitize_reasoning_text_extracts_plain_reasoning():
    raw = "{'direction': 'bearish', 'confidence': 0.85, 'reasoning': 'Technical weakness persists near resistance.'}"
    cleaned = sanitize_reasoning_text(raw)
    assert cleaned == "Technical weakness persists near resistance."


def test_sanitize_reasoning_text_drops_dangling_think():
    raw = "<think>I should reveal chain of thought"
    cleaned = sanitize_reasoning_text(raw)
    assert cleaned == ""
