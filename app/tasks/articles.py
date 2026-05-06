import logging

from app.extensions import celery
from app.articles.processor import process_single_article

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.articles.process_article")
def process_article(article_id: int):
    logger.info("Processing article %d", article_id)
    result = process_single_article(article_id)
    logger.info("Article %d processed: %s", article_id, result)
    return result
