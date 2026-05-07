import json

import click
import yaml
from flask import current_app
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Company, FeedSource, Index


@click.command("seed")
@with_appcontext
def seed_command():
    """Seed companies, indexes, and feed sources."""
    _seed_from_json()
    _seed_feeds()
    db.session.commit()
    click.echo("Seed complete.")


def _seed_from_json():
    seed_path = "/app/seed_data.json"
    try:
        with open(seed_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        click.echo("  seed_data.json not found, falling back to watchlist.yaml")
        _seed_from_yaml()
        return

    index_map = {}
    for idx_cfg in data.get("indexes", []):
        existing = Index.query.filter_by(symbol=idx_cfg["symbol"]).first()
        if not existing:
            existing = Index(symbol=idx_cfg["symbol"], name=idx_cfg["name"])
            db.session.add(existing)
            db.session.flush()
            click.echo(f"  Added index: {idx_cfg['symbol']}")
        index_map[idx_cfg["symbol"]] = existing

    added = 0
    updated = 0
    for t in data.get("tickers", []):
        company = Company.query.filter_by(symbol=t["symbol"]).first()
        if not company:
            company = Company(
                symbol=t["symbol"],
                name=t.get("name"),
                sector=t.get("sector"),
                industry=t.get("industry"),
                active=True,
            )
            db.session.add(company)
            db.session.flush()
            added += 1
        else:
            company.name = t.get("name", company.name)
            company.sector = t.get("sector", company.sector)
            company.industry = t.get("industry", company.industry)
            updated += 1

        for idx_symbol in t.get("indexes", []):
            idx_obj = index_map.get(idx_symbol)
            if idx_obj and idx_obj not in company.indexes:
                company.indexes.append(idx_obj)

    click.echo(f"  Companies: {added} added, {updated} updated")


def _seed_from_yaml():
    path = "/app/watchlist.yaml"
    with open(path) as f:
        config = yaml.safe_load(f)

    for t in config.get("tickers", []):
        existing = Company.query.filter_by(symbol=t["symbol"]).first()
        if not existing:
            db.session.add(
                Company(
                    symbol=t["symbol"],
                    name=t.get("name"),
                    sector=t.get("sector"),
                    industry=t.get("industry"),
                    description=t.get("description"),
                    active=True,
                )
            )


def _seed_feeds():
    path = "/app/watchlist.yaml"
    try:
        with open(path) as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return

    for f_cfg in config.get("news_feeds", []):
        existing = FeedSource.query.filter_by(url=f_cfg["url"]).first()
        if not existing:
            db.session.add(
                FeedSource(
                    name=f_cfg["name"],
                    url=f_cfg["url"],
                    source_type=f_cfg.get("source_type", "rss"),
                    active=True,
                )
            )
            click.echo(f"  Added feed: {f_cfg['name']}")


@click.command("process-backlog")
@click.option("--backfill", is_flag=True, default=True, help="Route to backfill queue (default)")
@click.option("--main", is_flag=True, default=False, help="Route to main celery queue")
@with_appcontext
def process_backlog_command(backfill, main):
    """Queue all unprocessed articles for processing via Celery."""
    from app.models import NewsArticle
    from app.tasks.articles import process_article

    queue = "celery" if main else "backfill"
    articles = NewsArticle.query.filter_by(processed=False).all()
    click.echo(f"Queuing {len(articles)} unprocessed articles on '{queue}' queue")

    for article in articles:
        process_article.apply_async(args=[article.id], queue=queue)

    click.echo(f"Queued {len(articles)} articles")


@click.command("clean-articles")
@click.option("--reprocess", is_flag=True, default=False, help="Re-queue cleaned articles for processing")
@click.option("--queue", default="backfill", help="Celery queue name (default: backfill)")
@with_appcontext
def clean_articles_command(reprocess, queue):
    """Detect and clean articles with bot-check content or no usable text."""
    from app.models import NewsArticle
    from app.articles.processor import BOT_CHECK_PHRASES

    articles = NewsArticle.query.filter(NewsArticle.processed == True).all()
    bot_check = 0
    no_content = 0
    already_good = 0

    for a in articles:
        text = (a.full_text or "").lower()
        is_bad = any(phrase in text for phrase in BOT_CHECK_PHRASES)

        if is_bad:
            a.full_text = None
            a.content_source = None
            a.processed = False
            bot_check += 1
        elif not a.full_text and not a.summary:
            a.content_source = None
            no_content += 1
        elif not a.content_source:
            if a.full_text and a.full_text == a.summary:
                a.content_source = "summary"
            elif a.full_text:
                a.content_source = "scraped"
            already_good += 1

    db.session.commit()
    click.echo(f"Bot-check pages cleared: {bot_check}")
    click.echo(f"No usable content: {no_content}")
    click.echo(f"Already good (tagged): {already_good}")

    if reprocess:
        from app.tasks.articles import process_article
        to_reprocess = NewsArticle.query.filter_by(processed=False).all()
        for a in to_reprocess:
            process_article.apply_async(args=[a.id], queue=queue)
        click.echo(f"Queued {len(to_reprocess)} articles for reprocessing on '{queue}'")


@click.command("backfill-prices")
@with_appcontext
def backfill_prices_command():
    """Queue 60-day 15m price backfill for all companies."""
    from app.tasks.maintenance import backfill_all
    result = backfill_all.delay()
    click.echo(f"Backfill queued: {result.id}")
