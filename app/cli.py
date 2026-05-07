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
@with_appcontext
def process_backlog_command():
    """Queue all unprocessed articles for processing via Celery."""
    from app.models import NewsArticle
    from app.tasks.articles import process_article

    articles = NewsArticle.query.filter_by(processed=False).all()
    click.echo(f"Queuing {len(articles)} unprocessed articles")

    for article in articles:
        process_article.delay(article.id)

    click.echo(f"Queued {len(articles)} articles for processing")


@click.command("backfill-prices")
@with_appcontext
def backfill_prices_command():
    """Queue 60-day 15m price backfill for all companies."""
    from app.tasks.maintenance import backfill_all
    result = backfill_all.delay()
    click.echo(f"Backfill queued: {result.id}")
