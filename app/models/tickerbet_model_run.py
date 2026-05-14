from datetime import datetime, timezone

from app.extensions import db


class TickerBetModelRun(db.Model):
    __tablename__ = "tickerbet_model_runs"
    __table_args__ = (
        db.Index("ix_tickerbet_run_started", "started_at"),
        db.Index("ix_tickerbet_run_status", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="running")
    model_family = db.Column(db.String(32), nullable=False, default="xgboost")

    started_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    training_window_start = db.Column(db.DateTime(timezone=True), nullable=True)
    training_window_end = db.Column(db.DateTime(timezone=True), nullable=True)

    company_count = db.Column(db.Integer, nullable=False, default=0)
    sample_count = db.Column(db.Integer, nullable=False, default=0)
    train_count = db.Column(db.Integer, nullable=False, default=0)
    test_count = db.Column(db.Integer, nullable=False, default=0)

    feature_columns = db.Column(db.JSON, default=dict)
    metrics = db.Column(db.JSON, default=dict)

    artifact_prefix = db.Column(db.String(512), nullable=True)
    dataset_key = db.Column(db.String(512), nullable=True)
    model_keys = db.Column(db.JSON, default=dict)
    metadata_key = db.Column(db.String(512), nullable=True)

    error = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<TickerBetModelRun run_id={self.run_id} status={self.status}>"
