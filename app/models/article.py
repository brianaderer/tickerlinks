from app.extensions import db
from datetime import datetime, timezone


article_companies = db.Table(
    "article_companies",
    db.Column("article_id", db.Integer, db.ForeignKey("news_articles.id"), primary_key=True),
    db.Column("company_id", db.Integer, db.ForeignKey("companies.id"), primary_key=True),
    db.Column("sentiment", db.String(10)),
    db.Column("relevance", db.String(10)),
)


class NewsArticle(db.Model):
    __tablename__ = "news_articles"

    id = db.Column(db.Integer, primary_key=True)
    feed_source_id = db.Column(
        db.Integer, db.ForeignKey("feed_sources.id"), nullable=False, index=True
    )
    title = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    url = db.Column(db.Text, unique=True, nullable=False)
    author = db.Column(db.String(255))
    source_name = db.Column(db.String(255))
    full_text = db.Column(db.Text)
    processed = db.Column(db.Boolean, default=False, nullable=False)
    published_at = db.Column(db.DateTime(timezone=True))
    fetched_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    companies = db.relationship("Company", secondary=article_companies, backref="articles")

    def __repr__(self):
        return f"<Article {self.title[:50]}>"
