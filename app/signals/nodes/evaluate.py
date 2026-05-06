import logging

from app.signals.state import EngineState

logger = logging.getLogger(__name__)


def evaluate_node(state: EngineState) -> EngineState:
    threshold = state.get("confidence_threshold", 0.55)
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)

    predictions = state.get("predictions", [])
    strong = [p for p in predictions if p["confidence"] >= threshold]
    weak = [p for p in predictions if p["confidence"] < threshold]

    logger.info(
        "Evaluation (iter %d/%d): %d strong, %d weak predictions (threshold: %.2f)",
        iteration, max_iter, len(strong), len(weak), threshold,
    )

    state["strong_predictions"] = strong
    state["weak_predictions"] = weak
    state["iteration"] = iteration + 1
    state["needs_refinement"] = len(weak) > len(strong) and iteration < max_iter

    return state


def should_refine(state: EngineState) -> str:
    if state.get("needs_refinement", False):
        logger.info("Refinement triggered — re-running detection with adjusted params")
        return "refine"
    return "output"


def refine_node(state: EngineState) -> EngineState:
    logger.info("Refining detector parameters for iteration %d", state.get("iteration", 0))
    state["confidence_threshold"] = max(0.45, state.get("confidence_threshold", 0.55) - 0.05)
    return state
