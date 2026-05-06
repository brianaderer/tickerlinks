from app.extensions import db
from datetime import datetime, timezone


class Fundamentals(db.Model):
    __tablename__ = "fundamentals"
    __table_args__ = (
        db.Index("ix_fundamentals_company_snap", "company_id", "snapshot_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True
    )
    pe_trailing = db.Column(db.Float)
    pe_forward = db.Column(db.Float)
    eps_trailing = db.Column(db.Float)
    eps_forward = db.Column(db.Float)
    dividend_yield = db.Column(db.Float)
    beta = db.Column(db.Float)
    fifty_two_week_high = db.Column(db.Float)
    fifty_two_week_low = db.Column(db.Float)
    market_cap = db.Column(db.BigInteger)
    current_price = db.Column(db.Float)
    snapshot_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company = db.relationship("Company", backref=db.backref("fundamentals", lazy="dynamic"))

    def __repr__(self):
        return f"<Fundamentals {self.company.symbol} @ {self.snapshot_at}>"
