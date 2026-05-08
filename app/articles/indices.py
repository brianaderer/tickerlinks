import logging
from collections import defaultdict
from datetime import datetime, timezone

from app.articles.processor import get_typesense_client, ensure_collection, COLLECTION_NAME

logger = logging.getLogger(__name__)


def _load_chunk0_metadatas(before: datetime = None, after: datetime = None) -> list[dict]:
    client = get_typesense_client()
    ensure_collection()

    filters = ["chunk_index:0"]
    if before:
        filters.append(f"published_at_ts:<={int(before.timestamp())}")
    if after:
        filters.append(f"published_at_ts:>={int(after.timestamp())}")

    search_params = {
        "q": "*",
        "filter_by": " && ".join(filters),
        "per_page": 250,
        "page": 1,
        "include_fields": "article_id,companies,company_sentiments,company_relevances,"
                          "source_name,published_at",
    }

    results = []
    while True:
        resp = client.collections[COLLECTION_NAME].documents.search(search_params)
        hits = resp.get("hits", [])
        if not hits:
            break
        for hit in hits:
            results.append(hit["document"])
        if len(hits) < 250:
            break
        search_params["page"] += 1

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


def _parse_companies(companies_val) -> list[str]:
    if not companies_val:
        return []
    if isinstance(companies_val, list):
        return [c.strip().upper() for c in companies_val if c.strip()]
    return [c.strip().upper() for c in companies_val.split(",") if c.strip()]


def _parse_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None


def sentiment_score(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    stats = defaultdict(lambda: {"bullish": 0, "bearish": 0, "neutral": 0, "total": 0, "latest_published_at": None})

    for m in metas:
        sentiments = _parse_sentiments(m.get("company_sentiments", ""))
        pub = _parse_timestamp(m.get("published_at", ""))
        for sym, sent in sentiments.items():
            if symbol and sym != symbol.upper():
                continue
            stats[sym]["total"] += 1
            if sent in ("bullish", "bearish", "neutral"):
                stats[sym][sent] += 1
            if pub and (stats[sym]["latest_published_at"] is None or pub > stats[sym]["latest_published_at"]):
                stats[sym]["latest_published_at"] = pub

    result = {}
    for sym, s in stats.items():
        total = s["total"]
        result[sym] = {
            "score": round((s["bullish"] - s["bearish"]) / total, 4) if total else 0,
            "bullish": s["bullish"],
            "bearish": s["bearish"],
            "neutral": s["neutral"],
            "total_mentions": total,
            "latest_published_at": s["latest_published_at"],
        }
    return result


def mention_velocity(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    anchor = before or datetime.now(timezone.utc)

    windows = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
    counts = defaultdict(lambda: {w: 0 for w in windows})
    prev_counts = defaultdict(lambda: {w: 0 for w in windows})
    latest_ts = defaultdict(lambda: None)

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
            if latest_ts[sym] is None or ts > latest_ts[sym]:
                latest_ts[sym] = ts
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
        velocity["latest_published_at"] = latest_ts.get(sym)
        result[sym] = velocity
    return result


def comention_pairs(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    pairs = defaultdict(lambda: {"count": 0, "same_sentiment": 0, "divergent_sentiment": 0, "latest_published_at": None})

    for m in metas:
        sentiments = _parse_sentiments(m.get("company_sentiments", ""))
        pub = _parse_timestamp(m.get("published_at", ""))
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
                if pub and (pairs[pair_key]["latest_published_at"] is None or pub > pairs[pair_key]["latest_published_at"]):
                    pairs[pair_key]["latest_published_at"] = pub

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
            "latest_published_at": data["latest_published_at"],
        }
    return result


def source_breadth(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    metas = _load_chunk0_metadatas(before=before, after=after)
    company_sources = defaultdict(set)
    latest_ts = defaultdict(lambda: None)

    for m in metas:
        companies = _parse_companies(m.get("companies", ""))
        source = m.get("source_name", "")
        pub = _parse_timestamp(m.get("published_at", ""))
        if not source:
            continue

        for sym in companies:
            if symbol and sym != symbol.upper():
                continue
            company_sources[sym].add(source)
            if pub and (latest_ts[sym] is None or pub > latest_ts[sym]):
                latest_ts[sym] = pub

    result = {}
    for sym, sources in company_sources.items():
        result[sym] = {
            "unique_sources": len(sources),
            "sources": sorted(sources),
            "latest_published_at": latest_ts.get(sym),
        }
    return result


def all_indices(symbol: str = None, before: datetime = None, after: datetime = None) -> dict:
    return {
        "sentiment_score": sentiment_score(symbol, before=before, after=after),
        "mention_velocity": mention_velocity(symbol, before=before, after=after),
        "comention_pairs": comention_pairs(symbol, before=before, after=after),
        "source_breadth": source_breadth(symbol, before=before, after=after),
    }
