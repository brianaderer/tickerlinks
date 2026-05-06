from app.extensions import db
from datetime import datetime, timezone


class FeedSource(db.Model):
    __tablename__ = "feed_sources"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.Text, unique=True, nullable=False)
    source_type = db.Column(db.String(50), nullable=False, default="rss")
    active = db.Column(db.Boolean, default=True, nullable=False)
    last_polled = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    articles = db.relationship("NewsArticle", backref="feed_source", lazy="dynamic")

    def __repr__(self):
        return f"<FeedSource {self.name}>"
