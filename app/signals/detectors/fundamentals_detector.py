import logging
from datetime import datetime, timedelta, timezone

from app.signals.detectors.base import SignalDetector
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)


class FundamentalsDetector(SignalDetector):
    name = "fundamentals"
    signal_type = "fundamentals"

    def __init__(self):
        self.insider_cluster_window_days = 30
        self.insider_cluster_min_count = 3
        self.fifty_two_week_proximity_pct = 0.05

    def detect(self, state: EngineState) -> list[SignalData]:
        signals = []
        for company_id, fund_info in state.get("fundamentals_data", {}).items():
            symbol = fund_info.get("symbol", "?")
            fundamentals = fund_info.get("latest")
            insider_trades = fund_info.get("insider_trades", [])

            price_info = state.get("price_data", {}).get(company_id)
            latest_candle_ts = ""
            if price_info and price_info.get("df") is not None and not price_info["df"].empty:
                ts = price_info["df"].index[-1]
                latest_candle_ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

            if fundamentals:
                signals.extend(self._check_52week(company_id, symbol, fundamentals, latest_candle_ts))
            if insider_trades:
                signals.extend(self._check_insider_cluster(company_id, symbol, insider_trades))

        return signals

    def _check_52week(self, company_id: int, symbol: str, f: dict, candle_ts: str = "") -> list[SignalData]:
        signals = []
        price = f.get("current_price")
        high = f.get("fifty_two_week_high")
        low = f.get("fifty_two_week_low")

        if not all([price, high, low]) or high == low:
            return []

        proximity_to_high = (high - price) / high
        proximity_to_low = (price - low) / low if low > 0 else 999

        if proximity_to_high <= self.fifty_two_week_proximity_pct:
            signals.append(SignalData(
                signal_name="Near 52-Week High",
                signal_type="fundamentals",
                company_id=company_id,
                symbol=symbol,
                direction="bullish",
                confidence=0.6,
                source_at=candle_ts,
                context={
                    "price": price,
                    "52w_high": high,
                    "proximity_pct": round(proximity_to_high * 100, 2),
                },
            ))
        elif proximity_to_low <= self.fifty_two_week_proximity_pct:
            signals.append(SignalData(
                signal_name="Near 52-Week Low",
                signal_type="fundamentals",
                company_id=company_id,
                symbol=symbol,
                direction="bearish",
                confidence=0.6,
                source_at=candle_ts,
                context={
                    "price": price,
                    "52w_low": low,
                    "proximity_pct": round(proximity_to_low * 100, 2),
                },
            ))

        return signals

    def _check_insider_cluster(self, company_id: int, symbol: str, trades: list[dict]) -> list[SignalData]:
        now = datetime.now(timezone.utc).date()
        cutoff = now - timedelta(days=self.insider_cluster_window_days)

        recent_buys = [
            t for t in trades
            if t.get("transaction_type") == "Purchase"
            and t.get("shares", 0) > 0
            and t.get("date")
            and t["date"] >= cutoff
        ]
        recent_sells = [
            t for t in trades
            if t.get("transaction_type") == "Sale"
            and t.get("shares", 0) > 0
            and t.get("date")
            and t["date"] >= cutoff
        ]

        signals = []
        if len(recent_buys) >= self.insider_cluster_min_count:
            total_shares = sum(t.get("shares", 0) for t in recent_buys)
            latest_date = max(t["date"] for t in recent_buys if t.get("date"))
            source_at_str = datetime.combine(latest_date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat() if latest_date else ""
            signals.append(SignalData(
                signal_name="Insider Cluster Buy",
                signal_type="fundamentals",
                company_id=company_id,
                symbol=symbol,
                direction="bullish",
                confidence=min(0.85, 0.6 + len(recent_buys) * 0.05),
                source_at=source_at_str,
                context={
                    "buy_count": len(recent_buys),
                    "total_shares": total_shares,
                    "window_days": self.insider_cluster_window_days,
                    "filers": list({t.get("filer_name", "?") for t in recent_buys})[:5],
                },
            ))

        if len(recent_sells) >= self.insider_cluster_min_count:
            total_shares = sum(t.get("shares", 0) for t in recent_sells)
            latest_date = max(t["date"] for t in recent_sells if t.get("date"))
            source_at_str = datetime.combine(latest_date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat() if latest_date else ""
            signals.append(SignalData(
                signal_name="Insider Cluster Sell",
                signal_type="fundamentals",
                company_id=company_id,
                symbol=symbol,
                direction="bearish",
                confidence=min(0.85, 0.6 + len(recent_sells) * 0.05),
                source_at=source_at_str,
                context={
                    "sell_count": len(recent_sells),
                    "total_shares": total_shares,
                    "window_days": self.insider_cluster_window_days,
                    "filers": list({t.get("filer_name", "?") for t in recent_sells})[:5],
                },
            ))

        return signals
