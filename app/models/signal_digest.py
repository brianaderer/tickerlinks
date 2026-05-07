from app.extensions import db
from datetime import datetime, timezone


class SignalDigest(db.Model):
    __tablename__ = "signal_digests"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    direction = db.Column(db.String(10), nullable=False)
    net_confidence = db.Column(db.Float, nullable=False)
    match_count = db.Column(db.Integer, nullable=False)
    digest = db.Column(db.Text, nullable=False)
    matches = db.Column(db.JSON, default=list)
    generated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    company = db.relationship("Company", backref="signal_digests")

    def __repr__(self):
        return f"<SignalDigest {self.company_id} {self.direction}>"
