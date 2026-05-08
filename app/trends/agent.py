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
from app.signals.research.agent import run_research

from langchain_core.tools import tool


@tool
def research_company_brief(symbol: str, context: str) -> str:
    """Search the article database for a company. Returns summaries only.

    Args:
        symbol: Ticker symbol (e.g. "NVDA")
        context: What to research - signals, themes, questions to answer

    Returns:
        Up to 10 article summaries with dates and metadata.
    """
    docs = run_research(symbol, context)
    if not docs:
        return "No articles found."
    parts = []
    for d in docs:
        text = d.get("summary") or d.get("title") or "No summary"
        parts.append(
            f"[{d['published_at']}] {d['title']} ({d['source_name']})\n"
            f"Sentiment: {d['sentiment']}\n{text}"
        )
    return "\n\n---\n\n".join(parts)
from app.trends.prompts import ANALYZE_SYSTEM, SYNTHESIZE_SYSTEM

logger = logging.getLogger(__name__)

MAX_RESEARCH_CALLS = 2


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

    # Filter to full-text articles only (exclude summary-only)
    from app.models import NewsArticle as NA
    scraped_ids = set(
        row[0] for row in
        NA.query.with_entities(NA.id)
        .filter(NA.id.in_([a["article_id"] for a in articles]), NA.content_source == "scraped")
        .all()
    )
    articles = [a for a in articles if a["article_id"] in scraped_ids]

    logger.info("Gathered %d full-text articles with topic tags for trending", len(articles))
    return articles


def _format_topic_data(articles: list[dict]) -> str:
    lines = []
    for a in articles[:100]:
        topics = ", ".join(a["topics"][:5]) if a["topics"] else "none"
        companies = ", ".join(a["companies"][:5]) if a["companies"] else "none"
        lines.append(
            f"[{a['published_at'][:10]}] (id:{a['article_id']}) {a['title'][:120]}\n"
            f"  Topics: {topics} | Companies: {companies}"
        )
    return "\n".join(lines)


def analyze_trends(articles: list[dict], today: str) -> list[dict]:
    llm = _get_llm(max_tokens=2000)
    if not llm:
        logger.warning("No LLM configured, skipping trend analysis")
        return []

    llm_with_tools = llm.bind_tools([research_company_brief])
    topic_data = _format_topic_data(articles)

    messages = [
        SystemMessage(content=ANALYZE_SYSTEM.format(today=today)),
        HumanMessage(content=(
            f"Here are the {min(len(articles), 100)} most recent articles from the last 7 days:\n\n"
            f"{topic_data}\n\n"
            f"Identify the 10 most significant trends. You may use the research_company tool "
            f"up to {MAX_RESEARCH_CALLS} times if needed. /no_think"
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
            result = research_company_brief.invoke(tc["args"])
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
        HumanMessage(content=f"Write impact statements for these 10 trends:\n\n{candidates_text}\n/no_think"),
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


SIMILARITY_THRESHOLD = 0.80
MAX_DEDUP_ROUNDS = 2

MERGE_PROMPT = """You previously generated these trends, but some are too similar to each other. The following groups were flagged as near-duplicates by cosine similarity on their headlines:

{groups}

MERGE each group into a single consolidated trend. Keep the strongest headline, combine article_ids, union the companies and tags. Then fill the freed slots with NEW trends from the article corpus that cover DIFFERENT sectors or themes.

Return the full set of 10 trends in the same JSON format:
{{
    "trends": [...]
}}
/no_think"""


def _dedup_trends(candidates: list[dict], articles: list[dict], today: str) -> list[dict]:
    from app.articles.processor import get_embedding_model
    import numpy as np

    headlines = [t.get("headline", "") for t in candidates]
    if len(headlines) < 2:
        return candidates

    model = get_embedding_model()
    embeddings = model.encode(headlines)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms
    sim_matrix = normalized @ normalized.T

    groups = []
    used = set()
    for i in range(len(candidates)):
        if i in used:
            continue
        group = [i]
        for j in range(i + 1, len(candidates)):
            if j in used:
                continue
            if sim_matrix[i][j] >= SIMILARITY_THRESHOLD:
                group.append(j)
                used.add(j)
        if len(group) > 1:
            groups.append(group)
            used.update(group)

    if not groups:
        logger.info("Dedup: no similar trends found (threshold=%.2f)", SIMILARITY_THRESHOLD)
        return candidates

    group_text = ""
    for g in groups:
        items = [f"  Rank {candidates[i].get('rank','?')}: {candidates[i].get('headline','')}" for i in g]
        sims = [f"{sim_matrix[g[0]][j]:.2f}" for j in g[1:]]
        group_text += f"GROUP (similarities: {', '.join(sims)}):\n" + "\n".join(items) + "\n\n"

    logger.info("Dedup: found %d groups of similar trends, sending back for merge", len(groups))

    llm = _get_llm(max_tokens=2000)
    if not llm:
        return candidates

    topic_data = _format_topic_data(articles)
    messages = [
        SystemMessage(content=ANALYZE_SYSTEM.format(today=today)),
        HumanMessage(content=(
            f"Article corpus ({min(len(articles), 100)} articles):\n{topic_data}\n\n"
            + MERGE_PROMPT.format(groups=group_text)
        )),
    ]

    response = llm.invoke(messages)
    text = _strip_think(response.content)
    parsed = parse_llm_json(text)
    if parsed and parsed.get("trends"):
        return parsed["trends"]

    return candidates


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

    for rnd in range(MAX_DEDUP_ROUNDS):
        deduped = _dedup_trends(candidates, articles, today)
        if deduped is candidates:
            break
        candidates = deduped
        logger.info("Dedup round %d complete, %d trends", rnd + 1, len(candidates))

    trends = synthesize_trends(candidates, articles, today)
    trends = _resolve_article_ids(trends)

    now = datetime.now(timezone.utc)
    snapshot = _upsert_snapshot(trends, now)
    logger.info("Trending: %d trends generated", len(trends))
    return snapshot


def _resolve_article_ids(trends: list[dict]) -> list[dict]:
    """Replace LLM-picked article IDs with actual Typesense search results per trend."""
    from app.articles.processor import get_typesense_client, ensure_collection, COLLECTION_NAME
    from app.models import NewsArticle

    client = get_typesense_client()
    ensure_collection()

    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    scraped_ids = set(
        row[0] for row in
        NewsArticle.query.with_entities(NewsArticle.id)
        .filter(NewsArticle.content_source == "scraped")
        .all()
    )

    for t in trends:
        queries = []
        for tag in t.get("top_tags", [])[:4]:
            queries.append(tag)
        if t.get("companies"):
            from app.models import Company
            for sym in t["companies"][:3]:
                comp = Company.query.filter_by(symbol=sym).first()
                queries.append(f"{comp.name} {sym}" if comp else sym)
        if not queries:
            queries.append(t.get("headline", "")[:80])

        seen = set()
        aids = []
        try:
            for q in queries:
                if len(aids) >= 10:
                    break
                results = client.collections[COLLECTION_NAME].documents.search({
                    "q": q,
                    "query_by": "title,document",
                    "filter_by": f"chunk_index:0 && published_at_ts:>={cutoff_ts}",
                    "per_page": 15,
                    "sort_by": "_text_match:desc",
                })
                for hit in results.get("hits", []):
                    aid = hit["document"].get("article_id")
                    if aid and aid not in seen and aid in scraped_ids:
                        seen.add(aid)
                        aids.append(aid)
                    if len(aids) >= 10:
                        break
            t["article_ids"] = aids
            logger.debug("Trend '%s': resolved %d article IDs", t.get("headline", "")[:40], len(aids))
        except Exception:
            logger.exception("Failed to resolve articles for trend: %s", t.get("headline", "")[:40])

    return trends


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
