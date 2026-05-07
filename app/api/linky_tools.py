from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from app.extensions import db
from app.models import (
    Company, Fundamentals, PriceHistory, SignalMatch, Prediction,
    Signal, Report, TrendSnapshot,
)
from app.signals.research import research_company  # re-export existing tool


@tool
def get_company_profile(symbol: str) -> str:
    """Get fundamentals, recent signals, latest prediction, and price action for a company.

    Args:
        symbol: Ticker symbol (e.g. "NVDA")

    Returns:
        Company profile with fundamentals, signals, prediction, and price data.
    """
    company = Company.query.filter_by(symbol=symbol.upper()).first()
    if not company:
        return f"Company {symbol} not found."

    parts = [f"## {company.symbol} — {company.name or 'Unknown'}"]
    if company.sector:
        parts.append(f"Sector: {company.sector} | Industry: {company.industry or 'N/A'}")

    fund = Fundamentals.query.filter_by(company_id=company.id).order_by(
        Fundamentals.snapshot_at.desc()
    ).first()
    if fund:
        parts.append(f"\nFundamentals (as of {fund.snapshot_at.strftime('%Y-%m-%d')}):")
        if fund.current_price:
            parts.append(f"  Price: ${fund.current_price:.2f}")
        if fund.pe_trailing:
            parts.append(f"  P/E (trailing): {fund.pe_trailing:.1f}")
        if fund.pe_forward:
            parts.append(f"  P/E (forward): {fund.pe_forward:.1f}")
        if fund.eps_trailing:
            parts.append(f"  EPS (trailing): {fund.eps_trailing:.2f}")
        if fund.beta:
            parts.append(f"  Beta: {fund.beta:.2f}")
        if fund.dividend_yield:
            parts.append(f"  Dividend yield: {fund.dividend_yield:.2%}")
        if fund.fifty_two_week_high and fund.fifty_two_week_low:
            parts.append(f"  52w range: ${fund.fifty_two_week_low:.2f} — ${fund.fifty_two_week_high:.2f}")
        if fund.market_cap:
            parts.append(f"  Market cap: ${fund.market_cap:,.0f}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    matches = (
        SignalMatch.query.filter(
            SignalMatch.company_id == company.id,
            SignalMatch.detected_at >= cutoff,
        )
        .order_by(SignalMatch.detected_at.desc())
        .limit(15)
        .all()
    )
    if matches:
        parts.append(f"\nRecent signals ({len(matches)}, last 7 days):")
        for m in matches:
            parts.append(
                f"  - {m.signal.name} ({m.direction}, {m.confidence:.0%}) "
                f"at {m.detected_at.strftime('%Y-%m-%d %H:%M')}"
            )

    from sqlalchemy import func
    pred = (
        Prediction.query.filter_by(company_id=company.id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    if pred:
        mag = f", magnitude {pred.magnitude:.0%}" if pred.magnitude else ""
        parts.append(
            f"\nLatest prediction: {pred.direction} ({pred.confidence:.0%}{mag})"
            f"\n  Reasoning: {(pred.reasoning or '')[:300]}"
            f"\n  Updated: {pred.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

    prices = (
        PriceHistory.query.filter(
            PriceHistory.company_id == company.id,
            PriceHistory.timestamp >= cutoff,
        )
        .order_by(PriceHistory.timestamp.desc())
        .limit(10)
        .all()
    )
    if prices:
        latest = prices[0]
        oldest = prices[-1]
        change = (latest.close - oldest.open) / oldest.open * 100 if oldest.open else 0
        parts.append(
            f"\nPrice action (7d): ${oldest.open:.2f} -> ${latest.close:.2f} ({change:+.2f}%)"
            f"\n  Latest: ${latest.close:.2f} (vol: {latest.volume:,.0f})"
        )

    return "\n".join(parts)


@tool
def get_trends() -> str:
    """Get the current trending topics across all tracked companies.

    Returns:
        Up to 10 trending topics with headlines, impact statements, and associated companies.
    """
    snapshot = TrendSnapshot.query.order_by(TrendSnapshot.generated_at.desc()).first()
    if not snapshot or not snapshot.trends:
        return "No trending topics available yet."

    parts = [f"Trending topics (as of {snapshot.generated_at.strftime('%Y-%m-%d %H:%M')}):\n"]
    for t in snapshot.trends[:10]:
        companies = ", ".join(t.get("companies", []))
        parts.append(
            f"#{t.get('rank', '?')}: {t.get('headline', 'No headline')}\n"
            f"  Impact: {t.get('impact', 'N/A')}\n"
            f"  Companies: {companies}\n"
            f"  Span: {t.get('first_seen', '?')} to {t.get('latest', '?')}\n"
        )
    return "\n".join(parts)


@tool
def get_market_brief() -> str:
    """Get the latest market brief summary.

    Returns:
        The most recent market brief with timestamp.
    """
    report = Report.query.order_by(Report.generated_at.desc()).first()
    if not report or not report.summary:
        return "No market brief available yet."

    return (
        f"Market Brief (updated {report.generated_at.strftime('%Y-%m-%d %H:%M')}):\n\n"
        f"{report.summary}"
    )


@tool
def get_signal_weights() -> str:
    """Get the signal accuracy rubric — operative accuracy for all active signals.

    Returns:
        List of all active signals with their accuracy scores and sample sizes.
    """
    signals = Signal.query.filter_by(active=True).order_by(Signal.signal_type, Signal.name).all()
    if not signals:
        return "No active signals found."

    parts = ["Signal accuracy rubric:\n"]
    for s in signals:
        parts.append(
            f"  {s.name} ({s.direction}, {s.signal_type}): "
            f"accuracy={s.operative_accuracy:.1%}, samples={s.total_samples}"
        )
    return "\n".join(parts)


LINKY_TOOLS = [research_company, get_company_profile, get_trends, get_market_brief, get_signal_weights]
