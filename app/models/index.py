from app.extensions import db
from datetime import datetime, timezone

company_index = db.Table(
    "company_index",
    db.Column("company_id", db.Integer, db.ForeignKey("companies.id"), primary_key=True),
    db.Column("index_id", db.Integer, db.ForeignKey("indexes.id"), primary_key=True),
)


class Index(db.Model):
    __tablename__ = "indexes"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    companies = db.relationship(
        "Company", secondary=company_index, back_populates="indexes"
    )

    def __repr__(self):
        return f"<Index {self.symbol}>"
