from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from sqlalchemy import func

from app.extensions import db
from app.models import (
    Company, Fundamentals, PriceHistory, SignalMatch, Prediction,
    Signal, Report, TrendSnapshot, SignalDigest,
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
            source_time = m.source_at or m.detected_at
            parts.append(
                f"  - {m.signal.name} ({m.direction}, {m.confidence:.0%}) "
                f"source: {source_time.strftime('%Y-%m-%d %H:%M')}"
            )

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
        vol_str = f"{latest.volume:,.0f}" if latest.volume is not None else "n/a"
        open_str = f"${oldest.open:.2f}" if oldest.open is not None else "n/a"
        close_str = f"${latest.close:.2f}" if latest.close is not None else "n/a"
        parts.append(
            f"\nPrice action (7d): {open_str} -> {close_str} ({change:+.2f}%)"
            f"\n  Latest: {close_str} (vol: {vol_str})"
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


@tool
def screen_stocks(sort_by: str = "prediction", direction: str = "bullish", limit: int = 10) -> str:
    """Screen and rank stocks across the entire tracked universe.

    Args:
        sort_by: Ranking criteria. One of "prediction" (highest confidence predictions),
                 "pe_forward" (lowest forward P/E), "dividend" (highest dividend yield),
                 "signals" (most recent signal matches), "momentum" (7-day price change).
        direction: Filter predictions/signals by direction: "bullish", "bearish", or "any".
        limit: Number of results to return (max 20).

    Returns:
        Ranked list of stocks matching the criteria.
    """
    limit = min(limit, 20)

    if sort_by == "prediction":
        latest_subq = (
            db.session.query(
                Prediction.company_id,
                func.max(Prediction.created_at).label("max_created"),
            )
            .group_by(Prediction.company_id)
            .subquery()
        )
        query = (
            Prediction.query.join(
                latest_subq,
                (Prediction.company_id == latest_subq.c.company_id)
                & (Prediction.created_at == latest_subq.c.max_created),
            )
        )
        if direction != "any":
            query = query.filter(Prediction.direction == direction)
        preds = query.order_by(Prediction.confidence.desc()).limit(limit).all()
        if not preds:
            return f"No {direction} predictions found."
        parts = [f"Top {len(preds)} {direction} predictions by confidence:\n"]
        for p in preds:
            mag = f", magnitude {p.magnitude:.0%}" if p.magnitude else ""
            parts.append(
                f"  {p.company.symbol}: {p.direction} {p.confidence:.0%}{mag}"
                f" — {(p.reasoning or '')[:120]}"
            )
        return "\n".join(parts)

    elif sort_by == "pe_forward":
        latest_subq = (
            db.session.query(
                Fundamentals.company_id,
                func.max(Fundamentals.snapshot_at).label("max_snap"),
            )
            .group_by(Fundamentals.company_id)
            .subquery()
        )
        funds = (
            Fundamentals.query.join(
                latest_subq,
                (Fundamentals.company_id == latest_subq.c.company_id)
                & (Fundamentals.snapshot_at == latest_subq.c.max_snap),
            )
            .filter(Fundamentals.pe_forward > 0)
            .order_by(Fundamentals.pe_forward.asc())
            .limit(limit)
            .all()
        )
        if not funds:
            return "No forward P/E data available."
        parts = [f"Top {len(funds)} stocks by lowest forward P/E:\n"]
        for f in funds:
            price = f"${f.current_price:.2f}" if f.current_price else "n/a"
            parts.append(
                f"  {f.company.symbol}: P/E(fwd) {f.pe_forward:.1f}, price {price}"
            )
        return "\n".join(parts)

    elif sort_by == "dividend":
        latest_subq = (
            db.session.query(
                Fundamentals.company_id,
                func.max(Fundamentals.snapshot_at).label("max_snap"),
            )
            .group_by(Fundamentals.company_id)
            .subquery()
        )
        funds = (
            Fundamentals.query.join(
                latest_subq,
                (Fundamentals.company_id == latest_subq.c.company_id)
                & (Fundamentals.snapshot_at == latest_subq.c.max_snap),
            )
            .filter(Fundamentals.dividend_yield > 0)
            .order_by(Fundamentals.dividend_yield.desc())
            .limit(limit)
            .all()
        )
        if not funds:
            return "No dividend data available."
        parts = [f"Top {len(funds)} stocks by dividend yield:\n"]
        for f in funds:
            parts.append(
                f"  {f.company.symbol}: yield {f.dividend_yield:.2%}"
                f", P/E(fwd) {f.pe_forward:.1f}" if f.pe_forward else ""
            )
        return "\n".join(parts)

    elif sort_by == "signals":
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        query = (
            db.session.query(
                SignalMatch.company_id,
                func.count(SignalMatch.id).label("cnt"),
            )
            .filter(SignalMatch.detected_at >= cutoff)
        )
        if direction != "any":
            query = query.filter(SignalMatch.direction == direction)
        rows = (
            query.group_by(SignalMatch.company_id)
            .order_by(func.count(SignalMatch.id).desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return f"No {direction} signal matches in the last 7 days."
        parts = [f"Top {len(rows)} stocks by {direction} signal count (7d):\n"]
        for company_id, cnt in rows:
            comp = Company.query.get(company_id)
            if comp:
                parts.append(f"  {comp.symbol}: {cnt} signals")
        return "\n".join(parts)

    elif sort_by == "momentum":
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        latest_subq = (
            db.session.query(
                PriceHistory.company_id,
                func.max(PriceHistory.timestamp).label("max_ts"),
            )
            .group_by(PriceHistory.company_id)
            .subquery()
        )
        oldest_subq = (
            db.session.query(
                PriceHistory.company_id,
                func.min(PriceHistory.timestamp).label("min_ts"),
            )
            .filter(PriceHistory.timestamp >= cutoff)
            .group_by(PriceHistory.company_id)
            .subquery()
        )
        companies = Company.query.filter_by(active=True).all()
        momentum = []
        for c in companies:
            latest = (
                PriceHistory.query.filter_by(company_id=c.id)
                .order_by(PriceHistory.timestamp.desc())
                .first()
            )
            oldest = (
                PriceHistory.query.filter(
                    PriceHistory.company_id == c.id,
                    PriceHistory.timestamp >= cutoff,
                )
                .order_by(PriceHistory.timestamp.asc())
                .first()
            )
            if latest and oldest and oldest.open and oldest.open > 0:
                change = (latest.close - oldest.open) / oldest.open
                momentum.append((c.symbol, change, latest.close))

        if direction == "bullish":
            momentum.sort(key=lambda x: x[1], reverse=True)
        elif direction == "bearish":
            momentum.sort(key=lambda x: x[1])
        else:
            momentum.sort(key=lambda x: abs(x[1]), reverse=True)

        momentum = momentum[:limit]
        if not momentum:
            return "No price data available for momentum ranking."
        parts = [f"Top {len(momentum)} stocks by 7-day momentum ({direction}):\n"]
        for sym, change, price in momentum:
            parts.append(f"  {sym}: {change:+.2%} (${price:.2f})")
        return "\n".join(parts)

    return f"Unknown sort_by value: {sort_by}. Use prediction, pe_forward, dividend, signals, or momentum."


LINKY_TOOLS = [research_company, get_company_profile, get_trends, get_market_brief, get_signal_weights, screen_stocks]
