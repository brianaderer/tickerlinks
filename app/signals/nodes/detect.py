import logging

from app.signals.detectors.technical import TechnicalDetector
from app.signals.detectors.volume import VolumeDetector
from app.signals.detectors.fundamentals_detector import FundamentalsDetector
from app.signals.detectors.article_sentiment import ArticleSentimentDetector
from app.signals.detectors.mention_velocity import MentionVelocityDetector
from app.signals.detectors.comention import ComentionDetector
from app.signals.detectors.source_breadth import SourceBreadthDetector
from app.signals.state import EngineState

logger = logging.getLogger(__name__)

DETECTORS = [
    TechnicalDetector(),
    VolumeDetector(),
    FundamentalsDetector(),
    ArticleSentimentDetector(),
    MentionVelocityDetector(),
    ComentionDetector(),
    SourceBreadthDetector(),
]


def detect_node(state: EngineState) -> EngineState:
    all_signals = []

    for detector in DETECTORS:
        try:
            signals = detector.detect(state)
            all_signals.extend(signals)
            logger.info("Detector %s produced %d signals", detector.name, len(signals))
        except Exception:
            logger.exception("Detector %s failed", detector.name)

    state["signals"] = all_signals
    logger.info("Total signals detected: %d", len(all_signals))
    return state
