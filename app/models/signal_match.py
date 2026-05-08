from app.extensions import db
from datetime import datetime, timezone


prediction_match = db.Table(
    "prediction_match",
    db.Column(
        "prediction_id",
        db.Integer,
        db.ForeignKey("predictions.id"),
        primary_key=True,
    ),
    db.Column(
        "signal_match_id",
        db.Integer,
        db.ForeignKey("signal_matches.id"),
        primary_key=True,
    ),
)


class SignalMatch(db.Model):
    __tablename__ = "signal_matches"
    __table_args__ = (
        db.Index("ix_match_company_detected", "company_id", "detected_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    signal_id = db.Column(
        db.Integer, db.ForeignKey("signals.id"), nullable=False, index=True
    )
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True
    )
    confidence = db.Column(db.Float, nullable=False)
    direction = db.Column(db.String(10), nullable=False)
    context = db.Column(db.JSON, default=dict)
    run_id = db.Column(db.String(32), index=True)
    source_at = db.Column(db.DateTime(timezone=True), nullable=True)
    detected_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company = db.relationship("Company", backref=db.backref("signal_matches", lazy="dynamic"))

    def __repr__(self):
        return f"<SignalMatch {self.signal.name} on {self.company.symbol}>"
