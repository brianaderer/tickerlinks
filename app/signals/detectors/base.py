from abc import ABC, abstractmethod

from app.signals.state import EngineState, SignalData


class SignalDetector(ABC):
    name: str
    signal_type: str

    @abstractmethod
    def detect(self, state: EngineState) -> list[SignalData]:
        ...

    def refine(self, feedback: dict) -> None:
        """Override to adjust parameters based on backtest feedback."""
        pass
