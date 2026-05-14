from datetime import date
from types import SimpleNamespace

from app.api.linky_tools import (
    LINKY_TOOLS,
    TICKERBETS_DISCLAIMER,
    _resolve_tickerbets_target_date,
    ticker_bets,
    ticker_bets_rankings,
    ticker_bets_overlay,
)


def test_linky_tools_include_ticker_bets():
    names = [tool.name for tool in LINKY_TOOLS]
    assert "ticker_bets" in names
    assert "ticker_bets_rankings" in names
    assert "ticker_bets_overlay" in names


def test_ticker_bets_response_includes_disclaimer(monkeypatch):
    def fake_generate_bet_prediction(symbol: str, target_date: str, run_id: str | None = None):
        return {
            "symbol": symbol,
            "requested_target_date": target_date,
            "resolved_target_date": target_date,
            "horizon_days": 2,
            "as_of": "2026-05-14T00:00:00+00:00",
            "current_price": 100.0,
            "predicted_price": 101.25,
            "predicted_delta": 1.25,
            "predicted_delta_pct": 0.0125,
            "run_id": "run123",
            "metrics": {"mae": 1.1, "rmse": 2.2, "r2": 0.8, "directional_accuracy": 0.55},
        }

    monkeypatch.setattr("app.tickerbets.service.generate_bet_prediction", fake_generate_bet_prediction)
    output = ticker_bets.invoke({"symbol": "AAPL", "target_date": "2026-05-16"})

    assert "TickerBets estimate for AAPL" in output
    assert "Disclaimer:" in output
    assert TICKERBETS_DISCLAIMER in output
    assert "Directional Acc" not in output


def test_ticker_bets_error_path_includes_disclaimer(monkeypatch):
    def fake_generate_bet_prediction(symbol: str, target_date: str, run_id: str | None = None):
        raise ValueError("No successful tickerbet model run available")

    monkeypatch.setattr("app.tickerbets.service.generate_bet_prediction", fake_generate_bet_prediction)
    output = ticker_bets.invoke({"symbol": "AAPL", "target_date": "2026-05-16"})

    assert "TickerBets unavailable" in output
    assert TICKERBETS_DISCLAIMER in output


def test_resolve_tickerbets_target_date_caps_horizon_to_10_days(monkeypatch):
    monkey_dates = [date(2026, 5, 15), date(2026, 5, 16), date(2026, 5, 19), date(2026, 5, 20)]
    monkeypatch.setattr(
        "app.tickerbets.service.available_target_dates",
        lambda min_days_ahead=1, max_days_ahead=10: monkey_dates[:max_days_ahead],
    )
    resolved = _resolve_tickerbets_target_date("", 999)

    assert resolved == monkey_dates[-1].isoformat()


def test_ticker_bets_can_include_metrics_and_directional_accuracy(monkeypatch):
    def fake_generate_bet_prediction(symbol: str, target_date: str, run_id: str | None = None):
        return {
            "symbol": symbol,
            "requested_target_date": target_date,
            "resolved_target_date": target_date,
            "horizon_days": 2,
            "as_of": "2026-05-14T00:00:00+00:00",
            "current_price": 100.0,
            "predicted_price": 101.25,
            "predicted_delta": 1.25,
            "predicted_delta_pct": 0.0125,
            "run_id": "run123",
            "metrics": {"mae": 1.1, "rmse": 2.2, "r2": 0.8, "directional_accuracy": 0.55},
        }

    monkeypatch.setattr("app.tickerbets.service.generate_bet_prediction", fake_generate_bet_prediction)
    output = ticker_bets.invoke(
        {
            "symbol": "AAPL",
            "target_date": "2026-05-16",
            "include_model_metrics": True,
            "include_directional_accuracy": True,
        }
    )

    assert "Metrics:" in output
    assert "Directional Acc" in output


def test_ticker_bets_rankings_response_is_grounded_and_includes_disclaimer(monkeypatch):
    monkeypatch.setattr(
        "app.api.linky_tools._get_tickerbets_rankings",
        lambda target_date, horizon_days, run_id="": {
            "requested_target_date": "2026-05-16",
            "count": 3,
            "rows": [
                {
                    "symbol": "BEAR",
                    "delta_pct": -0.08,
                    "current_price": 100.0,
                    "predicted_price": 92.0,
                    "resolved_target_date": "2026-05-16",
                    "horizon_days": 5,
                    "run_id": "run123",
                },
                {
                    "symbol": "MID",
                    "delta_pct": 0.01,
                    "current_price": 100.0,
                    "predicted_price": 101.0,
                    "resolved_target_date": "2026-05-16",
                    "horizon_days": 5,
                    "run_id": "run123",
                },
                {
                    "symbol": "BULL",
                    "delta_pct": 0.05,
                    "current_price": 100.0,
                    "predicted_price": 105.0,
                    "resolved_target_date": "2026-05-16",
                    "horizon_days": 5,
                    "run_id": "run123",
                },
            ],
        },
    )
    output = ticker_bets_rankings.invoke({"target_date": "2026-05-16", "horizon_days": 5, "limit": 1})

    assert "Most bullish" in output
    assert "Most bearish" in output
    assert "BULL" in output
    assert "BEAR" in output
    assert TICKERBETS_DISCLAIMER in output


def test_ticker_bets_overlay_returns_direct_verdict_with_disclaimer(monkeypatch):
    monkeypatch.setattr(
        "app.api.linky_tools._lookup_company",
        lambda symbol: SimpleNamespace(id=1, symbol=symbol),
    )
    monkeypatch.setattr(
        "app.api.linky_tools._fetch_tickerbets_prediction",
        lambda symbol, target_date, run_id="": {
            "symbol": symbol,
            "requested_target_date": target_date,
            "resolved_target_date": target_date,
            "horizon_days": 2,
            "as_of": "2026-05-14T00:00:00+00:00",
            "current_price": 100.0,
            "predicted_price": 103.0,
            "predicted_delta": 3.0,
            "predicted_delta_pct": 0.03,
            "run_id": "run123",
            "metrics": {"directional_accuracy": 0.6},
        },
    )
    monkeypatch.setattr(
        "app.api.linky_tools._get_recent_overlay_context",
        lambda company_id: {
            "latest_prediction": SimpleNamespace(direction="bullish", confidence=0.72),
            "signal_count_7d": 4,
            "bullish_signal_score": 2.1,
            "bearish_signal_score": 1.0,
            "price_change_7d_pct": 0.04,
        },
    )

    output = ticker_bets_overlay.invoke({"symbol": "AAPL", "target_date": "2026-05-16"})
    assert "verdict=supports" in output
    assert "Key evidence:" in output
    assert "directional acc" not in output.lower()
    assert TICKERBETS_DISCLAIMER in output


def test_ticker_bets_overlay_missing_company_includes_disclaimer(monkeypatch):
    monkeypatch.setattr("app.api.linky_tools._lookup_company", lambda symbol: None)
    output = ticker_bets_overlay.invoke({"symbol": "ZZZZ", "target_date": "2026-05-16"})

    assert "overlay unavailable" in output.lower()
    assert TICKERBETS_DISCLAIMER in output
