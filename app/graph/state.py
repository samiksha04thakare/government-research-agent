from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    question: str
    category: str                   # e.g. government_schemes, pest_management, out_of_scope
    scope: str                      # government_related | agriculture_related | out_of_scope
    source_route: dict[str, Any]    # target route and source information
    metadata_filter: dict | None    # ChromaDB metadata filter for retrieval
    intent: dict[str, Any]          # location, user_type, year, topic
    sub_questions: list[str]
    evidence: list[dict]            # {text, metadata, validation, cid}
    sufficient: bool
    missing: str                    # what the grader says is still missing
    loops: int                      # retrieval retries used (bounded by MAX_AGENT_LOOPS)
    draft_answer: str
    conflicts: list[dict]
    unsupported: list[str]
    citations: list[dict]
    final_answer: str
    status: str                     # completed | insufficient_evidence | out_of_scope | no_documents_for_category
    language: str                   # en | hi | mr
    detected_language: str          # en | hi | mr
    practical_steps: list[str]
    clarifying_question: str | None
    missing_evidence_warning: bool
    matched_scheme: dict[str, Any] | None  # Structured scheme record from PostgreSQL/SQL
