import logging
import time
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

from app.extensions import db
from app.models import Company, InsiderTrade
from app.sources.base import BaseFetcher

logger = logging.getLogger(__name__)

EDGAR_HEADERS = {
    "User-Agent": "StockLynx Research research@stocklynx.dev",
    "Accept": "application/json",
}
EDGAR_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"

TRANSACTION_CODE_MAP = {
    "P": "Purchase",
    "S": "Sale",
    "G": "Gift",
    "A": "Award",
    "M": "Exercise",
    "F": "Tax Withholding",
    "C": "Conversion",
    "D": "Return to Issuer",
    "J": "Other",
}

MAX_FORM4_PER_COMPANY = 20


class EdgarFetcher(BaseFetcher):
    def __init__(self):
        self._cik_cache = {}

    def fetch(self, symbols: list[str] | None = None, delay: float = 0.15) -> list[dict]:
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

        cik_stripped = cik.lstrip("0")
        now = datetime.now(timezone.utc)
        results = []
        parsed_count = 0

        for idx, form in enumerate(forms):
            if form != "4":
                continue
            if idx >= len(dates) or idx >= len(accessions):
                break
            if parsed_count >= MAX_FORM4_PER_COMPANY:
                break

            filing_date = dates[idx]
            accession_raw = accessions[idx]
            accession = accession_raw.replace("-", "")
            doc = primary_docs[idx] if idx < len(primary_docs) else ""

            # Build the rendered URL (for dedup) and raw XML URL
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{doc}"

            existing = InsiderTrade.query.filter_by(filing_url=filing_url).first()
            if existing:
                continue  # already parsed this filing

            # Fetch and parse the raw Form 4 XML
            raw_doc = doc.split("/")[-1] if "/" in doc else doc
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{raw_doc}"

            trades = self._parse_form4_xml(xml_url, company.id, filing_date, filing_url, now)
            if trades:
                results.extend(trades)
            parsed_count += 1
            time.sleep(0.12)  # stay under 10 req/sec SEC limit

        db.session.commit()
        if results:
            logger.info("Stored %d insider transactions for %s", len(results), symbol)
        return results

    def _parse_form4_xml(self, xml_url: str, company_id: int, filing_date: str,
                         filing_url: str, now: datetime) -> list[dict]:
        try:
            resp = requests.get(xml_url, headers=EDGAR_HEADERS, timeout=10)
            if resp.status_code != 200:
                return []
            root = ET.fromstring(resp.content)
        except Exception:
            logger.debug("Failed to parse Form 4 XML: %s", xml_url)
            return []

        # Extract filer info
        owner_name = self._xml_text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown"
        owner_title = self._xml_text(root, ".//reportingOwner/reportingOwnerRelationship/officerTitle")

        trades = []
        # Parse non-derivative transactions
        for txn in root.findall(".//nonDerivativeTransaction"):
            trade = self._parse_transaction(txn, company_id, owner_name, owner_title,
                                            filing_date, filing_url, now)
            if trade:
                trades.append(trade)

        # Parse derivative transactions (options exercises etc.)
        for txn in root.findall(".//derivativeTransaction"):
            trade = self._parse_transaction(txn, company_id, owner_name, owner_title,
                                            filing_date, filing_url, now)
            if trade:
                trades.append(trade)

        return trades

    def _parse_transaction(self, txn_el, company_id: int, owner_name: str,
                           owner_title: str | None, filing_date: str,
                           filing_url: str, now: datetime) -> dict | None:
        code = self._xml_text(txn_el, ".//transactionCoding/transactionCode")
        if not code:
            return None

        transaction_type = TRANSACTION_CODE_MAP.get(code, f"Other ({code})")

        shares_str = self._xml_text(txn_el, ".//transactionAmounts/transactionShares/value")
        price_str = self._xml_text(txn_el, ".//transactionAmounts/transactionPricePerShare/value")
        ad_code = self._xml_text(txn_el, ".//transactionAmounts/transactionAcquiredDisposedCode/value")
        txn_date_str = self._xml_text(txn_el, ".//transactionDate/value") or filing_date

        shares = float(shares_str) if shares_str else 0.0
        price = float(price_str) if price_str and price_str != "0" else None
        total_value = (shares * price) if shares and price else None

        # Adjust sign: D = disposed (negative context)
        if ad_code == "D" and transaction_type == "Purchase":
            transaction_type = "Sale"

        try:
            txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d").date()
        except ValueError:
            txn_date = datetime.strptime(filing_date, "%Y-%m-%d").date()

        trade = InsiderTrade(
            company_id=company_id,
            filer_name=owner_name,
            filer_title=owner_title,
            transaction_type=transaction_type,
            shares=shares,
            price_per_share=price,
            total_value=total_value,
            transaction_date=txn_date,
            filing_url=filing_url,
            fetched_at=now,
        )
        db.session.add(trade)
        return {"name": owner_name, "type": transaction_type, "shares": shares, "date": txn_date_str}

    @staticmethod
    def _xml_text(el, path: str) -> str | None:
        node = el.find(path)
        return node.text.strip() if node is not None and node.text else None
