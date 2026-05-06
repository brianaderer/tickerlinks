from app.extensions import db
from datetime import datetime, timezone


class Signal(db.Model):
    __tablename__ = "signals"

    __table_args__ = (
        db.UniqueConstraint("name", "direction", name="uq_signal_name_direction"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    signal_type = db.Column(db.String(50), nullable=False, index=True)
    direction = db.Column(db.String(10), nullable=False, default="neutral")
    description = db.Column(db.Text)
    parameters = db.Column(db.JSON, default=dict)
    historical_accuracy = db.Column(db.Float, default=0.0)
    sample_size = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    matches = db.relationship("SignalMatch", backref="signal", lazy="dynamic")

    def __repr__(self):
        return f"<Signal {self.name}>"
