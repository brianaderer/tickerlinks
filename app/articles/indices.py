import logging
import os
from collections import defaultdict
from datetime import datetime, timezone

import chromadb

logger = logging.getLogger(__name__)

_chroma_collection = None


def _get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        host = os.environ.get("CHROMA_HOST", "chromadb")
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        client = chromadb.HttpClient(host=host, port=port)
        _chroma_collection = client.get_or_create_collection(
            name="article_chunks",
            metadata={"hnsw:space": "cosine"},
        )
    return _chroma_collection


def _load_chunk0_metadatas(before: datetime = None, after: datetime = None) -> list[dict]:
    col = _get_collection()
    docs = col.get(limit=50000, include=["metadatas"])
    results = []
    for m in docs["metadatas"]:
        if m.get("chunk_index", 0) != 0:
            continue
        if before or after:
            ts = _parse_timestamp(m.get("published_at", ""))
            if not ts:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if before and ts > before:
                continue
            if after and ts < after:
                continue
        results.append(m)
    return results


def _parse_sentiments(sentiments_str: str) -> dict[str, str]:
    result = {}
    if not sentiments_str:
        return result
    for pair in sentiments_str.split(","):
        if ":" in pair:
            sym, sent = pair.split(":", 1)
            result[sym.strip().upper()] = sent.strip()
    return result


def _parse_companies(companies_str: str) -> list[str]:
    if not companies_str:
        return []
    return [c.strip().upper() for c in companies_str.split(",") if c.strip()]


def _parse_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None


def sentiment_score(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    stats = defaultdict(lambda: {"bullish": 0, "bearish": 0, "neutral": 0, "total": 0})

    for m in metas:
        sentiments = _parse_sentiments(m.get("company_sentiments", ""))
        for sym, sent in sentiments.items():
            if symbol and sym != symbol.upper():
                continue
            stats[sym]["total"] += 1
            if sent in ("bullish", "bearish", "neutral"):
                stats[sym][sent] += 1

    result = {}
    for sym, s in stats.items():
        total = s["total"]
        result[sym] = {
            "score": round((s["bullish"] - s["bearish"]) / total, 4) if total else 0,
            "bullish": s["bullish"],
            "bearish": s["bearish"],
            "neutral": s["neutral"],
            "total_mentions": total,
        }
    return result


def mention_velocity(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    anchor = before or datetime.now(timezone.utc)

    windows = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
    counts = defaultdict(lambda: {w: 0 for w in windows})
    prev_counts = defaultdict(lambda: {w: 0 for w in windows})

    for m in metas:
        companies = _parse_companies(m.get("companies", ""))
        ts = _parse_timestamp(m.get("published_at", ""))
        if not ts:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        age_seconds = (anchor - ts).total_seconds()
        if age_seconds < 0:
            continue

        for sym in companies:
            if symbol and sym != symbol.upper():
                continue
            for window_name, window_secs in windows.items():
                if age_seconds <= window_secs:
                    counts[sym][window_name] += 1
                elif age_seconds <= window_secs * 2:
                    prev_counts[sym][window_name] += 1

    result = {}
    for sym in set(list(counts.keys()) + list(prev_counts.keys())):
        velocity = {}
        for w in windows:
            current = counts[sym][w]
            previous = prev_counts[sym][w]
            rate_of_change = (current - previous) / max(previous, 1)
            velocity[w] = {
                "count": current,
                "previous": previous,
                "rate_of_change": round(rate_of_change, 3),
            }
        result[sym] = velocity
    return result


def comention_pairs(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    pairs = defaultdict(lambda: {"count": 0, "same_sentiment": 0, "divergent_sentiment": 0})

    for m in metas:
        sentiments = _parse_sentiments(m.get("company_sentiments", ""))
        syms = list(sentiments.keys())
        if len(syms) < 2:
            continue

        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                a, b = sorted([syms[i], syms[j]])
                if symbol and symbol.upper() not in (a, b):
                    continue

                pair_key = f"{a}/{b}"
                pairs[pair_key]["count"] += 1

                sent_a = sentiments[syms[i]]
                sent_b = sentiments[syms[j]]
                if sent_a == sent_b:
                    pairs[pair_key]["same_sentiment"] += 1
                else:
                    pairs[pair_key]["divergent_sentiment"] += 1

    result = {}
    for pair_key, data in sorted(pairs.items(), key=lambda x: -x[1]["count"]):
        total = data["count"]
        result[pair_key] = {
            "count": total,
            "same_sentiment": data["same_sentiment"],
            "divergent_sentiment": data["divergent_sentiment"],
            "divergence_ratio": round(data["divergent_sentiment"] / max(total, 1), 3),
        }
    return result


def source_breadth(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    company_sources = defaultdict(set)

    for m in metas:
        companies = _parse_companies(m.get("companies", ""))
        source = m.get("source_name", "")
        if not source:
            continue

        for sym in companies:
            if symbol and sym != symbol.upper():
                continue
            company_sources[sym].add(source)

    result = {}
    for sym, sources in company_sources.items():
        result[sym] = {
            "unique_sources": len(sources),
            "sources": sorted(sources),
        }
    return result


def all_indices(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    return {
        "sentiment_score": sentiment_score(symbol, before=before, after=after),
        "mention_velocity": mention_velocity(symbol, before=before, after=after),
        "comention_pairs": comention_pairs(symbol, before=before, after=after),
        "source_breadth": source_breadth(symbol, before=before, after=after),
    }
