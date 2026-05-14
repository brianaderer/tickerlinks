from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from sqlalchemy import func

from app.extensions import db
from app.models import (
    Company, Fundamentals, PriceHistory, SignalMatch, Prediction,
    Signal, Report, TrendSnapshot, SignalDigest,
)
from app.signals.research import research_company  # re-export existing tool

TICKERBETS_DISCLAIMER = (
    "Tickerbets provides experimental, model-based price estimates derived from historical data patterns. "
    "These outputs are not financial advice, investment recommendations, or guarantees of future performance, "
    "and should not be the sole basis for trading decisions."
)
_RANKINGS_CACHE_TTL_SECONDS = 120
_RANKINGS_CACHE: dict[str, tuple[datetime, dict]] = {}


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
    latest_match_subq = (
        db.session.query(
            func.max(SignalMatch.id).label("max_id"),
        )
        .filter(SignalMatch.detected_at >= cutoff)
        .group_by(
            SignalMatch.company_id,
            SignalMatch.signal_id,
            SignalMatch.direction,
            func.coalesce(SignalMatch.source_at, SignalMatch.detected_at),
        )
        .subquery()
    )
    matches = (
        SignalMatch.query.join(latest_match_subq, SignalMatch.id == latest_match_subq.c.max_id)
        .filter(SignalMatch.company_id == company.id)
        .order_by(SignalMatch.source_at.desc().nullslast(), SignalMatch.detected_at.desc())
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


def _resolve_tickerbets_target_date(target_date: str, horizon_days: int) -> str:
    if target_date:
        return target_date
    try:
        days = int(horizon_days)
    except (TypeError, ValueError):
        days = 1
    days = max(1, min(days, 10))
    from app.tickerbets.service import available_target_dates

    dates = available_target_dates(min_days_ahead=1, max_days_ahead=10)
    if dates:
        idx = min(days - 1, len(dates) - 1)
        return dates[idx].isoformat()
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _fetch_tickerbets_prediction(symbol: str, target_date: str, run_id: str = "") -> dict:
    from app.tickerbets.service import generate_bet_prediction

    return generate_bet_prediction(
        symbol=symbol,
        target_date=target_date,
        run_id=(run_id or None),
    )


def _tickerbets_rankings_cache_key(target_date: str, horizon_days: int, run_id: str) -> str:
    return f"{target_date}|{horizon_days}|{run_id or 'latest'}"


def _get_tickerbets_rankings(target_date: str, horizon_days: int, run_id: str = "") -> dict:
    requested_target = _resolve_tickerbets_target_date(target_date, horizon_days)
    cache_key = _tickerbets_rankings_cache_key(requested_target, horizon_days, run_id)
    now = datetime.now(timezone.utc)
    cached = _RANKINGS_CACHE.get(cache_key)
    if cached:
        ts, payload = cached
        if (now - ts).total_seconds() <= _RANKINGS_CACHE_TTL_SECONDS:
            return payload

    rows = []
    companies = Company.query.filter_by(active=True).order_by(Company.symbol.asc()).all()
    for company in companies:
        try:
            result = _fetch_tickerbets_prediction(
                symbol=company.symbol,
                target_date=requested_target,
                run_id=run_id,
            )
        except Exception:
            continue

        rows.append(
            {
                "symbol": company.symbol,
                "delta_pct": float(result.get("predicted_delta_pct", 0.0)),
                "delta": float(result.get("predicted_delta", 0.0)),
                "current_price": float(result.get("current_price", 0.0)),
                "predicted_price": float(result.get("predicted_price", 0.0)),
                "resolved_target_date": result.get("resolved_target_date"),
                "horizon_days": int(result.get("horizon_days", horizon_days)),
                "run_id": result.get("run_id", ""),
            }
        )

    rows.sort(key=lambda r: r["delta_pct"])
    payload = {
        "requested_target_date": requested_target,
        "computed_at": now.isoformat(),
        "count": len(rows),
        "rows": rows,
    }
    _RANKINGS_CACHE[cache_key] = (now, payload)
    return payload


def _lookup_company(symbol: str):
    return Company.query.filter_by(symbol=symbol.upper()).first()


def _get_recent_overlay_context(company_id: int) -> dict:
    latest_prediction = (
        Prediction.query.filter_by(company_id=company_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    dedup_subq = (
        db.session.query(func.max(SignalMatch.id).label("max_id"))
        .filter(SignalMatch.company_id == company_id, SignalMatch.detected_at >= cutoff)
        .group_by(
            SignalMatch.company_id,
            SignalMatch.signal_id,
            SignalMatch.direction,
            func.coalesce(SignalMatch.source_at, SignalMatch.detected_at),
        )
        .subquery()
    )
    matches = (
        SignalMatch.query.join(dedup_subq, SignalMatch.id == dedup_subq.c.max_id)
        .order_by(SignalMatch.source_at.desc().nullslast(), SignalMatch.detected_at.desc())
        .all()
    )
    bullish_signal_score = sum(float(m.confidence) for m in matches if m.direction == "bullish")
    bearish_signal_score = sum(float(m.confidence) for m in matches if m.direction == "bearish")

    prices = (
        PriceHistory.query.filter(
            PriceHistory.company_id == company_id,
            PriceHistory.timestamp >= cutoff,
        )
        .order_by(PriceHistory.timestamp.asc())
        .all()
    )
    price_change_7d_pct = None
    if len(prices) >= 2 and prices[0].open and prices[-1].close:
        base = float(prices[0].open)
        if base > 0:
            price_change_7d_pct = (float(prices[-1].close) - base) / base

    return {
        "latest_prediction": latest_prediction,
        "signal_count_7d": len(matches),
        "bullish_signal_score": bullish_signal_score,
        "bearish_signal_score": bearish_signal_score,
        "price_change_7d_pct": price_change_7d_pct,
    }


def _direction_from_delta(delta: float) -> str:
    if delta > 0:
        return "bullish"
    if delta < 0:
        return "bearish"
    return "flat"


@tool
def ticker_bets(
    symbol: str,
    target_date: str = "",
    horizon_days: int = 1,
    run_id: str = "",
    include_model_metrics: bool = False,
    include_directional_accuracy: bool = False,
) -> str:
    """Get an experimental 1-10 day model-based price estimate for a ticker.

    Use this tool when users ask for short-horizon price targets, expected move by date,
    or to compare quant model output with signal/LLM narrative. You can call it proactively
    in those contexts.

    Args:
        symbol: Ticker symbol (e.g. "AAPL")
        target_date: Optional ISO date (YYYY-MM-DD) for target day (must resolve to 1-10 days ahead)
        horizon_days: Optional fallback horizon when target_date is omitted (1-10)
        run_id: Optional specific model run id to use
        include_model_metrics: Include MAE/RMSE/R² metrics if True
        include_directional_accuracy: Include directional accuracy when metrics are included

    Returns:
        TickerBets estimate, always including a disclaimer.
    """
    symbol = (symbol or "").upper().strip()
    if not symbol:
        return f"TickerBets unavailable: missing symbol.\n\nDisclaimer: {TICKERBETS_DISCLAIMER}"

    requested_target = _resolve_tickerbets_target_date(target_date, horizon_days)

    try:
        result = _fetch_tickerbets_prediction(symbol=symbol, target_date=requested_target, run_id=run_id)
    except Exception as exc:
        return f"TickerBets unavailable for {symbol}: {exc}\n\nDisclaimer: {TICKERBETS_DISCLAIMER}"

    metrics = result.get("metrics", {})
    tb_direction = _direction_from_delta(float(result.get("predicted_delta", 0.0)))
    parts = [
        (
            f"TickerBets estimate for {result['symbol']} "
            f"(horizon {result['horizon_days']}D, target {result['resolved_target_date']}):"
        ),
        (
            f"  Current: ${float(result['current_price']):.2f} | "
            f"Predicted: ${float(result['predicted_price']):.2f} | "
            f"Delta: {float(result['predicted_delta']):+.2f} "
            f"({float(result['predicted_delta_pct']) * 100:+.2f}%)"
        ),
        f"  Directional call: {tb_direction}",
        (
            f"  Run: {result['run_id']} | "
            f"Requested date: {result['requested_target_date']} | "
            f"As-of: {result['as_of']}"
        ),
    ]
    if metrics and include_model_metrics:
        metrics_line = (
            f"  Metrics: MAE {float(metrics.get('mae', 0.0)):.4f}, "
            f"RMSE {float(metrics.get('rmse', 0.0)):.4f}, "
            f"R² {float(metrics.get('r2', 0.0)):.4f}"
        )
        if include_directional_accuracy and "directional_accuracy" in metrics:
            metrics_line += f", Directional Acc {float(metrics['directional_accuracy']) * 100:.2f}%"
        parts.append(metrics_line)

    parts.append(f"\nDisclaimer: {TICKERBETS_DISCLAIMER}")
    return "\n".join(parts)


@tool
def ticker_bets_rankings(
    target_date: str = "",
    horizon_days: int = 5,
    limit: int = 5,
    direction: str = "both",
    run_id: str = "",
) -> str:
    """Rank most bullish/bearish tickers by TickerBets predicted move for a given near-term horizon.

    Use this tool when users ask: "most bullish", "most bearish", "best/worst in 1-10 days",
    or any cross-universe leaderboard based on TickerBets.

    Args:
        target_date: Optional ISO target date (YYYY-MM-DD). If omitted, use horizon_days.
        horizon_days: Fallback horizon in days (1-10) when target_date is omitted.
        limit: Number of rows per side (max 20).
        direction: "both", "bullish", or "bearish".
        run_id: Optional specific model run id.

    Returns:
        Grounded bullish/bearish rankings with disclaimer.
    """
    limit = max(1, min(int(limit or 5), 20))
    direction = (direction or "both").strip().lower()
    if direction not in {"both", "bullish", "bearish"}:
        direction = "both"

    try:
        rankings = _get_tickerbets_rankings(target_date=target_date, horizon_days=horizon_days, run_id=run_id)
    except Exception as exc:
        return f"TickerBets rankings unavailable: {exc}\n\nDisclaimer: {TICKERBETS_DISCLAIMER}"

    rows = rankings.get("rows", [])
    if not rows:
        return f"TickerBets rankings unavailable: no predictions produced.\n\nDisclaimer: {TICKERBETS_DISCLAIMER}"

    target = rows[0].get("resolved_target_date") or rankings.get("requested_target_date")
    run = rows[0].get("run_id", "")
    horizon = rows[0].get("horizon_days", horizon_days)
    bearish = rows[:limit]
    bullish = list(reversed(rows[-limit:]))

    parts = [
        (
            f"TickerBets {horizon}D rankings for target {target} "
            f"(universe size {rankings.get('count', len(rows))}, run {run}):"
        )
    ]

    if direction in {"both", "bullish"}:
        parts.append("\nMost bullish:")
        for r in bullish:
            parts.append(
                f"  - {r['symbol']}: {r['delta_pct'] * 100:+.2f}% "
                f"(${r['current_price']:.2f} -> ${r['predicted_price']:.2f})"
            )

    if direction in {"both", "bearish"}:
        parts.append("\nMost bearish:")
        for r in bearish:
            parts.append(
                f"  - {r['symbol']}: {r['delta_pct'] * 100:+.2f}% "
                f"(${r['current_price']:.2f} -> ${r['predicted_price']:.2f})"
            )

    parts.append(f"\nDisclaimer: {TICKERBETS_DISCLAIMER}")
    return "\n".join(parts)


@tool
def ticker_bets_overlay(
    symbol: str,
    target_date: str = "",
    horizon_days: int = 1,
    run_id: str = "",
    include_directional_accuracy: bool = False,
) -> str:
    """Overlay TickerBets with latest prediction, signals, and price action for a direct verdict.

    Use this when users ask whether TickerBets is likely right/wrong, agree/disagree with it,
    or explicitly ask for an overlay/reconciliation with other TickerLinks data sources.

    Args:
        symbol: Ticker symbol (e.g. "AAPL")
        target_date: Optional ISO date (YYYY-MM-DD), preferred when user specifies a date
        horizon_days: Optional fallback horizon (1-10) when target_date is omitted
        run_id: Optional model run id to pin analysis
        include_directional_accuracy: Include directional accuracy in the overlay summary if True

    Returns:
        A direct verdict (supports/mixed/conflicts) plus supporting evidence and disclaimer.
    """
    symbol = (symbol or "").upper().strip()
    if not symbol:
        return f"TickerBets overlay unavailable: missing symbol.\n\nDisclaimer: {TICKERBETS_DISCLAIMER}"

    company = _lookup_company(symbol)
    if not company:
        return f"TickerBets overlay unavailable: company {symbol} not found.\n\nDisclaimer: {TICKERBETS_DISCLAIMER}"

    requested_target = _resolve_tickerbets_target_date(target_date, horizon_days)
    try:
        tb = _fetch_tickerbets_prediction(symbol=symbol, target_date=requested_target, run_id=run_id)
    except Exception as exc:
        return f"TickerBets overlay unavailable for {symbol}: {exc}\n\nDisclaimer: {TICKERBETS_DISCLAIMER}"

    ctx = _get_recent_overlay_context(company.id)
    tb_dir = _direction_from_delta(float(tb.get("predicted_delta", 0.0)))
    support = 0.0
    oppose = 0.0
    evidence = []

    pred = ctx.get("latest_prediction")
    if pred:
        pred_dir = str(pred.direction or "").lower()
        pred_conf = float(pred.confidence or 0.5)
        if pred_dir == tb_dir:
            support += pred_conf
            evidence.append(f"Latest prediction aligns: {pred_dir} ({pred_conf:.0%})")
        elif pred_dir in {"bullish", "bearish"} and tb_dir in {"bullish", "bearish"}:
            oppose += pred_conf
            evidence.append(f"Latest prediction conflicts: {pred_dir} ({pred_conf:.0%})")
    else:
        evidence.append("No recent prediction available for comparison")

    bull_score = float(ctx.get("bullish_signal_score") or 0.0)
    bear_score = float(ctx.get("bearish_signal_score") or 0.0)
    signal_total = bull_score + bear_score
    signal_count = int(ctx.get("signal_count_7d") or 0)
    if signal_total > 0:
        signal_margin = abs(bull_score - bear_score) / signal_total
        signal_dir = "bullish" if bull_score > bear_score else "bearish" if bear_score > bull_score else "mixed"
        if signal_dir == tb_dir:
            support += signal_margin
            evidence.append(
                f"Signal balance aligns ({signal_count} matches, bull={bull_score:.2f}, bear={bear_score:.2f})"
            )
        elif signal_dir in {"bullish", "bearish"} and tb_dir in {"bullish", "bearish"}:
            oppose += signal_margin
            evidence.append(
                f"Signal balance conflicts ({signal_count} matches, bull={bull_score:.2f}, bear={bear_score:.2f})"
            )
        else:
            evidence.append(
                f"Signal balance mixed ({signal_count} matches, bull={bull_score:.2f}, bear={bear_score:.2f})"
            )
    else:
        evidence.append("No recent directional signal balance available")

    momentum = ctx.get("price_change_7d_pct")
    if momentum is not None:
        momentum = float(momentum)
        if momentum > 0:
            mom_dir = "bullish"
        elif momentum < 0:
            mom_dir = "bearish"
        else:
            mom_dir = "flat"
        mom_weight = min(abs(momentum) / 0.05, 0.6)
        if mom_dir == tb_dir:
            support += mom_weight
            evidence.append(f"7-day price momentum aligns ({momentum:+.2%})")
        elif mom_dir in {"bullish", "bearish"} and tb_dir in {"bullish", "bearish"}:
            oppose += mom_weight
            evidence.append(f"7-day price momentum conflicts ({momentum:+.2%})")
        else:
            evidence.append(f"7-day price momentum neutral ({momentum:+.2%})")

    net = support - oppose
    if net >= 0.35:
        verdict = "supports"
    elif net <= -0.35:
        verdict = "conflicts"
    else:
        verdict = "mixed"

    strength = abs(net)
    if strength >= 0.9:
        confidence_tier = "high"
    elif strength >= 0.45:
        confidence_tier = "moderate"
    else:
        confidence_tier = "low"

    directional_acc = float((tb.get("metrics") or {}).get("directional_accuracy", 0.0))
    tickerbets_line = (
        f"  TickerBets: {_direction_from_delta(float(tb['predicted_delta']))} "
        f"{float(tb['predicted_delta_pct']) * 100:+.2f}% by {tb['resolved_target_date']}"
    )
    if include_directional_accuracy:
        tickerbets_line += f" (directional acc {directional_acc * 100:.2f}%)"
    parts = [
        (
            f"TickerBets overlay for {symbol}: verdict={verdict} "
            f"({confidence_tier} confidence)"
        ),
        tickerbets_line,
        f"  Evidence score: support {support:.2f} vs oppose {oppose:.2f} (net {net:+.2f})",
        "  Key evidence:",
    ]
    parts.extend([f"    - {line}" for line in evidence[:5]])
    parts.append(f"\nDisclaimer: {TICKERBETS_DISCLAIMER}")
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
        dedup_subq = (
            db.session.query(
                func.max(SignalMatch.id).label("max_id"),
            )
            .filter(SignalMatch.detected_at >= cutoff)
            .group_by(
                SignalMatch.company_id,
                SignalMatch.signal_id,
                SignalMatch.direction,
                func.coalesce(SignalMatch.source_at, SignalMatch.detected_at),
            )
            .subquery()
        )
        query = (
            db.session.query(
                SignalMatch.company_id,
                func.count(SignalMatch.id).label("cnt"),
            )
            .join(dedup_subq, SignalMatch.id == dedup_subq.c.max_id)
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


LINKY_TOOLS = [
    research_company,
    get_company_profile,
    get_trends,
    get_market_brief,
    get_signal_weights,
    ticker_bets,
    ticker_bets_rankings,
    ticker_bets_overlay,
    screen_stocks,
]
