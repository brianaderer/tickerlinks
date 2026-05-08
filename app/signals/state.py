from dataclasses import dataclass, field
from typing import TypedDict


class SignalData(TypedDict, total=False):
    signal_name: str
    signal_type: str
    company_id: int
    symbol: str
    direction: str
    confidence: float
    context: dict
    source_at: str


class EngineState(TypedDict, total=False):
    company_ids: list[int]
    price_data: dict
    news_data: dict
    fundamentals_data: dict
    insider_data: dict
    signals: list[SignalData]
    predictions: list[dict]
    strong_predictions: list[dict]
    weak_predictions: list[dict]
    needs_refinement: bool
    iteration: int
    max_iterations: int
    confidence_threshold: float
