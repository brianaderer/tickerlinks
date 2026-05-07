from app.extensions import db
from datetime import datetime, timezone


class TrendSnapshot(db.Model):
    __tablename__ = "trend_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    generated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    trends = db.Column(db.JSON, nullable=False, default=list)

    def __repr__(self):
        return f"<TrendSnapshot {self.generated_at}>"
