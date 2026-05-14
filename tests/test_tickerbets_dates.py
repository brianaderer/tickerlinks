from datetime import date

from app.tickerbets.service import _normalize_target_date, _parse_target_date


def test_parse_target_date_accepts_date_and_iso():
    assert _parse_target_date("2026-05-14") == date(2026, 5, 14)
    assert _parse_target_date("2026-05-14T21:30:00+00:00") == date(2026, 5, 14)


def test_normalize_target_date_moves_weekend_to_monday():
    saturday = date(2026, 5, 16)
    sunday = date(2026, 5, 17)

    assert _normalize_target_date(saturday) == date(2026, 5, 18)
    assert _normalize_target_date(sunday) == date(2026, 5, 18)
