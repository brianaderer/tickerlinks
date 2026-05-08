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

SUMMARY_PROMPT = """You are a senior market analyst writing a rolling 24-hour market brief. Today is {today}. This brief is updated every 15 minutes.

RULES:
- Write 1-2 natural paragraphs, newspaper-style. No bullet points, no headers, no lists.
- Use **bold** for ticker symbols and key numbers.
- Emphasize the most recent developments — what happened in the last few hours matters more than yesterday. But weave in the full-day context.
- Be specific: name tickers, cite percentage moves, mention signal counts.
- If there are notable divergences (bullish signals on a stock with bearish sentiment, or vice versa), call them out.
- End with one actionable insight or thing to watch.

DATA:
{data}"""


def generate_hourly_report() -> Report:
    now = datetime.now(timezone.utc)
    window = now - timedelta(hours=24)

    movers = _get_top_movers(window)
    signals = _get_recent_signals(window)
    predictions = _get_latest_predictions()
    indices = _get_article_indices_snapshot()

    data = {
        "top_movers": movers,
        "signals": signals,
        "predictions": predictions,
        "article_indices": indices,
    }

    summary = _generate_summary(data, now)

    existing = Report.query.filter_by(report_type="hourly").order_by(
        Report.generated_at.desc()
    ).first()

    if existing:
        existing.generated_at = now
        existing.summary = summary
        existing.data = data
        db.session.commit()
        logger.info("Updated hourly report #%d", existing.id)
        return existing

    report = Report(
        report_type="hourly",
        generated_at=now,
        summary=summary,
        data=data,
    )
    db.session.add(report)
    db.session.commit()
    logger.info("Generated hourly report #%d", report.id)
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
        .order_by(SignalMatch.detected_at.desc())
        .limit(100)
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
            "source_at": (m.source_at or m.detected_at).isoformat(),
        }
        for m in matches
    ]


def _get_latest_predictions() -> list[dict]:
    from sqlalchemy import func
    latest_subq = (
        db.session.query(
            Prediction.company_id,
            func.max(Prediction.created_at).label("max_created"),
        )
        .group_by(Prediction.company_id)
        .subquery()
    )

    preds = (
        Prediction.query.join(
            latest_subq,
            (Prediction.company_id == latest_subq.c.company_id)
            & (Prediction.created_at == latest_subq.c.max_created),
        )
        .order_by(Prediction.confidence.desc())
        .all()
    )

    return [
        {
            "company": p.company.symbol,
            "direction": p.direction,
            "confidence": p.confidence,
            "magnitude": p.magnitude,
            "reasoning": (p.reasoning or "")[:200],
            "signal_count": len(p.signal_matches),
            "updated_at": p.created_at.isoformat(),
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


def _generate_summary(data: dict, now: datetime) -> str:
    api_key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return _fallback_summary(data)

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B"),
        openai_api_key=api_key,
        openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
        temperature=0.3,
        max_tokens=1500,
    )

    movers_str = ""
    for m in data.get("top_movers", [])[:8]:
        movers_str += f"  {m['symbol']}: {m['change_pct']:+.2f}% (${m['close']:.2f})\n"

    signals = data.get("signals", [])
    by_company: dict[str, list] = {}
    for s in signals:
        by_company.setdefault(s["company"], []).append(s)

    signals_str = ""
    for sym, sigs in sorted(by_company.items(), key=lambda x: -len(x[1]))[:8]:
        bullish = [s for s in sigs if s["direction"] == "bullish"]
        bearish = [s for s in sigs if s["direction"] == "bearish"]
        latest_time = sigs[0]["source_at"][:16]
        signals_str += (
            f"  {sym}: {len(bullish)} bullish, {len(bearish)} bearish "
            f"(latest: {latest_time})\n"
        )
        for s in sigs[:3]:
            signals_str += f"    - {s['signal']} ({s['direction']}, {s['confidence']:.0%}) source: {s['source_at'][:16]}\n"

    preds_str = ""
    for p in data.get("predictions", [])[:6]:
        mag = f", magnitude {p['magnitude']:.0%}" if p.get("magnitude") else ""
        preds_str += (
            f"  {p['company']}: {p['direction']} ({p['confidence']:.0%}{mag}) "
            f"— {p['reasoning'][:120]}\n"
        )

    indices = data.get("article_indices", {})
    sentiment_str = ""
    for sym, s in list(indices.get("top_sentiment", {}).items())[:6]:
        sentiment_str += f"  {sym}: score={s['score']:+.3f} ({s['total_mentions']} mentions, {s['bullish']}B/{s['bearish']}b/{s['neutral']}N)\n"

    spikes_str = ""
    for sym, v in list(indices.get("mention_spikes", {}).items())[:5]:
        spikes_str += f"  {sym}: {v.get('count', 0)} mentions (rate of change: {v.get('rate_of_change', 0):+.1f}x)\n"

    context = f"""PRICE MOVERS (24h):
{movers_str or '  No significant movers'}

SIGNALS BY COMPANY (24h, most active first):
{signals_str or '  No signals'}

CURRENT PREDICTIONS:
{preds_str or '  No predictions'}

ARTICLE SENTIMENT:
{sentiment_str or '  No sentiment data'}

MENTION VELOCITY SPIKES:
{spikes_str or '  No spikes'}"""

    try:
        response = llm.invoke([
            SystemMessage(content="You are a senior market analyst. Write concise, data-driven briefings. No preamble."),
            HumanMessage(content=SUMMARY_PROMPT.format(today=now.strftime("%Y-%m-%d %H:%M UTC"), data=context)),
        ])
        text = re.sub(r"<think>[\s\S]*?</think>", "", response.content).strip()
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
        parts.append(f"**{top['symbol']}** leads movers at {top['change_pct']:+.2f}%.")
    companies = set(s["company"] for s in signals)
    parts.append(f"{len(signals)} signals fired across **{len(companies)}** companies in the last 24 hours.")
    if preds:
        parts.append(f"{len(preds)} active predictions.")

    return " ".join(parts)
