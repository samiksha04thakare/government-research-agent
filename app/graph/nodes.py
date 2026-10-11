from app.agents import classifier, planner, verifier
from app.agents.research_agent import synthesize_answer
from app.config import MAX_AGENT_LOOPS, RELEVANCE_THRESHOLD
from app.graph.state import ResearchState
from app.rag import router
from app.tools.document_search import vector_search
from app.utils.citations import build_citations, format_citations_markdown
from app.utils.logging import get_logger

log = get_logger("graph")

OUT_OF_SCOPE_RESPONSE = (
    "This question is outside the scope of the AI Government Research Agent. "
    "Please ask a government or agriculture-related question."
)
RELEVANCE_NOT_FOUND_MESSAGE = (
    "No sufficiently relevant official information was found in the indexed government sources for this question."
)


def classify_query(state: ResearchState) -> ResearchState:
    res = classifier.classify(state["question"])
    cat = res.get("category", "out_of_scope")
    scope = res.get("scope", "out_of_scope")
    route = router.get_route(cat)
    log.info("query classified as category='%s', scope='%s' (filter: %s)", cat, scope, route.get("filter"))
    return {
        "category": cat,
        "scope": scope,
        "source_route": route,
        "metadata_filter": route.get("filter"),
        "loops": 0,
        "evidence": [],
    }


def out_of_scope(state: ResearchState) -> ResearchState:
    return {
        "final_answer": OUT_OF_SCOPE_RESPONSE,
        "citations": [],
        "conflicts": [],
        "unsupported": [],
        "status": "out_of_scope",
    }


def no_documents(state: ResearchState) -> ResearchState:
    return {
        "final_answer": router.NO_DOCUMENTS_RESPONSE,
        "citations": [],
        "conflicts": [],
        "unsupported": [],
        "status": "no_documents_for_category",
    }


def route_after_classify(state: ResearchState) -> str:
    scope = state.get("scope", "out_of_scope")
    if scope == "out_of_scope":
        return "out_of_scope"
    if not state.get("source_route", {}).get("has_documents", True):
        return "no_documents"
    return "analyze_query"


def analyze_query(state: ResearchState) -> ResearchState:
    from app.schemes.pipeline import find_matching_scheme_for_query
    matched = find_matching_scheme_for_query(state["question"])
    matched_dict = matched.to_dict() if matched else None
    return {
        "intent": planner.analyze(state["question"]),
        "loops": 0,
        "evidence": [],
        "matched_scheme": matched_dict,
    }


def plan_research(state: ResearchState) -> ResearchState:
    return {"sub_questions": planner.plan(state["question"], state["intent"])}


def retrieve(state: ResearchState) -> ResearchState:
    filters = state.get("metadata_filter")
    cat = state.get("category", "unknown")
    q_main = state.get("question", "")

    evidence_map = {
        (e["metadata"].get("content_hash"), e["text"][:80]): e
        for e in state.get("evidence", [])
    }
    raw_retrieved_count = 0
    all_scores = []

    for q in state["sub_questions"]:
        raw_items = vector_search(q, k=4, filters=filters)
        raw_retrieved_count += len(raw_items)
        for item in raw_items:
            score = item.get("similarity_score", 0.0)
            all_scores.append(score)
            if score >= RELEVANCE_THRESHOLD:
                key = (item["metadata"].get("content_hash"), item["text"][:80])
                if key not in evidence_map:
                    evidence_map[key] = item
                elif score > evidence_map[key].get("similarity_score", 0.0):
                    evidence_map[key]["similarity_score"] = score

    evidence = list(evidence_map.values())
    decision = "ACCEPTED" if evidence else "REJECTED_LOW_RELEVANCE"
    log.info(
        "RETRIEVAL: Query='%s' | Category='%s' | Retrieved document count=%d | Documents accepted after relevance filtering=%d | Relevance scores=%s | Final decision='%s' (Threshold=%.2f)",
        q_main,
        cat,
        raw_retrieved_count,
        len(evidence),
        all_scores[:6],
        decision,
        RELEVANCE_THRESHOLD,
    )
    return {"evidence": evidence}


def grade_evidence(state: ResearchState) -> ResearchState:
    evidence = state.get("evidence", [])
    if not evidence:
        return {"sufficient": False, "missing": "No sufficiently relevant official documents passed the similarity threshold."}
    from app.utils.citations import filter_supported_evidence
    supported_evidence, _ = filter_supported_evidence(state["question"], evidence, category=state.get("category"))
    if not supported_evidence:
        return {"evidence": [], "sufficient": False, "missing": "Retrieved documents do not support the specific claims or procedures of this query."}
    g = verifier.grade(state["question"], supported_evidence)
    kept = [supported_evidence[i] for i in g.relevant_indexes if 0 <= i < len(supported_evidence)]
    return {"evidence": kept, "sufficient": g.sufficient and bool(kept), "missing": g.missing}


def refine_query(state: ResearchState) -> ResearchState:
    new_qs = planner.refine(state["question"], state.get("missing", ""), state["sub_questions"])
    return {"sub_questions": new_qs, "loops": state.get("loops", 0) + 1}


def synthesize(state: ResearchState) -> ResearchState:
    citations = build_citations(state["evidence"])
    lang = state.get("language", "auto")
    scheme = state.get("matched_scheme")
    draft = synthesize_answer(
        state["question"],
        state["evidence"],
        matched_scheme=scheme,
        language=lang,
    )
    return {"draft_answer": draft, "citations": citations}


def verify(state: ResearchState) -> ResearchState:
    v = verifier.verify(state["draft_answer"], state["evidence"])
    return {"conflicts": [c.model_dump() for c in v.conflicts], "unsupported": v.unsupported_claims}


def cite(state: ResearchState) -> ResearchState:
    answer = state["draft_answer"]
    if state.get("conflicts"):
        answer += "\n\n**Conflicting information found:**\n" + "\n".join(
            f"- {c['topic']} (sources {c['source_ids']}): {c['explanation']}" for c in state["conflicts"]
        )
    if state.get("unsupported"):
        answer += "\n\n**Could not be verified from the retrieved sources:**\n" + "\n".join(
            f"- {u}" for u in state["unsupported"]
        )
    from app.utils.citations import reconcile_citations_with_answer
    reconciled_answer, reconciled_citations = reconcile_citations_with_answer(answer, state.get("citations", []))
    final_answer = reconciled_answer + format_citations_markdown(reconciled_citations)
    return {"final_answer": final_answer, "status": "completed", "citations": reconciled_citations}


def insufficient(state: ResearchState) -> ResearchState:
    return {
        "final_answer": RELEVANCE_NOT_FOUND_MESSAGE,
        "citations": [],
        "conflicts": [],
        "status": "insufficient_evidence",
    }


def route_after_grade(state: ResearchState) -> str:
    if not state.get("evidence"):
        return "insufficient"
    if state.get("sufficient"):
        return "synthesize"
    if state.get("loops", 0) < MAX_AGENT_LOOPS:
        return "refine_query"
    # loop budget exhausted: answer only if some relevant evidence exists
    return "synthesize" if state.get("evidence") else "insufficient"
