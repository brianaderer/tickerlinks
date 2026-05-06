import logging

from langgraph.graph import StateGraph, END

from app.signals.state import EngineState
from app.signals.nodes.gather import gather_node
from app.signals.nodes.detect import detect_node
from app.signals.nodes.aggregate import aggregate_node
from app.signals.nodes.predict import predict_node
from app.signals.nodes.evaluate import evaluate_node, should_refine, refine_node
from app.signals.nodes.output import output_node

logger = logging.getLogger(__name__)


def build_signal_graph() -> StateGraph:
    graph = StateGraph(EngineState)

    graph.add_node("gather", gather_node)
    graph.add_node("detect", detect_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("predict", predict_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("refine", refine_node)
    graph.add_node("output", output_node)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "detect")
    graph.add_edge("detect", "aggregate")
    graph.add_edge("aggregate", "predict")
    graph.add_edge("predict", "evaluate")
    graph.add_conditional_edges("evaluate", should_refine, {
        "refine": "refine",
        "output": "output",
    })
    graph.add_edge("refine", "detect")
    graph.add_edge("output", END)

    return graph.compile()


def run_analysis(company_ids: list[int] | None = None) -> dict:
    logger.info("Starting signal analysis engine")

    initial_state: EngineState = {
        "company_ids": company_ids or [],
        "price_data": {},
        "news_data": {},
        "fundamentals_data": {},
        "insider_data": {},
        "signals": [],
        "predictions": [],
        "iteration": 0,
        "max_iterations": 3,
        "confidence_threshold": 0.55,
    }

    graph = build_signal_graph()
    final_state = graph.invoke(initial_state)

    strong = final_state.get("strong_predictions", [])
    weak = final_state.get("weak_predictions", [])
    total_signals = len(final_state.get("signals", []))

    logger.info(
        "Analysis complete: %d signals, %d strong predictions, %d weak predictions",
        total_signals, len(strong), len(weak),
    )

    return {
        "total_signals": total_signals,
        "strong_predictions": len(strong),
        "weak_predictions": len(weak),
        "iterations": final_state.get("iteration", 0),
    }
