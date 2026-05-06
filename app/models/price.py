from app.extensions import db
from datetime import datetime, timezone


class PriceHistory(db.Model):
    __tablename__ = "price_history"
    __table_args__ = (
        db.UniqueConstraint("company_id", "timestamp", name="uq_company_timestamp"),
        db.Index("ix_price_company_ts", "company_id", "timestamp"),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True
    )
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float)
    volume = db.Column(db.BigInteger)
    dividends = db.Column(db.Float, default=0.0)
    stock_splits = db.Column(db.Float, default=0.0)
    fetched_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<Price {self.company.symbol} @ {self.timestamp}>"
