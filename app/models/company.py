from app.extensions import db
from app.models.index import company_index
from datetime import datetime, timezone


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    sector = db.Column(db.String(100))
    industry = db.Column(db.String(100))
    market_cap = db.Column(db.BigInteger)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    prices = db.relationship("PriceHistory", backref="company", lazy="dynamic")
    articles = db.relationship("NewsArticle", backref="company", lazy="dynamic")
    indexes = db.relationship(
        "Index", secondary=company_index, back_populates="companies"
    )

    def __repr__(self):
        return f"<Company {self.symbol}>"
