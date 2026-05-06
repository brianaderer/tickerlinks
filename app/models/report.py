from datetime import datetime, timezone

from app.extensions import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(20), nullable=False, default="hourly")
    generated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    summary = db.Column(db.Text)
    data = db.Column(db.JSON, default=dict)

    def __repr__(self):
        return f"<Report {self.report_type} {self.generated_at}>"
