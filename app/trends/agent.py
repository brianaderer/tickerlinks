import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from app.extensions import db
from app.models import TrendSnapshot
from app.signals.llm_utils import parse_llm_json
from app.signals.research import research_company
from app.trends.prompts import ANALYZE_SYSTEM, SYNTHESIZE_SYSTEM

logger = logging.getLogger(__name__)

MAX_RESEARCH_CALLS = 5


class TrendState(TypedDict, total=False):
    today: str
    raw_topics: list[dict]
    trends: list[dict]


def _get_llm(max_tokens: int = 2000):
    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return None
    return ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.3,
        max_tokens=max_tokens,
    )


def _strip_think(text: str) -> str:
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def gather_topics() -> list[dict]:
    from app.articles.processor import get_typesense_client, ensure_collection, COLLECTION_NAME

    client = get_typesense_client()
    ensure_collection()

    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())

    search_params = {
        "q": "*",
        "filter_by": f"chunk_index:0 && published_at_ts:>={cutoff_ts}",
        "per_page": 250,
        "page": 1,
        "include_fields": "article_id,title,topic_threads,companies,published_at,published_at_ts",
    }

    articles = []
    seen = set()

    while True:
        results = client.collections[COLLECTION_NAME].documents.search(search_params)
        hits = results.get("hits", [])
        if not hits:
            break

        for hit in hits:
            doc = hit["document"]
            aid = doc.get("article_id")
            if aid in seen:
                continue
            seen.add(aid)

            topic_str = doc.get("topic_threads", "")
            topics = [t.strip() for t in topic_str.split("||") if t.strip()] if topic_str else []

            companies = doc.get("companies", [])
            if isinstance(companies, str):
                companies = [c.strip() for c in companies.split(",") if c.strip()]

            articles.append({
                "article_id": aid,
                "title": doc.get("title", ""),
                "topics": topics,
                "companies": companies,
                "published_at": doc.get("published_at", ""),
                "published_at_ts": doc.get("published_at_ts", 0),
            })

        if len(hits) < 250:
            break
        search_params["page"] += 1

    articles.sort(key=lambda a: a["published_at_ts"], reverse=True)
    logger.info("Gathered %d articles with topic tags for trending", len(articles))
    return articles


def _format_topic_data(articles: list[dict]) -> str:
    lines = []
    for a in articles[:200]:
        topics = ", ".join(a["topics"][:5]) if a["topics"] else "none"
        companies = ", ".join(a["companies"][:5]) if a["companies"] else "none"
        lines.append(
            f"[{a['published_at'][:10]}] (id:{a['article_id']}) {a['title'][:120]}\n"
            f"  Topics: {topics} | Companies: {companies}"
        )
    return "\n".join(lines)


def analyze_trends(articles: list[dict], today: str) -> list[dict]:
    llm = _get_llm(max_tokens=3000)
    if not llm:
        logger.warning("No LLM configured, skipping trend analysis")
        return []

    llm_with_tools = llm.bind_tools([research_company])
    topic_data = _format_topic_data(articles)

    messages = [
        SystemMessage(content=ANALYZE_SYSTEM.format(today=today)),
        HumanMessage(content=(
            f"Here are {len(articles)} articles from the last 7 days with their topic tags:\n\n"
            f"{topic_data}\n\n"
            f"Identify the 10 most significant trends. Use the research_company tool "
            f"to dig deeper on the most impactful topics (up to 5 calls)."
        )),
    ]

    research_calls = 0
    for _ in range(MAX_RESEARCH_CALLS + 1):
        response = llm_with_tools.invoke(messages)
        if not response.tool_calls or research_calls >= MAX_RESEARCH_CALLS:
            break
        messages.append(response)
        for tc in response.tool_calls:
            if research_calls >= MAX_RESEARCH_CALLS:
                messages.append(ToolMessage(
                    content="Research call limit reached.",
                    tool_call_id=tc["id"],
                ))
                continue
            logger.info("Trending research call: %s", tc["args"])
            result = research_company.invoke(tc["args"])
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
            research_calls += 1

    text = _strip_think(response.content)
    parsed = parse_llm_json(text)
    if not parsed:
        logger.error("Failed to parse trend analysis output")
        return []

    return parsed.get("trends", [])


def synthesize_trends(candidates: list[dict], articles: list[dict], today: str) -> list[dict]:
    llm = _get_llm(max_tokens=2000)
    if not llm:
        return candidates

    article_map = {a["article_id"]: a for a in articles}

    candidates_text = ""
    for t in candidates[:10]:
        aids = t.get("article_ids", [])[:10]
        article_titles = []
        for aid in aids:
            a = article_map.get(aid)
            if a:
                article_titles.append(f"[{a['published_at'][:10]}] {a['title'][:100]}")

        candidates_text += (
            f"Rank {t.get('rank', '?')}: {t.get('headline', 'No headline')}\n"
            f"  Tags: {', '.join(t.get('top_tags', []))}\n"
            f"  Companies: {', '.join(t.get('companies', []))}\n"
            f"  Span: {t.get('first_seen', '?')} to {t.get('latest', '?')}\n"
            f"  Articles ({len(aids)}):\n"
        )
        for title in article_titles[:5]:
            candidates_text += f"    - {title}\n"
        candidates_text += "\n"

    messages = [
        SystemMessage(content=SYNTHESIZE_SYSTEM.format(today=today)),
        HumanMessage(content=f"Write impact statements for these 10 trends:\n\n{candidates_text}"),
    ]

    response = llm.invoke(messages)
    text = _strip_think(response.content)
    parsed = parse_llm_json(text)

    if not parsed:
        logger.error("Failed to parse synthesis output")
        return candidates

    synthesis = parsed if isinstance(parsed, list) else parsed.get("trends", parsed.get("results", []))

    synthesis_map = {}
    for s in synthesis:
        rank = s.get("rank")
        if rank is not None:
            synthesis_map[rank] = s

    final = []
    for t in candidates[:10]:
        rank = t.get("rank")
        s = synthesis_map.get(rank, {})
        final.append({
            "rank": rank,
            "headline": s.get("headline", t.get("headline", "")),
            "impact": s.get("impact", ""),
            "top_tags": t.get("top_tags", []),
            "article_ids": t.get("article_ids", [])[:10],
            "companies": t.get("companies", []),
            "first_seen": t.get("first_seen", ""),
            "latest": t.get("latest", ""),
        })

    return final


def run_trending_agent() -> TrendSnapshot:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    articles = gather_topics()
    if not articles:
        logger.info("No articles found for trending analysis")
        snapshot = _upsert_snapshot([], datetime.now(timezone.utc))
        return snapshot

    candidates = analyze_trends(articles, today)
    if not candidates:
        logger.info("No trend candidates identified")
        snapshot = _upsert_snapshot([], datetime.now(timezone.utc))
        return snapshot

    trends = synthesize_trends(candidates, articles, today)

    now = datetime.now(timezone.utc)
    snapshot = _upsert_snapshot(trends, now)
    logger.info("Trending: %d trends generated", len(trends))
    return snapshot


def _upsert_snapshot(trends: list[dict], now: datetime) -> TrendSnapshot:
    existing = TrendSnapshot.query.order_by(TrendSnapshot.generated_at.desc()).first()
    if existing:
        existing.generated_at = now
        existing.trends = trends
        db.session.commit()
        return existing

    snapshot = TrendSnapshot(generated_at=now, trends=trends)
    db.session.add(snapshot)
    db.session.commit()
    return snapshot
