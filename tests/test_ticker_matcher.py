"""
Test suite for the ticker matching agent.

Failure modes:
1. Wrong ticker hallucination (ARMH->ARM, BRK->BRK.B, PAL->PLTR)
2. Universe guard — untracked companies dropped
3. Multi-company articles — all tracked tickers returned
4. Name-only mentions — no ticker in text, resolved by company name/description
5. Per-company sentiment — each company gets its own direction
"""
import pytest


@pytest.fixture(scope="session")
def app():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(autouse=True)
def app_context(app):
    with app.app_context():
        yield


@pytest.fixture(scope="session")
def valid_symbols(app):
    with app.app_context():
        from app.models import Company
        return set(c.symbol.upper() for c in Company.query.filter_by(active=True).all())


def _match(title, summary=""):
    from app.articles.ticker_matcher import match_tickers
    return match_tickers(title, summary)


class TestWrongTickerHallucination:
    def test_arm_not_armh(self):
        result = _match('Jim Cramer Calls Arm Holdings a "Real Good One"')
        assert "ARM" in result
        assert "ARMH" not in result

    def test_berkshire_is_brkb(self):
        result = _match('Berkshire Hathaway "Underperformed of Late"')
        assert "BRK.B" in result

    def test_palantir_is_pltr(self):
        result = _match("Palantir lifts annual revenue forecast on robust US government demand")
        assert "PLTR" in result
        assert "PAL" not in result


class TestUniverseGuard:
    def test_untracked_dropped(self):
        result = _match('Jim Cramer on Dutch Bros: "Serial Upside Surpriser"')
        assert "DUTCH" not in result
        assert "BROS" not in result

    def test_all_tickers_valid(self, valid_symbols):
        result = _match(
            "Apple reported strong earnings while GameStop shares fell",
            "Mixed day for equities as tech leads gains."
        )
        for sym in result:
            assert sym in valid_symbols, f"{sym} not in tracked universe"


class TestMultiCompany:
    def test_multiple_tracked_returned(self):
        result = _match(
            "Intel, PayPal, Palantir, Shopify, Micron Stock Market Movers",
            "These major stocks are making big moves after quarterly earnings."
        )
        for sym in ("INTC", "PYPL", "PLTR", "SHOP", "MU"):
            assert sym in result, f"Missing {sym}"


class TestNameOnly:
    def test_apple_by_name(self):
        result = _match("Apple reports record quarterly revenue driven by iPhone sales")
        assert "AAPL" in result

    def test_nvidia_by_name(self):
        result = _match("Nvidia dominates AI chip market as demand surges")
        assert "NVDA" in result


class TestSentiment:
    def test_mixed_sentiment(self):
        result = _match(
            "Apple beats earnings while Intel misses badly",
            "Apple reported strong Q2 results. Intel disappointed with weak guidance."
        )
        if "AAPL" in result and "INTC" in result:
            assert result["AAPL"]["sentiment"] == "bullish"
            assert result["INTC"]["sentiment"] == "bearish"
