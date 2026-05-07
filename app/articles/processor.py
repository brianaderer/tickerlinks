import logging
import os
import re
from typing import Optional

import requests
import typesense
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

from app.extensions import db
from app.models import NewsArticle, Company
from app.models.article import article_companies
from app.articles.ticker_matcher import match_tickers
from app.articles.summarizer import summarize_article

logger = logging.getLogger(__name__)

_embedding_model = None
_typesense_client = None

COLLECTION_NAME = "article_chunks"

COLLECTION_SCHEMA = {
    "name": COLLECTION_NAME,
    "fields": [
        {"name": "article_id", "type": "int32"},
        {"name": "chunk_index", "type": "int32"},
        {"name": "title", "type": "string", "optional": True},
        {"name": "document", "type": "string"},
        {"name": "companies", "type": "string[]", "optional": True, "facet": True},
        {"name": "company_sentiments", "type": "string", "optional": True},
        {"name": "company_relevances", "type": "string", "optional": True},
        {"name": "article_summary", "type": "string", "optional": True},
        {"name": "topic_threads", "type": "string", "optional": True},
        {"name": "source_name", "type": "string", "optional": True, "facet": True},
        {"name": "published_at_ts", "type": "int64", "optional": True, "sort": True},
        {"name": "published_at", "type": "string", "optional": True},
        {"name": "embedding", "type": "float[]", "num_dim": 384},
    ],
}


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def get_typesense_client():
    global _typesense_client
    if _typesense_client is None:
        host = os.environ.get("TYPESENSE_HOST", "typesense")
        port = os.environ.get("TYPESENSE_PORT", "8108")
        api_key = os.environ.get("TYPESENSE_API_KEY", "stocklynx-typesense-key")
        _typesense_client = typesense.Client({
            "nodes": [{"host": host, "port": port, "protocol": "http"}],
            "api_key": api_key,
            "connection_timeout_seconds": 10,
        })
    return _typesense_client


def ensure_collection():
    client = get_typesense_client()
    try:
        client.collections[COLLECTION_NAME].retrieve()
    except typesense.exceptions.ObjectNotFound:
        client.collections.create(COLLECTION_SCHEMA)
        logger.info("Created Typesense collection '%s'", COLLECTION_NAME)


def process_single_article(article_id: int) -> dict:
    article = NewsArticle.query.get(article_id)
    if not article:
        return {"error": f"Article {article_id} not found"}
    if article.processed:
        return {"skipped": True, "article_id": article_id}

    try:
        companies = _process_article(article)
        article.processed = True
        db.session.commit()
        return {"processed": True, "article_id": article_id, "companies": companies}
    except Exception:
        logger.exception("Failed to process article %d: %s", article.id, article.title[:60])
        return {"error": str(article_id)}


BOT_CHECK_PHRASES = [
    "cloudflare", "security verification", "checking your browser",
    "captcha", "are you a robot", "verify you are human",
    "just a moment", "enable javascript and cookies",
    "access denied", "403 forbidden", "please enable cookies",
]


def _is_bot_check(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in BOT_CHECK_PHRASES)


def _process_article(article: NewsArticle):
    title = article.title or ""
    summary = article.summary or ""

    # Try to scrape full text if we don't have it or existing text is a bot page
    if not article.full_text or _is_bot_check(article.full_text):
        scraped = _scrape_full_text(article.url)
        if scraped and not _is_bot_check(scraped):
            article.full_text = scraped
            article.content_source = "scraped"
        else:
            article.full_text = None
            article.content_source = None

    if article.full_text and not article.content_source:
        article.content_source = "scraped"

    # Fall back to RSS summary if scraping failed
    if not article.full_text and summary and len(summary) > 50:
        article.full_text = summary
        article.content_source = "summary"

    # If we have neither, skip this article entirely
    if not article.full_text:
        logger.info("Dropping article %d — no usable content: %s", article.id, title[:60])
        article.content_source = None
        return {}

    full_text = article.full_text
    companies = match_tickers(title, summary, full_text or "")

    db.session.execute(article_companies.delete().where(
        article_companies.c.article_id == article.id))
    for sym, meta in companies.items():
        comp = Company.query.filter_by(symbol=sym).first()
        if comp:
            db.session.execute(article_companies.insert().values(
                article_id=article.id,
                company_id=comp.id,
                sentiment=meta.get("sentiment", "neutral"),
                relevance=meta.get("relevance", "secondary"),
            ))

    summary_result = summarize_article(title, summary, full_text)

    tags = {
        "companies": companies,
        "article_summary": summary_result.get("summary", ""),
        "topic_threads": summary_result.get("topics", []),
    }

    chunks = _chunk_text(article)
    if not chunks:
        return companies

    _embed_and_store(article, chunks, tags)
    return companies


def _scrape_full_text(url: str) -> Optional[str]:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        article_tag = soup.find("article") or soup.find("div", class_=re.compile(r"article|content|body", re.I))
        if article_tag:
            paragraphs = article_tag.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        text = "\n\n".join(p.get_text(separator=" ", strip=True) for p in paragraphs if len(p.get_text(separator=" ", strip=True)) > 30)
        if len(text) < 100:
            return None
        if _is_bot_check(text):
            return None
        return text
    except Exception:
        logger.debug("Failed to scrape %s", url)
        return None


def _chunk_text(article: NewsArticle) -> list[str]:
    text = article.full_text or article.summary or ""
    if not text or len(text) < 50:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]

    if not paragraphs:
        paragraphs = [text[i:i+500] for i in range(0, len(text), 450)]

    return paragraphs


def _embed_and_store(article: NewsArticle, chunks: list[str], tags: dict):
    model = get_embedding_model()
    client = get_typesense_client()
    ensure_collection()

    embeddings = model.encode(chunks).tolist()

    companies = tags.get("companies", {})
    company_tickers = list(companies.keys()) if companies else []
    company_sentiments = ",".join(
        f"{sym}:{info.get('sentiment', 'neutral')}" for sym, info in companies.items()
    ) if companies else ""
    company_relevances = ",".join(
        f"{sym}:{info.get('relevance', 'primary')}" for sym, info in companies.items()
    ) if companies else ""

    for i, chunk in enumerate(chunks):
        doc_id = f"article_{article.id}_chunk_{i}"
        doc = {
            "id": doc_id,
            "article_id": article.id,
            "chunk_index": i,
            "title": (article.title or "")[:200],
            "document": chunk,
            "companies": company_tickers,
            "company_sentiments": company_sentiments,
            "company_relevances": company_relevances,
            "article_summary": tags.get("article_summary", ""),
            "topic_threads": " || ".join(tags.get("topic_threads", [])),
            "source_name": article.source_name or "",
            "published_at_ts": int(article.published_at.timestamp()) if article.published_at else 0,
            "published_at": article.published_at.isoformat() if article.published_at else "",
            "embedding": embeddings[i],
        }
        client.collections[COLLECTION_NAME].documents.upsert(doc)

    logger.debug("Stored %d chunks for article %d", len(chunks), article.id)


SENTIMENT_WINDOW_DAYS = 7
SENTIMENT_DECAY_LAMBDA = 0.3


def get_sentiment_index(symbol: str = None, limit: int = 50) -> list[dict]:
    import math
    from datetime import datetime, timedelta, timezone

    client = get_typesense_client()
    ensure_collection()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=SENTIMENT_WINDOW_DAYS)
    cutoff_ts = int(cutoff.timestamp())

    search_params = {
        "q": "*",
        "filter_by": f"chunk_index:0 && published_at_ts:>={cutoff_ts}",
        "per_page": 250,
        "page": 1,
        "include_fields": "article_id,company_sentiments,company_relevances,published_at_ts",
    }

    company_stats = {}
    seen_articles = {}

    while True:
        results = client.collections[COLLECTION_NAME].documents.search(search_params)
        hits = results.get("hits", [])
        if not hits:
            break

        for hit in hits:
            meta = hit["document"]
            article_id = meta.get("article_id")
            sentiments_str = meta.get("company_sentiments", "")
            pub_ts = meta.get("published_at_ts", 0)

            if not sentiments_str:
                continue

            age_days = (now.timestamp() - pub_ts) / 86400 if pub_ts else SENTIMENT_WINDOW_DAYS
            weight = math.exp(-SENTIMENT_DECAY_LAMBDA * age_days)

            sentiments = {}
            for pair in sentiments_str.split(","):
                if ":" in pair:
                    sym, sent = pair.split(":", 1)
                    sentiments[sym.strip()] = sent.strip()

            relevances_str = meta.get("company_relevances", "")
            relevances = {}
            for pair in relevances_str.split(","):
                if ":" in pair:
                    sym, rel = pair.split(":", 1)
                    relevances[sym.strip()] = rel.strip()

            for sym, sentiment in sentiments.items():
                if symbol and sym.upper() != symbol.upper():
                    continue

                article_key = f"{article_id}_{sym}"
                if article_key in seen_articles:
                    continue
                seen_articles[article_key] = True

                if sym not in company_stats:
                    company_stats[sym] = {
                        "symbol": sym,
                        "total_mentions": 0,
                        "weighted_mentions": 0.0,
                        "primary_mentions": 0,
                        "bullish": 0.0,
                        "bearish": 0.0,
                        "neutral": 0.0,
                        "sentiment_score": 0.0,
                    }

                stats = company_stats[sym]
                stats["total_mentions"] += 1
                stats["weighted_mentions"] += weight
                if relevances.get(sym) == "primary":
                    stats["primary_mentions"] += 1

                if sentiment == "bullish":
                    stats["bullish"] += weight
                elif sentiment == "bearish":
                    stats["bearish"] += weight
                elif sentiment == "neutral":
                    stats["neutral"] += weight

        if len(hits) < 250:
            break
        search_params["page"] += 1

    for sym, stats in company_stats.items():
        total_w = stats["weighted_mentions"]
        if total_w > 0:
            stats["sentiment_score"] = round(
                (stats["bullish"] - stats["bearish"]) / total_w, 4
            )
        stats["bullish"] = round(stats["bullish"], 3)
        stats["bearish"] = round(stats["bearish"], 3)
        stats["neutral"] = round(stats["neutral"], 3)
        stats["weighted_mentions"] = round(stats["weighted_mentions"], 3)

    results = sorted(company_stats.values(), key=lambda x: x["weighted_mentions"], reverse=True)

    if not symbol:
        results = results[:limit]

    return results


def search_articles(query: str, n_results: int = 10, company: str = None) -> list[dict]:
    model = get_embedding_model()
    client = get_typesense_client()
    ensure_collection()

    query_embedding = model.encode([query]).tolist()[0]

    search_params = {
        "q": "*",
        "vector_query": f"embedding:({query_embedding}, k:{n_results * 3})",
        "per_page": n_results * 3,
        "include_fields": "article_id,document,title,companies,company_sentiments,"
                          "article_summary,topic_threads,source_name,published_at",
    }

    if company:
        search_params["filter_by"] = f"companies:={company.upper()}"

    search_req = {"searches": [{"collection": COLLECTION_NAME, **search_params}]}
    multi = client.multi_search.perform(search_req, {})
    results = multi["results"][0] if multi.get("results") else {"hits": []}

    hits = []
    seen_articles = set()
    for hit in results.get("hits", []):
        doc = hit["document"]
        article_id = doc["article_id"]

        if article_id in seen_articles:
            continue
        seen_articles.add(article_id)

        vector_distance = hit.get("vector_distance", 0)

        hits.append({
            "article_id": article_id,
            "chunk": doc.get("document", ""),
            "title": doc.get("title", ""),
            "companies": ",".join(doc.get("companies", [])),
            "company_sentiments": doc.get("company_sentiments", ""),
            "article_summary": doc.get("article_summary", ""),
            "topic_threads": doc.get("topic_threads", ""),
            "source_name": doc.get("source_name", ""),
            "published_at": doc.get("published_at", ""),
            "distance": vector_distance,
        })

        if len(hits) >= n_results:
            break

    return hits
