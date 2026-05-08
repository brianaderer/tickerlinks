import json
import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.signals.detectors.base import SignalDetector
from app.signals.llm_utils import parse_llm_json
from app.signals.state import EngineState, SignalData

logger = logging.getLogger(__name__)

PATTERN_PROMPT = """You are a senior quantitative analyst. Given the following market signals detected for {symbol}, synthesize them into a pattern analysis.

Detected signals:
{signals_text}

Recent price action (last 5 data points):
{price_summary}

Identify any recognizable market patterns (e.g., earnings run-up, sector rotation, capitulation, momentum breakout, mean reversion).

Respond with ONLY a JSON object:
{{
    "pattern_name": "<name of detected pattern or 'none'>",
    "direction": "<bullish|bearish|neutral>",
    "confidence": <float 0.0 to 1.0>,
    "reasoning": "<concise explanation of the pattern and why it predicts this direction>"
}}"""


class PatternDetector(SignalDetector):
    name = "pattern"
    signal_type = "pattern"

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-14B-Instruct"),
                openai_api_key=os.environ.get("DEEPINFRA_API_KEY", ""),
                openai_api_base=os.environ.get("LLM_API_BASE", "https://api.deepinfra.com/v1/openai"),
                temperature=0.2,
                max_tokens=2000,
            )
        return self._llm

    def detect(self, state: EngineState) -> list[SignalData]:
        existing_signals = state.get("signals", [])
        if not existing_signals:
            return []

        companies = {}
        for sig in existing_signals:
            cid = sig.get("company_id")
            if cid not in companies:
                companies[cid] = {"symbol": sig.get("symbol", "?"), "signals": [], "types": set()}
            companies[cid]["signals"].append(sig)
            companies[cid]["types"].add(sig.get("signal_type", ""))

        results = []
        for company_id, info in companies.items():
            if len(info["types"]) < 2:
                continue
            try:
                signal = self._analyze_pattern(
                    company_id,
                    info["symbol"],
                    info["signals"],
                    state.get("price_data", {}).get(company_id),
                )
                if signal:
                    results.append(signal)
            except Exception:
                logger.exception("Pattern analysis failed for %s", info["symbol"])

        return results

    def _analyze_pattern(
        self, company_id: int, symbol: str, signals: list, price_info: dict | None
    ) -> SignalData | None:
        signals_text = "\n".join(
            f"- {s['signal_name']} ({s['direction']}, confidence: {s['confidence']:.2f}): {json.dumps(s.get('context', {}))}"
            for s in signals
        )

        price_summary = "No price data available"
        if price_info and price_info.get("df") is not None:
            df = price_info["df"]
            tail = df.tail(5)
            price_summary = "\n".join(
                f"  {idx}: O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f} V={int(row['volume'])}"
                for idx, row in tail.iterrows()
            )

        prompt = PATTERN_PROMPT.format(
            symbol=symbol, signals_text=signals_text, price_summary=price_summary
        )
        response = self.llm.invoke([
            SystemMessage(content="You are a quantitative pattern recognition system."),
            HumanMessage(content=prompt),
        ])

        result = parse_llm_json(response.content)
        if not result:
            logger.warning("Failed to parse pattern LLM response for %s: %s", symbol, response.content[:300])
            return None

        if result.get("pattern_name", "none").lower() == "none":
            return None
        if result.get("direction", "neutral") == "neutral":
            return None

        source_at_str = ""
        if price_info and price_info.get("df") is not None and not price_info["df"].empty:
            ts = price_info["df"].index[-1]
            source_at_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

        return SignalData(
            signal_name=f"Pattern: {result['pattern_name']}",
            signal_type="pattern",
            company_id=company_id,
            symbol=symbol,
            direction=result["direction"],
            confidence=float(result.get("confidence", 0.5)),
            source_at=source_at_str,
            context={
                "pattern": result["pattern_name"],
                "reasoning": result.get("reasoning", ""),
                "contributing_signals": len(signals),
            },
        )
