from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import ResearchState


def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("classify_query", nodes.classify_query)
    g.add_node("out_of_scope", nodes.out_of_scope)
    g.add_node("no_documents", nodes.no_documents)
    g.add_node("analyze_query", nodes.analyze_query)
    g.add_node("plan_research", nodes.plan_research)
    g.add_node("retrieve", nodes.retrieve)
    g.add_node("grade_evidence", nodes.grade_evidence)
    g.add_node("refine_query", nodes.refine_query)
    g.add_node("synthesize", nodes.synthesize)
    g.add_node("verify", nodes.verify)
    g.add_node("cite", nodes.cite)
    g.add_node("insufficient", nodes.insufficient)

    g.add_edge(START, "classify_query")
    g.add_conditional_edges(
        "classify_query",
        nodes.route_after_classify,
        {
            "analyze_query": "analyze_query",
            "out_of_scope": "out_of_scope",
            "no_documents": "no_documents",
        },
    )
    g.add_edge("out_of_scope", END)
    g.add_edge("no_documents", END)
    g.add_edge("analyze_query", "plan_research")
    g.add_edge("plan_research", "retrieve")
    g.add_edge("retrieve", "grade_evidence")
    g.add_conditional_edges(
        "grade_evidence",
        nodes.route_after_grade,
        {"synthesize": "synthesize", "refine_query": "refine_query", "insufficient": "insufficient"},
    )
    g.add_edge("refine_query", "retrieve")
    g.add_edge("synthesize", "verify")
    g.add_edge("verify", "cite")
    g.add_edge("cite", END)
    g.add_edge("insufficient", END)
    return g.compile()


graph = build_graph()


def run_research(question: str, language: str = "auto", scheme_id: str | None = None) -> ResearchState:
    payload = {"question": question, "language": language}
    if scheme_id:
        payload["scheme_id"] = scheme_id
    return graph.invoke(payload, config={"recursion_limit": 25})
