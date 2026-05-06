import logging
import os
import re
from datetime import datetime, timedelta, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.extensions import db
from app.models import Company, PriceHistory, SignalMatch, Prediction, Report
from app.articles.indices import sentiment_score, mention_velocity, source_breadth
from app.signals.llm_utils import parse_llm_json

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are a senior market analyst writing an hourly briefing. Based on the data below, write a concise 3-5 sentence executive summary covering the key market movements, notable signals, and any predictions worth highlighting.

Be specific — name tickers, cite numbers, and highlight what's actionable.

{data}"""


def generate_hourly_report() -> Report:
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    movers = _get_top_movers(one_hour_ago)
    signals = _get_recent_signals(one_hour_ago)
    predictions = _get_recent_predictions(one_hour_ago)
    indices = _get_article_indices_snapshot()

    data = {
        "top_movers": movers,
        "signals": signals,
        "predictions": predictions,
        "article_indices": indices,
    }

    summary = _generate_summary(data)

    report = Report(
        report_type="hourly",
        generated_at=now,
        summary=summary,
        data=data,
    )
    db.session.add(report)
    db.session.commit()

    logger.info("Generated hourly report #%d: %d movers, %d signals, %d predictions",
                report.id, len(movers), len(signals), len(predictions))
    return report


def _get_top_movers(since: datetime, limit: int = 10) -> list[dict]:
    companies = Company.query.filter_by(active=True).all()
    movers = []

    for company in companies:
        prices = (
            PriceHistory.query.filter(
                PriceHistory.company_id == company.id,
                PriceHistory.timestamp >= since,
            )
            .order_by(PriceHistory.timestamp)
            .all()
        )
        if len(prices) < 2:
            continue

        open_price = prices[0].open
        close_price = prices[-1].close
        if not open_price or open_price == 0:
            continue

        change_pct = (close_price - open_price) / open_price * 100

        movers.append({
            "symbol": company.symbol,
            "open": round(open_price, 2),
            "close": round(close_price, 2),
            "change_pct": round(change_pct, 2),
            "volume": sum(p.volume or 0 for p in prices),
        })

    movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return movers[:limit]


def _get_recent_signals(since: datetime) -> list[dict]:
    matches = (
        SignalMatch.query
        .filter(SignalMatch.detected_at >= since)
        .order_by(SignalMatch.confidence.desc())
        .limit(50)
        .all()
    )

    return [
        {
            "signal": m.signal.name,
            "signal_type": m.signal.signal_type,
            "company": m.company.symbol,
            "direction": m.direction,
            "confidence": m.confidence,
            "detected_at": m.detected_at.isoformat(),
        }
        for m in matches
    ]


def _get_recent_predictions(since: datetime) -> list[dict]:
    preds = (
        Prediction.query
        .filter(Prediction.created_at >= since)
        .order_by(Prediction.confidence.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "company": p.company.symbol,
            "direction": p.direction,
            "confidence": p.confidence,
            "reasoning": p.reasoning,
            "signal_count": len(p.signal_matches),
        }
        for p in preds
    ]


def _get_article_indices_snapshot() -> dict:
    try:
        sentiments = sentiment_score()
        top_sentiment = sorted(
            sentiments.items(),
            key=lambda x: x[1]["total_mentions"],
            reverse=True,
        )[:10]

        velocities = mention_velocity()
        spikes = {
            sym: v for sym, v in velocities.items()
            if v.get("24h", {}).get("rate_of_change", 0) > 0.5
        }

        breadth_data = source_breadth()
        high_breadth = {
            sym: b for sym, b in breadth_data.items()
            if b["unique_sources"] >= 3
        }

        return {
            "top_sentiment": {sym: data for sym, data in top_sentiment},
            "mention_spikes": {sym: v.get("24h", {}) for sym, v in list(spikes.items())[:10]},
            "high_source_breadth": {sym: b["unique_sources"] for sym, b in list(high_breadth.items())[:10]},
        }
    except Exception:
        logger.exception("Failed to pull article indices")
        return {}


def _generate_summary(data: dict) -> str:
    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return _fallback_summary(data)

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.3,
        max_tokens=500,
    )

    movers_str = ""
    for m in data.get("top_movers", [])[:5]:
        movers_str += f"  {m['symbol']}: {m['change_pct']:+.2f}% (${m['close']})\n"

    signals_str = ""
    for s in data.get("signals", [])[:10]:
        signals_str += f"  {s['company']} — {s['signal']} ({s['direction']}, {s['confidence']:.0%})\n"

    preds_str = ""
    for p in data.get("predictions", [])[:5]:
        preds_str += f"  {p['company']} — {p['direction']} ({p['confidence']:.0%}): {p['reasoning'][:100]}\n"

    indices = data.get("article_indices", {})
    sentiment_str = ""
    for sym, s in list(indices.get("top_sentiment", {}).items())[:5]:
        sentiment_str += f"  {sym}: score={s['score']}, mentions={s['total_mentions']}\n"

    context = f"""TOP MOVERS:
{movers_str or '  None'}

SIGNALS FIRED:
{signals_str or '  None'}

PREDICTIONS:
{preds_str or '  None'}

ARTICLE SENTIMENT:
{sentiment_str or '  None'}"""

    try:
        response = llm.invoke([
            SystemMessage(content="You are a senior market analyst. Write concise, data-driven briefings."),
            HumanMessage(content=SUMMARY_PROMPT.format(data=context)),
        ])
        text = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip()
        return text
    except Exception:
        logger.exception("LLM summary generation failed")
        return _fallback_summary(data)


def _fallback_summary(data: dict) -> str:
    movers = data.get("top_movers", [])
    signals = data.get("signals", [])
    preds = data.get("predictions", [])

    parts = []
    if movers:
        top = movers[0]
        parts.append(f"Top mover: {top['symbol']} at {top['change_pct']:+.2f}%.")
    parts.append(f"{len(signals)} signals fired across {len(set(s['company'] for s in signals))} companies.")
    if preds:
        parts.append(f"{len(preds)} predictions generated.")

    return " ".join(parts)
