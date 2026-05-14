from app import create_app
from app.extensions import celery


def test_celery_beat_schedule_has_trends_and_15m_report():
    app = create_app()
    with app.app_context():
        beat_schedule = celery.conf.beat_schedule
        assert "generate-trends" in beat_schedule
        assert beat_schedule["generate-trends"]["task"] == "app.tasks.trends.generate_trends"
        assert float(beat_schedule["generate-trends"]["schedule"]) == 900.0

        assert "generate-report" in beat_schedule
        assert beat_schedule["generate-report"]["task"] == "app.tasks.report.generate_report"
        assert float(beat_schedule["generate-report"]["schedule"]) == 900.0
