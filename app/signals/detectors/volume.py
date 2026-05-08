import logging

import pandas as pd

from app.signals.detectors.base import SignalDetector
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)


class VolumeDetector(SignalDetector):
    name = "volume"
    signal_type = "volume"

    def __init__(self):
        self.spike_threshold = 2.0
        self.lookback = 20

    def detect(self, state: EngineState) -> list[SignalData]:
        signals = []
        for company_id, price_rows in state.get("price_data", {}).items():
            symbol = price_rows.get("symbol", "?")
            df = price_rows.get("df")
            if df is None or len(df) < self.lookback + 1:
                continue

            signals.extend(self._check_volume_spike(df, company_id, symbol))
            signals.extend(self._check_volume_divergence(df, company_id, symbol))

        return signals

    def _candle_ts(self, df: pd.DataFrame, idx: int = -1) -> str:
        ts = df.index[idx]
        if hasattr(ts, "isoformat"):
            return ts.isoformat()
        return str(ts)

    def _check_volume_spike(self, df: pd.DataFrame, company_id: int, symbol: str) -> list[SignalData]:
        avg_volume = df["volume"].iloc[-self.lookback - 1:-1].mean()
        if avg_volume == 0:
            return []

        latest_volume = df["volume"].iloc[-1]
        ratio = latest_volume / avg_volume

        if ratio >= self.spike_threshold:
            price_change = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
            direction = "bullish" if price_change > 0 else "bearish"

            return [SignalData(
                signal_name="Volume Spike",
                signal_type="volume",
                company_id=company_id,
                symbol=symbol,
                direction=direction,
                confidence=min(0.85, 0.5 + (ratio - self.spike_threshold) * 0.1),
                source_at=self._candle_ts(df),
                context={
                    "volume_ratio": round(ratio, 2),
                    "avg_volume": int(avg_volume),
                    "latest_volume": int(latest_volume),
                    "price_change_pct": round(price_change * 100, 2),
                },
            )]
        return []

    def _check_volume_divergence(self, df: pd.DataFrame, company_id: int, symbol: str) -> list[SignalData]:
        recent = df.tail(5)
        if len(recent) < 5:
            return []

        price_trend = recent["close"].iloc[-1] - recent["close"].iloc[0]
        volume_trend = recent["volume"].iloc[-1] - recent["volume"].iloc[0]

        if price_trend > 0 and volume_trend < 0:
            return [SignalData(
                signal_name="Bearish Volume Divergence",
                signal_type="volume",
                company_id=company_id,
                symbol=symbol,
                direction="bearish",
                confidence=0.55,
                source_at=self._candle_ts(recent),
                context={"price_trend": "up", "volume_trend": "down"},
            )]
        elif price_trend < 0 and volume_trend > 0:
            return [SignalData(
                signal_name="Bullish Volume Divergence",
                signal_type="volume",
                company_id=company_id,
                symbol=symbol,
                direction="bullish",
                confidence=0.55,
                source_at=self._candle_ts(recent),
                context={"price_trend": "down", "volume_trend": "up"},
            )]
        return []

    def refine(self, feedback: dict) -> None:
        if feedback.get("spike_accuracy", 1.0) < 0.5:
            self.spike_threshold = min(3.0, self.spike_threshold + 0.2)
            logger.info("Refined volume spike threshold: %.1f", self.spike_threshold)
