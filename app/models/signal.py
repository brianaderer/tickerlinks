import math

from app.extensions import db
from datetime import datetime, timezone

DECAY_LAMBDA = 0.05
MAX_SNAPSHOTS = 60


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
    accuracy_snapshots = db.Column(db.JSON, default=list)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    matches = db.relationship("SignalMatch", backref="signal", lazy="dynamic")

    @property
    def operative_accuracy(self) -> float:
        snapshots = self.accuracy_snapshots or []
        if not snapshots:
            return self.historical_accuracy or 0.5

        weighted_sum = 0.0
        weight_total = 0.0
        for i, snap in enumerate(snapshots):
            w = math.exp(-DECAY_LAMBDA * i)
            total = snap.get("total", 0)
            if total == 0:
                continue
            weighted_sum += w * snap["accuracy"]
            weight_total += w

        if weight_total == 0:
            return 0.5
        return weighted_sum / weight_total

    @property
    def total_samples(self) -> int:
        return sum(s.get("total", 0) for s in (self.accuracy_snapshots or []))

    def push_snapshot(self, snapshot: dict):
        snaps = list(self.accuracy_snapshots or [])
        snaps.insert(0, snapshot)
        if len(snaps) > MAX_SNAPSHOTS:
            snaps = snaps[:MAX_SNAPSHOTS]
        self.accuracy_snapshots = snaps
        self.historical_accuracy = self.operative_accuracy
        self.sample_size = self.total_samples

    def __repr__(self):
        return f"<Signal {self.name}>"
