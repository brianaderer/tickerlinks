from app.extensions import db
from datetime import datetime, timezone


class InsiderTrade(db.Model):
    __tablename__ = "insider_trades"
    __table_args__ = (
        db.Index("ix_insider_company_date", "company_id", "transaction_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True
    )
    filer_name = db.Column(db.String(255), nullable=False)
    filer_title = db.Column(db.String(255))
    transaction_type = db.Column(db.String(50), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    price_per_share = db.Column(db.Float)
    total_value = db.Column(db.Float)
    transaction_date = db.Column(db.Date, nullable=False)
    filing_url = db.Column(db.Text, nullable=False, index=True)
    fetched_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company = db.relationship("Company", backref=db.backref("insider_trades", lazy="dynamic"))

    def __repr__(self):
        return f"<InsiderTrade {self.filer_name} {self.transaction_type} {self.company.symbol}>"
