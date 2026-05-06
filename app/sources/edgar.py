import logging
import time
from datetime import datetime, timezone

import requests

from app.extensions import db
from app.models import Company, InsiderTrade
from app.sources.base import BaseFetcher

logger = logging.getLogger(__name__)

EDGAR_HEADERS = {
    "User-Agent": "StockLynx Research research@stocklynx.dev",
    "Accept": "application/json",
}
EDGAR_SUBMISSIONS_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{cik}%22&dateRange=custom&startdt={start}&enddt={end}&forms=4"
EDGAR_FILINGS_URL = "https://efts.sec.gov/LATEST/search-index?q=%224%22&entityName={symbol}&dateRange=custom&startdt={start}&enddt={end}"
EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index?q={symbol}&forms=4&dateRange=custom&startdt={start}&enddt={end}"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


class EdgarFetcher(BaseFetcher):
    def __init__(self):
        self._cik_cache = {}

    def fetch(self, symbols: list[str] | None = None, delay: float = 1.0) -> list[dict]:
        if symbols is None:
            companies = Company.query.filter_by(active=True).all()
            symbols = [c.symbol for c in companies]

        self._load_cik_map()

        results = []
        for i, symbol in enumerate(symbols):
            try:
                trades = self._fetch_insider_trades(symbol)
                results.extend(trades)
            except Exception:
                logger.exception("Failed to fetch EDGAR data for %s", symbol)
            if delay and i < len(symbols) - 1:
                time.sleep(delay)
        return results

    def _load_cik_map(self):
        if self._cik_cache:
            return
        try:
            resp = requests.get(EDGAR_COMPANY_TICKERS, headers=EDGAR_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for entry in data.values():
                ticker = entry.get("ticker", "").upper()
                cik = str(entry.get("cik_str", "")).zfill(10)
                self._cik_cache[ticker] = cik
            logger.info("Loaded %d CIK mappings", len(self._cik_cache))
        except Exception:
            logger.exception("Failed to load CIK map")

    def _fetch_insider_trades(self, symbol: str) -> list[dict]:
        company = Company.query.filter_by(symbol=symbol).first()
        if not company:
            return []

        cik = self._cik_cache.get(symbol.upper())
        if not cik:
            logger.debug("No CIK found for %s", symbol)
            return []

        url = EDGAR_SUBMISSIONS.format(cik=cik)
        resp = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        now = datetime.now(timezone.utc)
        trades = []

        for idx, form in enumerate(forms):
            if form != "4":
                continue
            if idx >= len(dates) or idx >= len(accessions):
                break

            filing_date = dates[idx]
            accession = accessions[idx].replace("-", "")
            doc = primary_docs[idx] if idx < len(primary_docs) else ""
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc}"

            existing = InsiderTrade.query.filter_by(filing_url=filing_url).first()
            if existing:
                continue

            trade = InsiderTrade(
                company_id=company.id,
                filer_name=data.get("name", "Unknown"),
                transaction_type="Form 4",
                shares=0,
                price_per_share=None,
                total_value=None,
                transaction_date=datetime.strptime(filing_date, "%Y-%m-%d").date(),
                filing_url=filing_url,
                fetched_at=now,
            )
            db.session.add(trade)
            trades.append({"symbol": symbol, "date": filing_date, "url": filing_url})

        db.session.commit()
        if trades:
            logger.info("Stored %d insider filings for %s", len(trades), symbol)
        return trades
