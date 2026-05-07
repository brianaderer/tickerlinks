import logging

from app.extensions import celery
from app.models import Company
from app.sources.market import MarketFetcher
from app.sources.news import NewsFetcher
from app.sources.edgar import EdgarFetcher
from app.sources.fundamentals import FundamentalsFetcher

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.fetch.fetch_market_data")
def fetch_market_data():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    hour_utc = now.hour
    # 4am-8pm ET = 08:00-00:00 UTC
    if hour_utc >= 0 and hour_utc < 8:
        logger.info("Outside trading hours (UTC %d), skipping market fetch", hour_utc)
        return {"rows_fetched": 0, "skipped": True}

    logger.info("Starting market data fetch (15m)")
    fetcher = MarketFetcher(period="1d", interval="15m")
    results = fetcher.fetch()
    logger.info("Market fetch complete: %d rows", len(results))
    return {"rows_fetched": len(results)}


@celery.task(name="app.tasks.fetch.fetch_insider_trades")
def fetch_insider_trades():
    logger.info("Starting EDGAR insider trades fetch")
    fetcher = EdgarFetcher()
    results = fetcher.fetch(delay=1.0)
    logger.info("EDGAR fetch complete: %d trades", len(results))
    return {"trades_fetched": len(results)}


@celery.task(name="app.tasks.fetch.fetch_fundamentals")
def fetch_fundamentals():
    logger.info("Starting fundamentals fetch")
    fetcher = FundamentalsFetcher()
    results = fetcher.fetch(delay=0.5)
    logger.info("Fundamentals fetch complete: %d snapshots", len(results))
    return {"snapshots_fetched": len(results)}


@celery.task(name="app.tasks.fetch.fetch_news")
def fetch_news():
    logger.info("Starting news fetch")
    fetcher = NewsFetcher()
    results = fetcher.fetch()
    logger.info("News fetch complete: %d articles", len(results))
    return {"articles_fetched": len(results)}


@celery.task(name="app.tasks.fetch.backfill_market_data")
def backfill_market_data():
    import time

    logger.info("Starting 3-month backfill")

    companies = Company.query.filter_by(active=True).all()
    for i, company in enumerate(companies):
        logger.info("Syncing company info for %s", company.symbol)
        MarketFetcher.sync_company_info(company.symbol)
        if i < len(companies) - 1:
            time.sleep(5)

    fetcher = MarketFetcher(period="3mo", interval="1h")
    results = fetcher.fetch(delay=5.0)
    logger.info("Backfill complete: %d total rows", len(results))
    return {"rows_fetched": len(results)}
