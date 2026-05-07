import logging
import time
from datetime import datetime, timezone

import requests

from app.extensions import db
from app.models import Company, PriceHistory
from app.sources.base import BaseFetcher

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class MarketFetcher(BaseFetcher):
    def __init__(self, period="1d", interval="15m"):
        self.period = period
        self.interval = interval

    def fetch(self, symbols: list[str] | None = None, delay: float = 0) -> list[dict]:
        if symbols is None:
            companies = Company.query.filter_by(active=True).all()
            symbols = [c.symbol for c in companies]

        results = []
        for i, symbol in enumerate(symbols):
            try:
                rows = self._fetch_symbol(symbol)
                results.extend(rows)
            except Exception:
                logger.exception("Failed to fetch market data for %s", symbol)
            if delay and i < len(symbols) - 1:
                time.sleep(delay)
        return results

    def _fetch_symbol(self, symbol: str) -> list[dict]:
        company = Company.query.filter_by(symbol=symbol).first()
        if not company:
            logger.warning("Company %s not found in DB, skipping", symbol)
            return []

        url = YAHOO_CHART_URL.format(symbol=symbol)
        params = {"range": self.period, "interval": self.interval}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        chart_result = data.get("chart", {}).get("result")
        if not chart_result:
            logger.info("No chart data returned for %s", symbol)
            return []

        result = chart_result[0]
        timestamps = result.get("timestamp", [])
        quotes = result.get("indicators", {}).get("quote", [{}])[0]

        if not timestamps:
            logger.info("No timestamps for %s", symbol)
            return []

        now = datetime.now(timezone.utc)
        rows = []

        for idx, ts_epoch in enumerate(timestamps):
            ts_utc = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)

            existing = PriceHistory.query.filter_by(
                company_id=company.id, timestamp=ts_utc
            ).first()
            if existing:
                continue

            open_val = quotes.get("open", [None] * len(timestamps))[idx]
            high_val = quotes.get("high", [None] * len(timestamps))[idx]
            low_val = quotes.get("low", [None] * len(timestamps))[idx]
            close_val = quotes.get("close", [None] * len(timestamps))[idx]
            volume_val = quotes.get("volume", [None] * len(timestamps))[idx]

            if close_val is None:
                continue

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
            rows.append(
                {"symbol": symbol, "timestamp": str(ts_utc), "close": price.close}
            )

        db.session.commit()
        logger.info("Stored %d new price rows for %s", len(rows), symbol)
        return rows

    @staticmethod
    def sync_company_info(symbol: str) -> dict | None:
        try:
            url = YAHOO_CHART_URL.format(symbol=symbol)
            resp = requests.get(
                url, headers=HEADERS, params={"range": "1d", "interval": "1d"}, timeout=15
            )
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]

            company = Company.query.filter_by(symbol=symbol).first()
            if company:
                company.name = meta.get("longName") or meta.get("shortName")
                try:
                    from app.sources.fundamentals import FundamentalsFetcher
                    caps = FundamentalsFetcher._fetch_market_caps_batch([symbol])
                    if symbol in caps:
                        company.market_cap = caps[symbol]
                except Exception:
                    logger.warning("Could not fetch market cap for %s during sync", symbol)
                db.session.commit()
                logger.info("Synced company info for %s", symbol)
            return meta
        except Exception:
            logger.exception("Failed to sync info for %s", symbol)
            return None
