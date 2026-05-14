from datetime import date

from app.tickerbets.features import HORIZONS
from app.tickerbets.service import (
    _horizon_days_from_requested,
    _normalize_target_date,
    _parse_target_date,
    available_target_dates,
)


def test_parse_target_date_accepts_date_and_iso():
    assert _parse_target_date("2026-05-14") == date(2026, 5, 14)
    assert _parse_target_date("2026-05-14T21:30:00+00:00") == date(2026, 5, 14)


def test_normalize_target_date_moves_weekend_to_monday():
    saturday = date(2026, 5, 16)
    sunday = date(2026, 5, 17)

    assert _normalize_target_date(saturday) == date(2026, 5, 18)
    assert _normalize_target_date(sunday) == date(2026, 5, 18)


def test_tickerbets_horizons_cover_1_to_10_days():
    assert HORIZONS[0] == 1
    assert HORIZONS[-1] == 10
    assert len(HORIZONS) == 10


def test_horizon_days_from_requested_uses_requested_date_not_weekday_adjustment():
    as_of = date(2026, 5, 14)
    requested_weekend = date(2026, 5, 24)
    assert _horizon_days_from_requested(requested_weekend, as_of) == 10


def test_normalize_target_date_skips_market_holidays():
    # Independence Day 2026 is Saturday; NYSE observed holiday is Friday 2026-07-03.
    observed_holiday = date(2026, 7, 3)
    assert _normalize_target_date(observed_holiday) == date(2026, 7, 6)


def test_available_target_dates_exclude_weekends_and_market_holidays():
    # As-of chosen so +1 day is observed Independence Day holiday (2026-07-03),
    # and +2/+3 are weekend. First available target should be Monday 2026-07-06.
    as_of = date(2026, 7, 2)
    dates = available_target_dates(as_of=as_of, min_days_ahead=1, max_days_ahead=10)

    assert dates
    assert dates[0] == date(2026, 7, 6)
    assert all(d.weekday() < 5 for d in dates)
