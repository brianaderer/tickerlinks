from app.extensions import db
from datetime import datetime, timezone


class NewsArticle(db.Model):
    __tablename__ = "news_articles"
    __table_args__ = (
        db.Index("ix_article_company_pub", "company_id", "published_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id"), nullable=True, index=True
    )
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

    def __repr__(self):
        return f"<Article {self.title[:50]}>"
