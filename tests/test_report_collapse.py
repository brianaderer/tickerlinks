from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.api.routes import _collapse_reports_by_time_gap


def _r(report_id: int, generated_at: datetime):
    return SimpleNamespace(id=report_id, generated_at=generated_at)


def test_report_collapse_keeps_latest_per_40_min_window():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    reports = [
        _r(1, now),
        _r(2, now - timedelta(minutes=5)),
        _r(3, now - timedelta(minutes=20)),
        _r(4, now - timedelta(minutes=41)),
        _r(5, now - timedelta(minutes=75)),
    ]

    collapsed = _collapse_reports_by_time_gap(reports, min_gap_minutes=40)
    assert [r.id for r in collapsed] == [1, 4]


def test_report_collapse_no_window_returns_all():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    reports = [
        _r(1, now),
        _r(2, now - timedelta(minutes=5)),
    ]

    collapsed = _collapse_reports_by_time_gap(reports, min_gap_minutes=0)
    assert [r.id for r in collapsed] == [1, 2]
