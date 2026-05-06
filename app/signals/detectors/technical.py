import logging

import pandas as pd
import pandas_ta as ta

from app.signals.detectors.base import SignalDetector
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)


class TechnicalDetector(SignalDetector):
    name = "technical"
    signal_type = "technical"

    def __init__(self):
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.bb_period = 20
        self.bb_std = 2.0

    def detect(self, state: EngineState) -> list[SignalData]:
        signals = []
        for company_id, price_rows in state.get("price_data", {}).items():
            symbol = price_rows.get("symbol", "?")
            df = price_rows.get("df")
            if df is None or len(df) < 30:
                continue

            signals.extend(self._check_rsi(df, company_id, symbol))
            signals.extend(self._check_macd(df, company_id, symbol))
            signals.extend(self._check_bollinger(df, company_id, symbol))

        return signals

    def _check_rsi(self, df: pd.DataFrame, company_id: int, symbol: str) -> list[SignalData]:
        rsi = ta.rsi(df["close"], length=14)
        if rsi is None or rsi.empty:
            return []

        latest = rsi.iloc[-1]
        signals = []

        if latest <= self.rsi_oversold:
            signals.append(SignalData(
                signal_name="RSI Oversold",
                signal_type="technical",
                company_id=company_id,
                symbol=symbol,
                direction="bullish",
                confidence=min(0.9, (self.rsi_oversold - latest) / self.rsi_oversold + 0.5),
                context={"rsi": round(latest, 2), "threshold": self.rsi_oversold},
            ))
        elif latest >= self.rsi_overbought:
            signals.append(SignalData(
                signal_name="RSI Overbought",
                signal_type="technical",
                company_id=company_id,
                symbol=symbol,
                direction="bearish",
                confidence=min(0.9, (latest - self.rsi_overbought) / (100 - self.rsi_overbought) + 0.5),
                context={"rsi": round(latest, 2), "threshold": self.rsi_overbought},
            ))

        return signals

    def _check_macd(self, df: pd.DataFrame, company_id: int, symbol: str) -> list[SignalData]:
        macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd_df is None or macd_df.empty:
            return []

        macd_line = macd_df.iloc[:, 0]
        signal_line = macd_df.iloc[:, 2]

        if len(macd_line) < 2:
            return []

        prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
        curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]

        signals = []
        if prev_diff < 0 and curr_diff > 0:
            signals.append(SignalData(
                signal_name="MACD Bullish Crossover",
                signal_type="technical",
                company_id=company_id,
                symbol=symbol,
                direction="bullish",
                confidence=0.65,
                context={"macd": round(macd_line.iloc[-1], 4), "signal": round(signal_line.iloc[-1], 4)},
            ))
        elif prev_diff > 0 and curr_diff < 0:
            signals.append(SignalData(
                signal_name="MACD Bearish Crossover",
                signal_type="technical",
                company_id=company_id,
                symbol=symbol,
                direction="bearish",
                confidence=0.65,
                context={"macd": round(macd_line.iloc[-1], 4), "signal": round(signal_line.iloc[-1], 4)},
            ))

        return signals

    def _check_bollinger(self, df: pd.DataFrame, company_id: int, symbol: str) -> list[SignalData]:
        bb = ta.bbands(df["close"], length=self.bb_period, std=self.bb_std)
        if bb is None or bb.empty:
            return []

        latest_close = df["close"].iloc[-1]
        lower = bb.iloc[-1, 0]
        upper = bb.iloc[-1, 2]

        signals = []
        if latest_close <= lower:
            signals.append(SignalData(
                signal_name="Bollinger Band Lower Touch",
                signal_type="technical",
                company_id=company_id,
                symbol=symbol,
                direction="bullish",
                confidence=0.6,
                context={"close": round(latest_close, 2), "lower_band": round(lower, 2)},
            ))
        elif latest_close >= upper:
            signals.append(SignalData(
                signal_name="Bollinger Band Upper Touch",
                signal_type="technical",
                company_id=company_id,
                symbol=symbol,
                direction="bearish",
                confidence=0.6,
                context={"close": round(latest_close, 2), "upper_band": round(upper, 2)},
            ))

        return signals

    def refine(self, feedback: dict) -> None:
        if feedback.get("rsi_accuracy", 1.0) < 0.5:
            self.rsi_oversold = max(20, self.rsi_oversold - 2)
            self.rsi_overbought = min(80, self.rsi_overbought + 2)
            logger.info("Refined RSI thresholds: oversold=%d overbought=%d", self.rsi_oversold, self.rsi_overbought)
