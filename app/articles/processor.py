import logging
import os
import re
from typing import Optional

import chromadb
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

from app.extensions import db
from app.models import NewsArticle
from app.articles.ticker_matcher import match_tickers
from app.articles.summarizer import summarize_article

logger = logging.getLogger(__name__)

_embedding_model = None
_chroma_collection = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def get_chroma_collection():
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


def process_single_article(article_id: int) -> dict:
    article = NewsArticle.query.get(article_id)
    if not article:
        return {"error": f"Article {article_id} not found"}
    if article.processed:
        return {"skipped": True, "article_id": article_id}

    try:
        _process_article(article)
        article.processed = True
        db.session.commit()
        return {"processed": True, "article_id": article_id}
    except Exception:
        logger.exception("Failed to process article %d: %s", article.id, article.title[:60])
        return {"error": str(article_id)}


def _process_article(article: NewsArticle):
    title = article.title or ""
    summary = article.summary or ""

    if not article.full_text:
        article.full_text = _scrape_full_text(article.url)
    full_text = article.full_text or ""

    companies = match_tickers(title, summary)

    summary_result = summarize_article(title, summary, full_text)

    tags = {
        "companies": companies,
        "article_summary": summary_result.get("summary", ""),
        "topic_threads": summary_result.get("topics", []),
    }

    chunks = _chunk_text(article)
    if not chunks:
        return

    _embed_and_store(article, chunks, tags)


def _scrape_full_text(url: str) -> Optional[str]:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
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

        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
        return text if len(text) > 100 else None
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
    collection = get_chroma_collection()

    embeddings = model.encode(chunks).tolist()

    ids = [f"article_{article.id}_chunk_{i}" for i in range(len(chunks))]

    existing = collection.get(ids=ids)
    if existing and existing["ids"]:
        collection.delete(ids=existing["ids"])

    companies = tags.get("companies", {})
    company_tickers = ",".join(companies.keys()) if companies else ""
    company_sentiments = ",".join(
        f"{sym}:{info.get('sentiment', 'neutral')}" for sym, info in companies.items()
    ) if companies else ""
    company_relevances = ",".join(
        f"{sym}:{info.get('relevance', 'primary')}" for sym, info in companies.items()
    ) if companies else ""

    metadatas = [
        {
            "article_id": article.id,
            "chunk_index": i,
            "title": (article.title or "")[:200],
            "companies": company_tickers,
            "company_sentiments": company_sentiments,
            "company_relevances": company_relevances,
            "article_summary": tags.get("article_summary", ""),
            "topic_threads": " || ".join(tags.get("topic_threads", [])),
            "source_name": article.source_name or "",
            "published_at": article.published_at.isoformat() if article.published_at else "",
        }
        for i in range(len(chunks))
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.debug("Stored %d chunks for article %d", len(chunks), article.id)


def get_sentiment_index(symbol: str = None, limit: int = 50) -> list[dict]:
    collection = get_chroma_collection()

    all_docs = collection.get(
        include=["metadatas"],
        limit=10000,
    )

    company_stats = {}
    seen_articles = {}

    for meta in all_docs["metadatas"]:
        article_id = meta.get("article_id")
        chunk_index = meta.get("chunk_index", 0)
        if chunk_index != 0:
            continue

        sentiments_str = meta.get("company_sentiments", "")
        relevances_str = meta.get("company_relevances", "")
        published = meta.get("published_at", "")

        if not sentiments_str:
            continue

        sentiments = {}
        for pair in sentiments_str.split(","):
            if ":" in pair:
                sym, sent = pair.split(":", 1)
                sentiments[sym.strip()] = sent.strip()

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
                    "primary_mentions": 0,
                    "bullish": 0,
                    "bearish": 0,
                    "neutral": 0,
                    "sentiment_score": 0.0,
                }

            stats = company_stats[sym]
            stats["total_mentions"] += 1
            if relevances.get(sym) == "primary":
                stats["primary_mentions"] += 1

            if sentiment in ("bullish", "bearish", "neutral"):
                stats[sentiment] += 1

    for sym, stats in company_stats.items():
        total = stats["total_mentions"]
        if total > 0:
            stats["sentiment_score"] = round(
                (stats["bullish"] - stats["bearish"]) / total, 3
            )

    results = sorted(company_stats.values(), key=lambda x: x["total_mentions"], reverse=True)

    if not symbol:
        results = results[:limit]

    return results


def search_articles(query: str, n_results: int = 10, company: str = None) -> list[dict]:
    model = get_embedding_model()
    collection = get_chroma_collection()

    query_embedding = model.encode([query]).tolist()

    where = None
    if company:
        where = {"companies": {"$contains": company.upper()}}

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    seen_articles = set()
    for i, doc_id in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i]
        article_id = meta["article_id"]

        if article_id in seen_articles:
            continue
        seen_articles.add(article_id)

        hits.append({
            "article_id": article_id,
            "chunk": results["documents"][0][i],
            "title": meta.get("title", ""),
            "companies": meta.get("companies", ""),
            "company_sentiments": meta.get("company_sentiments", ""),
            "article_summary": meta.get("article_summary", ""),
            "topic_threads": meta.get("topic_threads", ""),
            "source_name": meta.get("source_name", ""),
            "published_at": meta.get("published_at", ""),
            "distance": results["distances"][0][i],
        })

    return hits
