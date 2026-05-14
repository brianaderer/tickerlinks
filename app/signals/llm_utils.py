import ast
import json
import re
from typing import Any


THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?</think>", flags=re.IGNORECASE)
THINK_TAG_RE = re.compile(r"</?think>", flags=re.IGNORECASE)
FENCE_RE = re.compile(r"```(?:json)?", flags=re.IGNORECASE)


def _first_struct_idx(text: str) -> int:
    obj_idx = text.find("{")
    arr_idx = text.find("[")
    candidates = [idx for idx in (obj_idx, arr_idx) if idx != -1]
    return min(candidates) if candidates else -1


def strip_llm_artifacts(text: str) -> str:
    """Remove think tags and markdown wrappers from model output."""
    if not text:
        return ""

    cleaned = THINK_BLOCK_RE.sub("", text)
    cleaned = FENCE_RE.sub("", cleaned)

    lower = cleaned.lower()
    think_idx = lower.find("<think>")
    if think_idx != -1:
        struct_idx = _first_struct_idx(cleaned)
        cleaned = cleaned[struct_idx:] if struct_idx > think_idx else cleaned[:think_idx]

    cleaned = THINK_TAG_RE.sub("", cleaned)
    cleaned = cleaned.replace("```", "")
    return cleaned.strip()


def _try_json(candidate: str) -> Any | None:
    candidate = candidate.strip()
    if not candidate:
        return None

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    normalized = (
        candidate
        .replace("“", "\"")
        .replace("”", "\"")
        .replace("’", "'")
    )
    try:
        value = ast.literal_eval(normalized)
        if isinstance(value, (dict, list)):
            return value
    except (SyntaxError, ValueError):
        return None
    return None


def _balanced_candidates(text: str):
    stack: list[str] = []
    start: int | None = None
    close_for = {"{": "}", "[": "]"}

    for i, ch in enumerate(text):
        if ch in close_for:
            if not stack:
                start = i
            stack.append(ch)
            continue

        if ch in ("}", "]") and stack:
            expected = close_for[stack[-1]]
            if ch == expected:
                stack.pop()
                if not stack and start is not None:
                    yield text[start : i + 1]
                    start = None
            else:
                stack = []
                start = None


def parse_llm_json(text: str) -> Any | None:
    """Extract structured JSON/dict output from noisy LLM responses."""
    cleaned = strip_llm_artifacts(text)
    if not cleaned:
        return None

    direct = _try_json(cleaned)
    if direct is not None:
        return direct

    for candidate in _balanced_candidates(cleaned):
        parsed = _try_json(candidate)
        if parsed is not None:
            return parsed

    return None


def sanitize_reasoning_text(text: str) -> str:
    """Return clean plain-text reasoning (no think tags, no raw JSON blobs)."""
    if not text:
        return ""

    cleaned = strip_llm_artifacts(text)
    parsed = parse_llm_json(cleaned)
    if isinstance(parsed, dict):
        nested = parsed.get("reasoning") or parsed.get("summary") or parsed.get("content")
        if isinstance(nested, str):
            cleaned = strip_llm_artifacts(nested)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Guard: if we still have a raw object-like blob, treat as unusable text.
    if cleaned.startswith("{") and cleaned.endswith("}"):
        parsed_blob = parse_llm_json(cleaned)
        if isinstance(parsed_blob, dict):
            nested = parsed_blob.get("reasoning") or parsed_blob.get("summary")
            if isinstance(nested, str):
                return re.sub(r"\s+", " ", strip_llm_artifacts(nested)).strip()
            return ""

    return cleaned
