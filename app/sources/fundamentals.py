import logging
import time
from datetime import datetime, timezone

import requests

from app.extensions import db
from app.models import Company, Fundamentals
from app.sources.base import BaseFetcher

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_QUOTE_URL = "https://query2.finance.yahoo.com/v7/finance/quote"
YAHOO_CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

QUOTE_BATCH_SIZE = 20


class FundamentalsFetcher(BaseFetcher):
    def fetch(self, symbols: list[str] | None = None, delay: float = 0.5) -> list[dict]:
        if symbols is None:
            companies = Company.query.filter_by(active=True).all()
            symbols = [c.symbol for c in companies]

        market_caps = self._fetch_market_caps_batch(symbols)

        results = []
        for i, symbol in enumerate(symbols):
            try:
                snapshot = self._fetch_fundamentals(symbol, market_caps.get(symbol))
                if snapshot:
                    results.append(snapshot)
            except Exception:
                logger.exception("Failed to fetch fundamentals for %s", symbol)
            if delay and i < len(symbols) - 1:
                time.sleep(delay)
        return results

    def _fetch_fundamentals(self, symbol: str, market_cap: int | None = None) -> dict | None:
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
            market_cap=market_cap,
            snapshot_at=now,
        )
        db.session.add(fundamentals)

        if market_cap is not None:
            company.market_cap = market_cap

        db.session.commit()

        logger.info("Stored fundamentals snapshot for %s (market_cap=%s)", symbol, market_cap)
        return {
            "symbol": symbol,
            "price": meta.get("regularMarketPrice"),
            "52w_high": meta.get("fiftyTwoWeekHigh"),
            "52w_low": meta.get("fiftyTwoWeekLow"),
            "market_cap": market_cap,
        }

    @staticmethod
    def _fetch_market_caps_batch(symbols: list[str]) -> dict[str, int]:
        caps: dict[str, int] = {}
        try:
            session = requests.Session()
            session.headers.update(HEADERS)
            session.get("https://fc.yahoo.com", timeout=10)
            crumb_resp = session.get(YAHOO_CRUMB_URL, timeout=10)
            crumb_resp.raise_for_status()
            crumb = crumb_resp.text

            for i in range(0, len(symbols), QUOTE_BATCH_SIZE):
                batch = symbols[i : i + QUOTE_BATCH_SIZE]
                resp = session.get(
                    YAHOO_QUOTE_URL,
                    params={"symbols": ",".join(batch), "crumb": crumb},
                    timeout=15,
                )
                resp.raise_for_status()
                for quote in resp.json().get("quoteResponse", {}).get("result", []):
                    cap = quote.get("marketCap")
                    if cap is not None:
                        caps[quote["symbol"]] = int(cap)
                if i + QUOTE_BATCH_SIZE < len(symbols):
                    time.sleep(0.3)

            logger.info("Batch-fetched market caps for %d/%d symbols", len(caps), len(symbols))
        except Exception:
            logger.exception("Failed to batch-fetch market caps")
        return caps
