import logging
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.models import Company, PriceHistory, NewsArticle, Fundamentals, InsiderTrade
from app.signals.state import EngineState

logger = logging.getLogger(__name__)


def gather_node(state: EngineState) -> EngineState:
    company_ids = state.get("company_ids", [])
    if not company_ids:
        companies = Company.query.filter_by(active=True).all()
        company_ids = [c.id for c in companies]

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    news_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    price_data = {}
    news_data = {}
    fundamentals_data = {}

    for cid in company_ids:
        company = Company.query.get(cid)
        if not company:
            continue

        prices = (
            PriceHistory.query.filter(
                PriceHistory.company_id == cid,
                PriceHistory.timestamp >= cutoff,
            )
            .order_by(PriceHistory.timestamp)
            .all()
        )

        if prices:
            df = pd.DataFrame(
                [
                    {
                        "timestamp": p.timestamp,
                        "open": p.open,
                        "high": p.high,
                        "low": p.low,
                        "close": p.close,
                        "volume": p.volume or 0,
                    }
                    for p in prices
                ]
            )
            df.set_index("timestamp", inplace=True)
            price_data[cid] = {"symbol": company.symbol, "df": df}

        articles = (
            NewsArticle.query.filter(
                NewsArticle.company_id == cid,
                NewsArticle.published_at >= news_cutoff,
            )
            .order_by(NewsArticle.published_at.desc())
            .limit(20)
            .all()
        )

        if articles:
            news_data[cid] = {
                "symbol": company.symbol,
                "articles": [
                    {
                        "title": a.title,
                        "summary": a.summary,
                        "published_at": a.published_at.isoformat() if a.published_at else None,
                        "source": a.source_name,
                    }
                    for a in articles
                ],
            }

        latest_fund = (
            Fundamentals.query.filter_by(company_id=cid)
            .order_by(Fundamentals.snapshot_at.desc())
            .first()
        )

        insider_trades = (
            InsiderTrade.query.filter_by(company_id=cid)
            .order_by(InsiderTrade.transaction_date.desc())
            .limit(50)
            .all()
        )

        fundamentals_data[cid] = {
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
                    "transaction_type": t.transaction_type,
                    "shares": t.shares,
                    "date": t.transaction_date,
                }
                for t in insider_trades
            ],
        }

    state["price_data"] = price_data
    state["news_data"] = news_data
    state["fundamentals_data"] = fundamentals_data
    state["company_ids"] = company_ids

    logger.info(
        "Gathered data: %d price sets, %d news sets, %d fundamentals sets",
        len(price_data), len(news_data), len(fundamentals_data),
    )
    return state
