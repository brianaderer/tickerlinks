from app.extensions import db
from datetime import datetime, timezone


class Backtest(db.Model):
    __tablename__ = "backtests"

    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(
        db.Integer, db.ForeignKey("predictions.id"), unique=True, nullable=False
    )
    actual_direction = db.Column(db.String(10))
    actual_magnitude = db.Column(db.Float)
    accuracy_score = db.Column(db.Float)
    evaluated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<Backtest pred={self.prediction_id} score={self.accuracy_score}>"
