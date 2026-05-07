import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from app.extensions import celery, db
from app.models import Company, PriceHistory

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

INTERVAL = "15m"
CHUNK_DAYS = 55  # Yahoo allows ~60 days max for 15m, use 55 for safety
LOOKBACK_DAYS = 60


@celery.task(name="app.tasks.maintenance.backfill_company")
def backfill_company(company_id: int):
    company = Company.query.get(company_id)
    if not company:
        return {"error": f"Company {company_id} not found"}

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=LOOKBACK_DAYS)

    total_new = 0
    chunk_start = start

    while chunk_start < now:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), now)

        try:
            new_rows = _fetch_chunk(company, chunk_start, chunk_end)
            total_new += new_rows
        except Exception:
            logger.exception("Failed chunk %s for %s", chunk_start.date(), company.symbol)

        chunk_start = chunk_end
        time.sleep(0.3)

    logger.info("Backfill %s: %d new rows", company.symbol, total_new)
    return {"symbol": company.symbol, "new_rows": total_new}


def _fetch_chunk(company: Company, start: datetime, end: datetime) -> int:
    url = YAHOO_CHART_URL.format(symbol=company.symbol)
    params = {
        "period1": int(start.timestamp()),
        "period2": int(end.timestamp()),
        "interval": INTERVAL,
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    chart_result = data.get("chart", {}).get("result")
    if not chart_result:
        return 0

    result = chart_result[0]
    timestamps = result.get("timestamp", [])
    quotes = result.get("indicators", {}).get("quote", [{}])[0]

    if not timestamps:
        return 0

    now = datetime.now(timezone.utc)
    new_count = 0

    for idx, ts_epoch in enumerate(timestamps):
        ts_utc = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)

        close_val = quotes.get("close", [None] * len(timestamps))[idx]
        if close_val is None:
            continue

        existing = PriceHistory.query.filter_by(
            company_id=company.id, timestamp=ts_utc
        ).first()
        if existing:
            continue

        open_val = quotes.get("open", [None] * len(timestamps))[idx]
        high_val = quotes.get("high", [None] * len(timestamps))[idx]
        low_val = quotes.get("low", [None] * len(timestamps))[idx]
        volume_val = quotes.get("volume", [None] * len(timestamps))[idx]

        price = PriceHistory(
            company_id=company.id,
            timestamp=ts_utc,
            open=float(open_val) if open_val else None,
            high=float(high_val) if high_val else None,
            low=float(low_val) if low_val else None,
            close=float(close_val),
            volume=int(volume_val) if volume_val else None,
            dividends=0.0,
            stock_splits=0.0,
            fetched_at=now,
        )
        db.session.add(price)
        new_count += 1

    db.session.commit()
    return new_count


@celery.task(name="app.tasks.maintenance.backfill_all")
def backfill_all():
    companies = Company.query.filter_by(active=True).all()
    logger.info("Queuing backfill for %d companies", len(companies))
    for c in companies:
        backfill_company.apply_async(args=[c.id], queue="backfill")
    return {"queued": len(companies)}


@celery.task(name="app.tasks.maintenance.reprocess_articles")
def reprocess_articles():
    from app.models import NewsArticle
    from app.tasks.articles import process_article

    unprocessed = NewsArticle.query.filter_by(processed=False).all()
    logger.info("Queuing %d articles for reprocessing on backfill queue", len(unprocessed))
    for a in unprocessed:
        process_article.apply_async(args=[a.id], queue="backfill")
    return {"queued": len(unprocessed)}


@celery.task(name="app.tasks.maintenance.reset_and_reprocess_articles")
def reset_and_reprocess_articles():
    from app.models import NewsArticle
    from app.tasks.articles import process_article

    count = NewsArticle.query.update({"processed": False})
    db.session.commit()
    logger.info("Reset %d articles to unprocessed", count)

    articles = NewsArticle.query.all()
    for a in articles:
        process_article.apply_async(args=[a.id], queue="backfill")
    logger.info("Queued %d articles on backfill queue", len(articles))
    return {"reset": count, "queued": len(articles)}
