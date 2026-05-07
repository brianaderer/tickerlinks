from flask import jsonify, request

from app.api import bp
from app.models import (
    Company, PriceHistory, FeedSource, NewsArticle, Index,
    Signal, SignalMatch, Prediction, Report,
)
from app.articles.processor import search_articles, get_sentiment_index
from app.articles.indices import all_indices


@bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@bp.route("/indexes")
def list_indexes():
    indexes = Index.query.order_by(Index.symbol).all()
    return jsonify(
        [
            {
                "id": i.id,
                "symbol": i.symbol,
                "name": i.name,
                "company_count": len(i.companies),
            }
            for i in indexes
        ]
    )


@bp.route("/companies")
def list_companies():
    index_filter = request.args.get("index")
    query = Company.query.filter_by(active=True)

    if index_filter:
        idx = Index.query.filter_by(symbol=index_filter.upper()).first_or_404()
        query = query.filter(Company.indexes.contains(idx))

    companies = query.order_by(Company.symbol).all()
    return jsonify(
        [
            {
                "id": c.id,
                "symbol": c.symbol,
                "name": c.name,
                "sector": c.sector,
                "industry": c.industry,
                "market_cap": c.market_cap,
                "description": c.description,
                "indexes": [i.symbol for i in c.indexes],
            }
            for c in companies
        ]
    )


@bp.route("/companies/<symbol>/prices")
def company_prices(symbol):
    company = Company.query.filter_by(symbol=symbol.upper()).first_or_404()
    limit = request.args.get("limit", 100, type=int)
    prices = (
        PriceHistory.query.filter_by(company_id=company.id)
        .order_by(PriceHistory.timestamp.desc())
        .limit(limit)
        .all()
    )
    return jsonify(
        [
            {
                "timestamp": p.timestamp.isoformat(),
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
            }
            for p in prices
        ]
    )


@bp.route("/feeds")
def list_feeds():
    sources = FeedSource.query.order_by(FeedSource.name).all()
    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "url": s.url,
                "source_type": s.source_type,
                "active": s.active,
                "last_polled": s.last_polled.isoformat() if s.last_polled else None,
            }
            for s in sources
        ]
    )


@bp.route("/articles")
def list_articles():
    limit = request.args.get("limit", 50, type=int)
    company_filter = request.args.get("company")

    query = NewsArticle.query.order_by(NewsArticle.published_at.desc())
    if company_filter:
        company = Company.query.filter_by(
            symbol=company_filter.upper()
        ).first_or_404()
        query = query.filter_by(company_id=company.id)

    articles = query.limit(limit).all()
    return jsonify(
        [
            {
                "id": a.id,
                "title": a.title,
                "summary": a.summary[:200] if a.summary else None,
                "url": a.url,
                "source_name": a.source_name,
                "company": a.company.symbol if a.company else None,
                "published_at": a.published_at.isoformat()
                if a.published_at
                else None,
            }
            for a in articles
        ]
    )


@bp.route("/signals")
def list_signals():
    signals = Signal.query.filter_by(active=True).order_by(Signal.signal_type, Signal.name).all()
    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "description": s.description,
                "parameters": s.parameters,
                "historical_accuracy": s.historical_accuracy,
                "sample_size": s.sample_size,
                "weight": s.historical_accuracy if s.historical_accuracy and s.historical_accuracy > 0 else 0.5,
                "match_count": s.matches.count(),
            }
            for s in signals
        ]
    )


@bp.route("/signals/matches")
def list_signal_matches():
    limit = request.args.get("limit", 50, type=int)
    company_filter = request.args.get("company")
    signal_type = request.args.get("type")

    query = SignalMatch.query.order_by(SignalMatch.detected_at.desc())
    if company_filter:
        company = Company.query.filter_by(
            symbol=company_filter.upper()
        ).first_or_404()
        query = query.filter_by(company_id=company.id)
    if signal_type:
        query = query.join(Signal).filter(Signal.signal_type == signal_type)

    matches = query.limit(limit).all()
    return jsonify(
        [
            {
                "id": m.id,
                "signal": m.signal.name,
                "signal_type": m.signal.signal_type,
                "company": m.company.symbol,
                "direction": m.direction,
                "confidence": m.confidence,
                "context": m.context,
                "detected_at": m.detected_at.isoformat(),
            }
            for m in matches
        ]
    )


@bp.route("/predictions")
def list_predictions():
    limit = request.args.get("limit", 50, type=int)
    company_filter = request.args.get("company")
    direction_filter = request.args.get("direction")

    query = Prediction.query.order_by(Prediction.created_at.desc())
    if company_filter:
        company = Company.query.filter_by(
            symbol=company_filter.upper()
        ).first_or_404()
        query = query.filter_by(company_id=company.id)
    if direction_filter:
        query = query.filter_by(direction=direction_filter.lower())

    predictions = query.limit(limit).all()
    return jsonify(
        [
            {
                "id": p.id,
                "company": p.company.symbol,
                "direction": p.direction,
                "confidence": p.confidence,
                "reasoning": p.reasoning,
                "target_date": p.target_date.isoformat() if p.target_date else None,
                "created_at": p.created_at.isoformat(),
                "signal_count": len(p.signal_matches),
            }
            for p in predictions
        ]
    )


@bp.route("/articles/search")
def search_articles_route():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    n = request.args.get("limit", 10, type=int)
    company = request.args.get("company")

    results = search_articles(query, n_results=n, company=company)

    for hit in results:
        article = NewsArticle.query.get(hit["article_id"])
        if article:
            hit["url"] = article.url
            hit["full_summary"] = article.summary

    return jsonify(results)


@bp.route("/sentiment")
def sentiment_index():
    symbol = request.args.get("symbol")
    limit = request.args.get("limit", 50, type=int)
    results = get_sentiment_index(symbol=symbol, limit=limit)
    return jsonify(results)


@bp.route("/indices")
def indices():
    symbol = request.args.get("symbol")
    results = all_indices(symbol=symbol)
    return jsonify(results)


@bp.route("/signals/weights")
def signal_weights():
    signals = Signal.query.filter_by(active=True).order_by(Signal.signal_type, Signal.name).all()
    return jsonify([
        {
            "signal": s.name,
            "direction": s.direction,
            "signal_type": s.signal_type,
            "weight": round(s.operative_accuracy, 4),
            "sample_size": s.total_samples,
            "snapshots": len(s.accuracy_snapshots or []),
        }
        for s in signals
    ])


@bp.route("/reports")
def list_reports():
    limit = request.args.get("limit", 20, type=int)
    reports = Report.query.order_by(Report.generated_at.desc()).limit(limit).all()
    return jsonify([
        {
            "id": r.id,
            "report_type": r.report_type,
            "generated_at": r.generated_at.isoformat(),
            "summary": r.summary,
        }
        for r in reports
    ])


@bp.route("/reports/latest")
def latest_report():
    report = Report.query.order_by(Report.generated_at.desc()).first()
    if not report:
        return jsonify({"error": "No reports yet"}), 404
    return jsonify({
        "id": report.id,
        "report_type": report.report_type,
        "generated_at": report.generated_at.isoformat(),
        "summary": report.summary,
        "data": report.data,
    })


@bp.route("/reports/<int:report_id>")
def get_report(report_id):
    report = Report.query.get_or_404(report_id)
    return jsonify({
        "id": report.id,
        "report_type": report.report_type,
        "generated_at": report.generated_at.isoformat(),
        "summary": report.summary,
        "data": report.data,
    })
