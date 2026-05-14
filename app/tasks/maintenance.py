import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from sqlalchemy import text

from app.extensions import celery, db
from app.models import Company, PriceHistory
from app.signals.llm_utils import sanitize_reasoning_text
from app.tasks.runtime import acquire_lock, release_lock, mark_heartbeat

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


DEDUPE_CTE_SQL = """
WITH ranked AS (
    SELECT
        id,
        FIRST_VALUE(id) OVER (
            PARTITION BY company_id, signal_id, direction, source_at
            ORDER BY detected_at DESC, id DESC
        ) AS keep_id,
        ROW_NUMBER() OVER (
            PARTITION BY company_id, signal_id, direction, source_at
            ORDER BY detected_at DESC, id DESC
        ) AS rn
    FROM signal_matches
),
dupes AS (
    SELECT id, keep_id
    FROM ranked
    WHERE rn > 1
)
"""

ARTICLE_DETECTOR_NAMES = {
    "article_sentiment",
    "mention_velocity",
    "comention",
    "source_breadth",
}


@celery.task(name="app.tasks.maintenance.dedupe_signal_matches")
def dedupe_signal_matches():
    db.session.execute(text("UPDATE signal_matches SET source_at = detected_at WHERE source_at IS NULL"))

    db.session.execute(text(
        DEDUPE_CTE_SQL
        + """
INSERT INTO prediction_match (prediction_id, signal_match_id)
SELECT pm.prediction_id, d.keep_id
FROM prediction_match pm
JOIN dupes d ON d.id = pm.signal_match_id
ON CONFLICT DO NOTHING
"""
    ))

    deleted_links = db.session.execute(text(
        DEDUPE_CTE_SQL
        + """
DELETE FROM prediction_match pm
USING dupes d
WHERE pm.signal_match_id = d.id
"""
    )).rowcount

    deleted_matches = db.session.execute(text(
        DEDUPE_CTE_SQL
        + """
DELETE FROM signal_matches sm
USING dupes d
WHERE sm.id = d.id
"""
    )).rowcount

    db.session.commit()
    logger.info(
        "Signal match dedupe complete: deleted_links=%s deleted_matches=%s",
        deleted_links, deleted_matches,
    )
    return {
        "deleted_prediction_links": max(deleted_links or 0, 0),
        "deleted_signal_matches": max(deleted_matches or 0, 0),
    }


@celery.task(name="app.tasks.maintenance.clean_prediction_reasoning")
def clean_prediction_reasoning():
    from app.models import Prediction

    preds = Prediction.query.filter(Prediction.reasoning.isnot(None)).all()
    scanned = 0
    updated = 0

    for pred in preds:
        scanned += 1
        original = (pred.reasoning or "").strip()
        cleaned = sanitize_reasoning_text(original)

        if not cleaned:
            signal_names = [m.signal.name for m in pred.signal_matches]
            if signal_names:
                cleaned = (
                    f"{pred.direction.title()} outlook based on {len(signal_names)} "
                    f"signals: {', '.join(signal_names[:6])}."
                )

        if cleaned and cleaned != original:
            pred.reasoning = cleaned
            updated += 1

    db.session.commit()
    logger.info("Prediction reasoning cleanup complete: %d/%d updated", updated, scanned)
    return {"scanned": scanned, "updated": updated}


def _build_replay_state(as_of: datetime, company_ids: list[int] | None = None) -> dict:
    from app.models import Fundamentals, InsiderTrade

    companies_q = Company.query.filter_by(active=True)
    if company_ids:
        companies_q = companies_q.filter(Company.id.in_(company_ids))
    companies = companies_q.order_by(Company.id).all()

    cutoff = as_of - timedelta(days=90)
    price_data = {}
    fundamentals_data = {}
    selected = []

    for company in companies:
        prices = (
            PriceHistory.query.filter(
                PriceHistory.company_id == company.id,
                PriceHistory.timestamp >= cutoff,
                PriceHistory.timestamp <= as_of,
            )
            .order_by(PriceHistory.timestamp)
            .all()
        )
        if len(prices) < 30:
            continue

        df = pd.DataFrame([
            {
                "timestamp": p.timestamp,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume or 0,
            }
            for p in prices
        ])
        if df.empty:
            continue

        df.set_index("timestamp", inplace=True)
        price_data[company.id] = {"symbol": company.symbol, "df": df}
        selected.append(company.id)

        latest_fund = (
            Fundamentals.query.filter(
                Fundamentals.company_id == company.id,
                Fundamentals.snapshot_at <= as_of,
            )
            .order_by(Fundamentals.snapshot_at.desc())
            .first()
        )

        insider_trades = (
            InsiderTrade.query.filter(
                InsiderTrade.company_id == company.id,
                InsiderTrade.transaction_date <= as_of.date(),
            )
            .order_by(InsiderTrade.transaction_date.desc())
            .limit(50)
            .all()
        )

        fundamentals_data[company.id] = {
            "symbol": company.symbol,
            "latest": {
                "current_price": latest_fund.current_price,
                "fifty_two_week_high": latest_fund.fifty_two_week_high,
                "fifty_two_week_low": latest_fund.fifty_two_week_low,
                "pe_trailing": latest_fund.pe_trailing,
                "beta": latest_fund.beta,
            } if latest_fund else None,
            "insider_trades": [
                {
                    "filer_name": t.filer_name,
                    "filer_title": t.filer_title,
                    "transaction_type": t.transaction_type,
                    "shares": t.shares,
                    "price_per_share": t.price_per_share,
                    "date": t.transaction_date,
                }
                for t in insider_trades
            ],
        }

    return {
        "company_ids": selected,
        "price_data": price_data,
        "news_data": {},
        "fundamentals_data": fundamentals_data,
        "insider_data": {},
        "signals": [],
        "predictions": [],
        "strong_predictions": [],
        "weak_predictions": [],
        "iteration": 0,
        "max_iterations": 1,
        "confidence_threshold": 0.55,
        "analysis_time": as_of.isoformat(),
    }


def _detect_signals_as_of(state: dict, as_of: datetime) -> dict:
    from app.signals.detectors.technical import TechnicalDetector
    from app.signals.detectors.volume import VolumeDetector
    from app.signals.detectors.fundamentals_detector import FundamentalsDetector
    from app.signals.detectors.article_sentiment import ArticleSentimentDetector
    from app.signals.detectors.mention_velocity import MentionVelocityDetector
    from app.signals.detectors.comention import ComentionDetector
    from app.signals.detectors.source_breadth import SourceBreadthDetector

    detectors = [
        TechnicalDetector(),
        VolumeDetector(),
        FundamentalsDetector(),
        ArticleSentimentDetector(),
        MentionVelocityDetector(),
        ComentionDetector(),
        SourceBreadthDetector(),
    ]

    signals = []
    for detector in detectors:
        try:
            if detector.name in ARTICLE_DETECTOR_NAMES:
                found = detector.detect(state, before=as_of)
            else:
                found = detector.detect(state)
            signals.extend(found)
        except Exception:
            logger.exception("Replay detector %s failed @ %s", detector.name, as_of.isoformat())

    state["signals"] = signals
    return state


def _hydrate_replay_predictions(state: dict):
    by_company = defaultdict(list)
    for sig in state.get("signals", []):
        by_company[sig["company_id"]].append(sig)

    for pred in state.get("predictions", []):
        company_signals = by_company.get(pred["company_id"], [])
        signal_names = sorted({s["signal_name"] for s in company_signals})
        pred["signal_names"] = signal_names
        pred["magnitude"] = max(0.0, min(1.0, float(pred.get("confidence", 0.5)) * 0.5))
        summary = ", ".join(signal_names[:8]) if signal_names else "active signals"
        pred["reasoning"] = (
            f"{pred['direction'].title()} outlook based on {len(company_signals)} "
            f"signals: {summary}."
        )

    state["strong_predictions"] = state.get("predictions", [])
    state["weak_predictions"] = []
    return state


def replay_history_sync(
    days: int = 90,
    step_hours: int = 6,
    include_trends: bool = True,
    include_report: bool = True,
    company_ids: list[int] | None = None,
) -> dict:
    from app.signals.nodes.aggregate import aggregate_node
    from app.signals.nodes.output import output_node

    if days <= 0:
        raise ValueError("days must be > 0")
    if step_hours <= 0:
        raise ValueError("step_hours must be > 0")

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    step = timedelta(hours=step_hours)

    cursor = start
    steps = 0
    total_signals = 0
    total_predictions = 0

    logger.info(
        "Starting historical replay: start=%s end=%s step=%sh",
        start.isoformat(), end.isoformat(), step_hours,
    )

    while cursor <= end:
        state = _build_replay_state(cursor, company_ids=company_ids)
        if state["company_ids"]:
            state = _detect_signals_as_of(state, cursor)
            state = aggregate_node(state)
            state = _hydrate_replay_predictions(state)
            output_node(state)

            total_signals += len(state.get("signals", []))
            total_predictions += len(state.get("predictions", []))

        steps += 1
        if steps % 20 == 0:
            logger.info(
                "Replay progress: %d steps complete (%s), signals=%d predictions=%d",
                steps, cursor.isoformat(), total_signals, total_predictions,
            )
        cursor += step

    trend_count = None
    report_id = None
    if include_trends:
        from app.trends.agent import run_trending_agent
        snapshot = run_trending_agent()
        trend_count = len(snapshot.trends or [])
    if include_report:
        from app.reports.generator import generate_hourly_report
        report = generate_hourly_report()
        report_id = report.id

    return {
        "steps": steps,
        "total_signals": total_signals,
        "total_predictions": total_predictions,
        "trend_count": trend_count,
        "report_id": report_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "step_hours": step_hours,
    }


@celery.task(name="app.tasks.maintenance.replay_history")
def replay_history(
    days: int = 90,
    step_hours: int = 6,
    include_trends: bool = True,
    include_report: bool = True,
):
    lock = acquire_lock("lock:task:replay_history", ttl_seconds=60 * 60 * 24)
    if not lock:
        logger.info("Skipping replay_history — previous run still in progress")
        return {"skipped": True, "reason": "lock_held"}

    try:
        result = replay_history_sync(
            days=days,
            step_hours=step_hours,
            include_trends=include_trends,
            include_report=include_report,
        )
        mark_heartbeat("analysis")
        if include_trends:
            mark_heartbeat("trends")
        if include_report:
            mark_heartbeat("report")
        return result
    finally:
        release_lock("lock:task:replay_history", lock)
