from flask import jsonify, request

from app.api import bp
from app.extensions import db
from app.models import (
    Company, PriceHistory, FeedSource, NewsArticle, Index,
    Signal, SignalMatch, Prediction, Report, SignalDigest,
    TrendSnapshot, article_companies,
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


def _article_companies(article_id: int) -> list[dict]:
    rows = db.session.execute(
        article_companies.select().where(article_companies.c.article_id == article_id)
    ).fetchall()
    result = []
    for r in rows:
        comp = Company.query.get(r.company_id)
        if comp:
            result.append({
                "symbol": comp.symbol,
                "sentiment": r.sentiment,
                "relevance": r.relevance,
            })
    return result


@bp.route("/articles")
def list_articles():
    limit = request.args.get("limit", 50, type=int)
    company_filter = request.args.get("company")

    from sqlalchemy import func
    sort_col = func.coalesce(NewsArticle.published_at, NewsArticle.fetched_at)
    query = NewsArticle.query.filter(
        NewsArticle.content_source == "scraped"
    ).order_by(sort_col.desc())
    if company_filter:
        company = Company.query.filter_by(
            symbol=company_filter.upper()
        ).first_or_404()
        query = query.filter(
            NewsArticle.id == article_companies.c.article_id,
            article_companies.c.company_id == company.id,
        )

    articles = query.limit(limit).all()
    return jsonify(
        [
            {
                "id": a.id,
                "title": a.title,
                "summary": a.summary[:200] if a.summary else None,
                "url": a.url,
                "source_name": a.source_name,
                "content_source": a.content_source,
                "companies": _article_companies(a.id),
                "published_at": a.published_at.isoformat()
                if a.published_at
                else None,
                "fetched_at": a.fetched_at.isoformat()
                if a.fetched_at
                else None,
            }
            for a in articles
        ]
    )


@bp.route("/articles/<int:article_id>")
def get_article(article_id):
    a = NewsArticle.query.get_or_404(article_id)
    return jsonify({
        "id": a.id,
        "title": a.title,
        "summary": a.summary,
        "full_text": a.full_text,
        "url": a.url,
        "author": a.author,
        "source_name": a.source_name,
        "content_source": a.content_source,
        "companies": _article_companies(a.id),
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
    })


@bp.route("/articles/batch")
def batch_articles():
    ids_param = request.args.get("ids", "")
    if not ids_param:
        return jsonify([])
    try:
        ids = [int(x) for x in ids_param.split(",") if x.strip()]
    except ValueError:
        return jsonify([])

    articles = NewsArticle.query.filter(NewsArticle.id.in_(ids)).order_by(
        NewsArticle.published_at.desc()
    ).all()
    return jsonify([
        {
            "id": a.id,
            "title": a.title,
            "summary": a.summary[:200] if a.summary else None,
            "url": a.url,
            "source_name": a.source_name,
            "content_source": a.content_source,
            "companies": _article_companies(a.id),
            "published_at": a.published_at.isoformat() if a.published_at else None,
        }
        for a in articles
    ])


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
    from datetime import datetime, timedelta, timezone
    limit = request.args.get("limit", 50, type=int)
    company_filter = request.args.get("company")
    direction_filter = request.args.get("direction")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    from sqlalchemy import func
    latest_subq = (
        db.session.query(
            Prediction.company_id,
            func.max(Prediction.created_at).label("max_created"),
        )
        .group_by(Prediction.company_id)
        .subquery()
    )

    query = Prediction.query.join(
        latest_subq,
        (Prediction.company_id == latest_subq.c.company_id)
        & (Prediction.created_at == latest_subq.c.max_created),
    ).filter(Prediction.created_at >= cutoff).order_by(Prediction.created_at.desc())

    if company_filter:
        company = Company.query.filter_by(
            symbol=company_filter.upper()
        ).first_or_404()
        query = query.filter(Prediction.company_id == company.id)
    if direction_filter:
        query = query.filter(Prediction.direction == direction_filter.lower())

    predictions = query.limit(limit).all()
    return jsonify(
        [
            {
                "id": p.id,
                "company": p.company.symbol,
                "direction": p.direction,
                "confidence": p.confidence,
                "magnitude": p.magnitude,
                "reasoning": p.reasoning,
                "target_date": p.target_date.isoformat() if p.target_date else None,
                "created_at": p.created_at.isoformat(),
                "signal_count": len(p.signal_matches),
            }
            for p in predictions
            if len(p.signal_matches) > 0
        ]
    )


@bp.route("/predictions/<symbol>/run", methods=["POST"])
def run_prediction(symbol):
    company = Company.query.filter_by(symbol=symbol.upper()).first_or_404()
    from app.tasks.analyze import run_company_prediction
    run_company_prediction.delay(company.id)
    return jsonify({"status": "queued", "symbol": company.symbol}), 202


@bp.route("/articles/search/text")
def text_search_articles():
    """Fast text search via Typesense (no embeddings) for keystroke-level queries."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    n = request.args.get("limit", 20, type=int)

    from app.articles.processor import get_typesense_client, ensure_collection, COLLECTION_NAME
    client = get_typesense_client()
    ensure_collection()

    search_params = {
        "q": query,
        "query_by": "title,document",
        "query_by_weights": "3,1",
        "per_page": n * 3,
        "include_fields": "article_id,title,source_name,published_at",
    }

    results = client.collections[COLLECTION_NAME].documents.search(search_params)

    hits = []
    seen = set()
    for hit in results.get("hits", []):
        doc = hit["document"]
        article_id = doc["article_id"]
        if article_id in seen:
            continue
        seen.add(article_id)
        article = NewsArticle.query.get(article_id)
        if not article:
            continue
        hits.append({
            "id": article.id,
            "title": article.title,
            "summary": article.summary[:200] if article.summary else None,
            "url": article.url,
            "source_name": article.source_name,
            "content_source": article.content_source,
            "companies": [],
            "published_at": article.published_at.isoformat() if article.published_at else None,
        })
        if len(hits) >= n:
            break

    return jsonify(hits)


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


@bp.route("/signals/digests")
def signal_digests():
    from sqlalchemy import func

    latest_subq = (
        db.session.query(
            SignalDigest.company_id,
            func.max(SignalDigest.generated_at).label("max_gen"),
        )
        .group_by(SignalDigest.company_id)
        .subquery()
    )

    digests = SignalDigest.query.join(
        latest_subq,
        (SignalDigest.company_id == latest_subq.c.company_id)
        & (SignalDigest.generated_at == latest_subq.c.max_gen),
    ).order_by(SignalDigest.net_confidence.desc()).limit(20).all()

    return jsonify([
        {
            "symbol": d.company.symbol,
            "direction": d.direction,
            "net_confidence": d.net_confidence,
            "match_count": d.match_count,
            "digest": d.digest,
            "matches": d.matches,
            "generated_at": d.generated_at.isoformat(),
        }
        for d in digests
    ])


@bp.route("/trends")
def get_trends():
    snapshot = TrendSnapshot.query.order_by(TrendSnapshot.generated_at.desc()).first()
    if not snapshot:
        return jsonify({"generated_at": None, "trends": []})
    return jsonify({
        "generated_at": snapshot.generated_at.isoformat(),
        "trends": snapshot.trends or [],
    })


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
