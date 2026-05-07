import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.models import Company
from app.signals.llm_utils import parse_llm_json

logger = logging.getLogger(__name__)

_company_list_prompt = None
_llm = None
_valid_symbols = None


def _get_valid_symbols() -> set[str]:
    global _valid_symbols
    if _valid_symbols is None:
        _valid_symbols = set(
            c.symbol.upper() for c in Company.query.filter_by(active=True).all()
        )
    return _valid_symbols


def _get_company_list_prompt() -> str:
    global _company_list_prompt
    if _company_list_prompt is None:
        companies = Company.query.filter_by(active=True).order_by(Company.symbol).all()
        lines = []
        for c in companies:
            desc = (c.description or "")[:120].replace("\n", " ")
            lines.append(f"{c.symbol} | {c.name} | {c.sector or ''} | {desc}")
        _company_list_prompt = "\n".join(lines)
    return _company_list_prompt


def _get_llm():
    global _llm
    if _llm is None:
        api_key = os.environ.get("DEEPINFRA_API_KEY", "")
        if not api_key:
            return None
        _llm = ChatOpenAI(
            model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
            openai_api_key=api_key,
            openai_api_base=os.environ.get(
                "LLM_API_BASE", "https://api.deepinfra.com/v1/openai"
            ),
            temperature=0,
            max_tokens=1000,
        )
    return _llm


def invalidate_cache():
    global _company_list_prompt, _valid_symbols
    _company_list_prompt = None
    _valid_symbols = None


SYSTEM_PROMPT = """You are a stock ticker identification agent. You will be given a news article and a complete list of tracked companies. Your job is to identify which companies from the list are mentioned in or clearly relevant to the article.

RULES:
- ONLY return tickers that appear in the provided company list. No exceptions.
- Match based on company name, description, sector, and article context — not just ticker symbols in the text.
- If the article mentions a company that is NOT in the list, do not include it.
- For each matched company, assess the article's sentiment toward THAT SPECIFIC company and whether it is a primary subject or secondary mention.

Return ONLY a JSON object:
{
    "companies": {
        "AAPL": {"sentiment": "bullish", "relevance": "primary"},
        "INTC": {"sentiment": "bearish", "relevance": "secondary"}
    }
}

If no tracked companies are mentioned, return: {"companies": {}}

Sentiment must be one of: bullish, bearish, neutral
Relevance must be one of: primary, secondary"""


def match_tickers(title: str, summary: str, full_text: str = "") -> dict:
    llm = _get_llm()
    if not llm:
        return {}

    company_list = _get_company_list_prompt()
    valid = _get_valid_symbols()

    body = (full_text or summary or "")[:4000]

    user_msg = f"""TRACKED COMPANIES:
{company_list}

ARTICLE:
Title: {title}
Body: {body}

Identify all tracked companies mentioned in or relevant to this article."""

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        result = parse_llm_json(response.content)
        if not result:
            return {}

        companies = result.get("companies", {})
        if isinstance(companies, list):
            companies = {c: {"sentiment": "neutral", "relevance": "primary"} for c in companies}

        validated = {}
        for sym, meta in companies.items():
            sym_upper = sym.strip().upper()
            if sym_upper in valid:
                validated[sym_upper] = meta
            else:
                logger.debug("Ticker agent returned %s — not in our list, dropped", sym_upper)

        return validated

    except Exception:
        logger.exception("Ticker matching agent failed")
        return {}
