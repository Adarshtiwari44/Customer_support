from langgraph.graph import StateGraph, START, END

from customer_support.agent.state import AgentState
from customer_support.agent.memory import load_conversation_memory, save_conversation_memory
from customer_support.agent.context import build_context
from customer_support.agent.classifier import classify_intent
from customer_support.agent.entities import extract_entities
from customer_support.agent.retriever import retrieve_evidence
from customer_support.agent.generator import generate_response
from customer_support.agent.validators import validate_response
from customer_support.agent.router import route_decision


def _route_after_decision(state: AgentState) -> str:
    """
    Router decision mapping.
    """
    return state.get("decision", "ESCALATE")


def build_graph() -> StateGraph:
    """
    Complete stateful agent pipeline:
      START → memory_load → context → classifier → entities → retriever → generator → validator → router → memory_save → END
    """
    graph = StateGraph(AgentState)

    # ---- Register nodes ----
    graph.add_node("memory_load", load_conversation_memory)
    graph.add_node("context", build_context)
    graph.add_node("classifier", classify_intent)
    graph.add_node("entities", extract_entities)
    graph.add_node("retriever", retrieve_evidence)
    graph.add_node("generator", generate_response)
    graph.add_node("validator", validate_response)
    graph.add_node("router", route_decision)
    graph.add_node("memory_save", save_conversation_memory)

    # ---- Linear pipeline edges ----
    graph.add_edge(START, "memory_load")
    graph.add_edge("memory_load", "context")
    graph.add_edge("context", "classifier")
    graph.add_edge("classifier", "entities")
    graph.add_edge("entities", "retriever")
    graph.add_edge("retriever", "generator")
    graph.add_edge("generator", "validator")
    graph.add_edge("validator", "router")
    graph.add_edge("router", "memory_save")

    # ---- Conditional edge after memory_save ----
    graph.add_conditional_edges(
        "memory_save",
        _route_after_decision,
        {
            "AUTO_HANDLE": END,
            "NEED_INFORMATION": END,
            "ESCALATE": END,
        },
    )

    return graph


# Compiled graph
app = build_graph().compile()
