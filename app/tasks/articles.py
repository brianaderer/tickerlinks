import logging

from app.extensions import celery
from app.articles.processor import process_single_article
from app.sse import sse_publish

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.articles.process_article")
def process_article(article_id: int):
    from app.models import NewsArticle

    logger.info("Processing article %d", article_id)
    result = process_single_article(article_id)
    logger.info("Article %d processed: %s", article_id, result)

    if isinstance(result, dict) and result.get("processed"):
        article = NewsArticle.query.get(article_id)
        title = article.title if article else ""
        companies = list(result.get("companies", {}).keys()) if isinstance(result.get("companies"), dict) else []
        sse_publish("news", "article_processed", {
            "article_id": article_id,
            "title": title,
            "companies": companies,
        })
    return result
