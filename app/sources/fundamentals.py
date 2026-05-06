import logging
import time
from datetime import datetime, timezone

import requests

from app.extensions import db
from app.models import Company, Fundamentals
from app.sources.base import BaseFetcher

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class FundamentalsFetcher(BaseFetcher):
    def fetch(self, symbols: list[str] | None = None, delay: float = 0.5) -> list[dict]:
        if symbols is None:
            companies = Company.query.filter_by(active=True).all()
            symbols = [c.symbol for c in companies]

        results = []
        for i, symbol in enumerate(symbols):
            try:
                snapshot = self._fetch_fundamentals(symbol)
                if snapshot:
                    results.append(snapshot)
            except Exception:
                logger.exception("Failed to fetch fundamentals for %s", symbol)
            if delay and i < len(symbols) - 1:
                time.sleep(delay)
        return results

    def _fetch_fundamentals(self, symbol: str) -> dict | None:
        company = Company.query.filter_by(symbol=symbol).first()
        if not company:
            return None

        url = YAHOO_CHART_URL.format(symbol=symbol)
        params = {"range": "1y", "interval": "1d"}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        result = data.get("chart", {}).get("result", [])
        if not result:
            return None

        meta = result[0].get("meta", {})

        now = datetime.now(timezone.utc)
        fundamentals = Fundamentals(
            company_id=company.id,
            fifty_two_week_high=meta.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=meta.get("fiftyTwoWeekLow"),
            current_price=meta.get("regularMarketPrice"),
            market_cap=None,
            snapshot_at=now,
        )
        db.session.add(fundamentals)
        db.session.commit()

        logger.info("Stored fundamentals snapshot for %s", symbol)
        return {
            "symbol": symbol,
            "price": meta.get("regularMarketPrice"),
            "52w_high": meta.get("fiftyTwoWeekHigh"),
            "52w_low": meta.get("fiftyTwoWeekLow"),
        }
