import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from app.extensions import db
from app.models import FeedSource, NewsArticle
from app.sources.base import BaseFetcher

logger = logging.getLogger(__name__)


class NewsFetcher(BaseFetcher):
    def fetch(self, feed_source_ids: list[int] | None = None) -> list[dict]:
        if feed_source_ids:
            sources = FeedSource.query.filter(
                FeedSource.id.in_(feed_source_ids), FeedSource.active.is_(True)
            ).all()
        else:
            sources = FeedSource.query.filter_by(active=True).all()

        results = []
        for source in sources:
            try:
                articles = self._fetch_feed(source)
                results.extend(articles)
            except Exception:
                logger.exception("Failed to fetch feed: %s", source.name)
        return results

    def _fetch_feed(self, source: FeedSource) -> list[dict]:
        feed = feedparser.parse(source.url)
        now = datetime.now(timezone.utc)
        articles = []
        for entry in feed.entries:
            url = entry.get("link", "")
            if not url:
                continue

            existing = NewsArticle.query.filter_by(url=url).first()
            if existing:
                continue

            published_at = self._parse_date(entry.get("published"))
            title = entry.get("title", "")
            summary = entry.get("summary", "")

            source_name = None
            entry_source = entry.get("source")
            if isinstance(entry_source, dict):
                source_name = entry_source.get("title")

            article = NewsArticle(
                feed_source_id=source.id,
                title=title,
                summary=self._clean_html(summary),
                url=url,
                author=entry.get("author"),
                source_name=source_name or source.name,
                published_at=published_at,
                fetched_at=now,
            )
            db.session.add(article)
            db.session.flush()

            articles.append({
                "id": article.id,
                "title": title[:100],
                "source": source.name,
            })

        source.last_polled = now
        db.session.commit()

        from app.tasks.articles import process_article
        for a in articles:
            process_article.delay(a["id"])

        logger.info("Stored %d new articles from %s (queued for processing)", len(articles), source.name)
        return articles

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str).astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _clean_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()
