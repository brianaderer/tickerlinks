import logging
import os
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END

from app.signals.llm_utils import parse_llm_json
from app.signals.research.prompts import PLAN_QUERY_SYSTEM, EVALUATE_SYSTEM

logger = logging.getLogger(__name__)

MAX_DOCUMENTS = 10


class ResearchState(TypedDict, total=False):
    symbol: str
    context: str
    today: str
    queries: list[str]
    documents: list[dict]
    iteration: int
    max_iterations: int
    days_back: int
    done: bool


def _get_llm():
    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return None
    return ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0,
        max_tokens=500,
    )


def _search_typesense(query: str, symbol: str, days_back: int = 7, limit: int = 10) -> list[dict]:
    from app.articles.processor import get_embedding_model, get_typesense_client, ensure_collection, COLLECTION_NAME
    from app.models import NewsArticle

    model = get_embedding_model()
    client = get_typesense_client()
    ensure_collection()

    query_embedding = model.encode([query]).tolist()[0]

    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())

    filters = [f"published_at_ts:>={cutoff_ts}"]
    if symbol:
        filters.append(f"companies:={symbol.upper()}")
    filter_by = " && ".join(filters)

    search_params = {
        "q": "*",
        "vector_query": f"embedding:({query_embedding}, k:{limit * 3})",
        "filter_by": filter_by,
        "per_page": limit * 3,
        "include_fields": "article_id,title,companies,company_sentiments,"
                          "article_summary,source_name,published_at",
    }

    search_req = {"searches": [{"collection": COLLECTION_NAME, **search_params}]}
    multi = client.multi_search.perform(search_req, {})
    results = multi["results"][0] if multi.get("results") else {"hits": []}

    hits = []
    seen = set()
    for hit in results.get("hits", []):
        doc = hit["document"]
        article_id = doc["article_id"]
        if article_id in seen:
            continue
        seen.add(article_id)

        article = NewsArticle.query.get(article_id)
        if not article:
            continue

        hits.append({
            "article_id": article_id,
            "title": article.title or "",
            "full_text": article.full_text or "",
            "summary": article.summary or "",
            "content_source": article.content_source or "unknown",
            "published_at": article.published_at.isoformat() if article.published_at else "",
            "source_name": article.source_name or "",
            "sentiment": doc.get("company_sentiments", ""),
            "distance": hit.get("vector_distance", 0),
        })

        if len(hits) >= limit:
            break

    return hits


def _merge_documents(existing: list[dict], new_hits: list[dict]) -> list[dict]:
    seen_ids = {d["article_id"] for d in existing}
    for hit in new_hits:
        if hit["article_id"] not in seen_ids:
            existing.append(hit)
            seen_ids.add(hit["article_id"])

    existing.sort(key=lambda d: d.get("distance", 999))
    return existing[:MAX_DOCUMENTS]


def plan_query_node(state: ResearchState) -> ResearchState:
    llm = _get_llm()
    if not llm:
        state["queries"] = [f"{state['symbol']} recent news"]
        state["days_back"] = 7
        return state

    prompt = PLAN_QUERY_SYSTEM.format(today=state["today"])
    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"Symbol: {state['symbol']}\nResearch context: {state['context']}"),
    ])

    result = parse_llm_json(response.content)
    if isinstance(result, dict):
        state["queries"] = result.get("queries", [f"{state['symbol']} recent news"])
        state["days_back"] = result.get("days_back", 7)
    else:
        state["queries"] = [f"{state['symbol']} recent news"]
        state["days_back"] = 7

    return state


def search_node(state: ResearchState) -> ResearchState:
    queries = state.get("queries", [])
    days_back = state.get("days_back", 7)
    existing = state.get("documents", [])
    remaining_slots = MAX_DOCUMENTS - len(existing)

    if remaining_slots <= 0:
        return state

    for query in queries:
        hits = _search_typesense(query, state["symbol"], days_back, limit=remaining_slots)
        existing = _merge_documents(existing, hits)
        remaining_slots = MAX_DOCUMENTS - len(existing)
        if remaining_slots <= 0:
            break

    state["documents"] = existing
    return state


def evaluate_node(state: ResearchState) -> ResearchState:
    iteration = state.get("iteration", 0)
    state["iteration"] = iteration + 1

    docs = state.get("documents", [])
    if not docs or iteration >= state.get("max_iterations", 3):
        state["done"] = True
        return state

    llm = _get_llm()
    if not llm:
        state["done"] = True
        return state

    doc_summary = "\n".join(
        f"- [{d['published_at']}] {d['title']} (sentiment: {d['sentiment']})"
        for d in docs
    )
    queries_tried = state.get("queries", [])

    prompt = EVALUATE_SYSTEM.format(today=state["today"])
    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=(
            f"Symbol: {state['symbol']}\n"
            f"Research context: {state['context']}\n"
            f"Queries already tried: {queries_tried}\n\n"
            f"Articles found ({len(docs)}):\n{doc_summary}"
        )),
    ])

    result = parse_llm_json(response.content)
    if isinstance(result, dict) and not result.get("sufficient", True):
        new_queries = result.get("new_queries", [])
        if new_queries:
            state["queries"] = new_queries
            state["days_back"] = result.get("days_back", 14)
            state["done"] = False
            return state

    state["done"] = True
    return state


def should_continue(state: ResearchState) -> str:
    if state.get("done", False):
        return "done"
    return "search"


def build_research_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("plan_query", plan_query_node)
    graph.add_node("search", search_node)
    graph.add_node("evaluate", evaluate_node)

    graph.set_entry_point("plan_query")
    graph.add_edge("plan_query", "search")
    graph.add_edge("search", "evaluate")
    graph.add_conditional_edges("evaluate", should_continue, {
        "search": "search",
        "done": END,
    })

    return graph.compile()


def run_research(symbol: str, context: str) -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    initial_state: ResearchState = {
        "symbol": symbol,
        "context": context,
        "today": today,
        "queries": [],
        "documents": [],
        "iteration": 0,
        "max_iterations": 3,
        "days_back": 7,
        "done": False,
    }

    graph = build_research_graph()
    final_state = graph.invoke(initial_state)

    docs = final_state.get("documents", [])
    logger.info("Research for %s: %d articles assembled over %d iterations",
                symbol, len(docs), final_state.get("iteration", 0))
    return docs


def format_research_results(docs: list[dict]) -> str:
    if not docs:
        return "No articles found."
    parts = []
    for d in docs:
        text = d.get("full_text") or d.get("summary") or "No text available"
        source_tag = "[SUMMARY ONLY] " if d.get("content_source") == "summary" else ""
        parts.append(
            f"{source_tag}[{d['published_at']}] {d['title']} ({d['source_name']})\n"
            f"Sentiment: {d['sentiment']}\n"
            f"{text}"
        )
    return "\n\n---\n\n".join(parts)


@tool
def research_company(symbol: str, context: str) -> str:
    """Search the article database for a company.

    Args:
        symbol: Ticker symbol (e.g. "NVDA")
        context: What to research - signals, themes, questions to answer

    Returns:
        Up to 10 full-text articles with dates and metadata.
    """
    docs = run_research(symbol, context)
    return format_research_results(docs)
