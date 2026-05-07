from app.extensions import db
from app.models.signal_match import prediction_match
from datetime import datetime, timezone


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True
    )
    direction = db.Column(db.String(10), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    magnitude = db.Column(db.Float, nullable=True)
    reasoning = db.Column(db.Text)
    target_date = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company = db.relationship("Company", backref=db.backref("predictions", lazy="dynamic"))
    signal_matches = db.relationship(
        "SignalMatch", secondary=prediction_match, backref="predictions"
    )
    backtest = db.relationship("Backtest", backref="prediction", uselist=False)

    def __repr__(self):
        return f"<Prediction {self.company.symbol} {self.direction}>"
