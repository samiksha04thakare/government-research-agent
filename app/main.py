import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import ADMIN_TOKEN, LLM_MODEL
from app.database.db import Document, ResearchHistory, Scheme, SessionLocal, init_db
from app.utils.logging import get_logger

from contextlib import asynccontextmanager

log = get_logger("api")

RAW_DIR = Path("data/raw")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXT = {".pdf", ".html", ".htm", ".txt"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        from app.schemes.pipeline import seed_official_schemes, sync_all_schemes_to_vectorstore
        if db.query(Scheme).count() == 0:
            seed_official_schemes(db=db)
        sync_all_schemes_to_vectorstore(db=db)
        if db.query(Document).filter(Document.indexed.is_(True)).count() == 0:
            from app.rag.bootstrap import bootstrap_baseline_documents
            bootstrap_baseline_documents(db=db)
    yield


app = FastAPI(title="AI Government Research Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(x_admin_token: str = Header(default="")):
    # Access control for document management (doc section 24)
    if not ADMIN_TOKEN or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Admin token required")


from pydantic import BaseModel, Field, field_validator

class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    language: str = Field(default="en", description="Response language: 'en', 'hi', 'mr', or 'auto'")
    scheme_id: str | None = Field(default=None, description="Optional scheme ID to scope research exclusively to that scheme")

    @field_validator("language", mode="before")
    def sanitize_language(cls, v):
        if not v or not isinstance(v, str):
            return "en"
        val = v.strip().lower()
        if val in ("en", "hi", "mr", "auto"):
            return val
        return "en"

    @field_validator("scheme_id", mode="before")
    def sanitize_scheme_id(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v_clean = v.strip()
            return v_clean if v_clean else None
        return str(v)


def has_llm_key():
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    is_groq = bool(groq_key and not any(p in groq_key for p in ["your-groq", "your_groq", "your-key"]))
    is_anthropic = bool(anthropic_key and not any(p in anthropic_key for p in ["your-key", "your_key"]))
    return is_groq or is_anthropic


def get_active_model_info():
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if groq_key and not any(p in groq_key for p in ["your-groq", "your_groq", "your-key"]):
        return f"{os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')} (Groq)"
    if anthropic_key and not any(p in anthropic_key for p in ["your-key", "your_key"]):
        return f"{LLM_MODEL} (Anthropic)"
    return "None (Grounded Local Vector Synthesis)"


@app.get("/health")
def health():
    with SessionLocal() as db:
        indexed_count = db.query(Document).filter(Document.indexed.is_(True)).count()
        total_count = db.query(Document).count()
        schemes_count = db.query(Scheme).count()
    
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    is_groq = bool(groq_key and not any(p in groq_key for p in ["your-groq", "your_groq", "your-key"]))
    is_anthropic = bool(anthropic_key and not any(p in anthropic_key for p in ["your-key", "your_key"]))
    provider = "groq" if is_groq else ("anthropic" if is_anthropic else "local_vector")

    return {
        "status": "ok",
        "has_api_key": has_llm_key(),
        "llm_provider": provider,
        "llm_model": get_active_model_info(),
        "groq_base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        "indexed_documents": indexed_count,
        "total_documents": total_count,
        "structured_schemes": schemes_count,
    }


class ApiKeyUpdateRequest(BaseModel):
    provider: str = Field(description="'groq' or 'anthropic'")
    api_key: str = Field(description="The API key value")
    base_url: str | None = Field(default=None, description="Optional custom base URL")
    model: str | None = Field(default=None, description="Optional custom model name")


@app.post("/config/api-key")
def update_api_key(req: ApiKeyUpdateRequest):
    key = req.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    import re
    env_path = Path(".env")
    env_content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""

    if req.provider.lower() == "groq":
        os.environ["GROQ_API_KEY"] = key
        if re.search(r"^GROQ_API_KEY=.*$", env_content, flags=re.MULTILINE):
            env_content = re.sub(r"^GROQ_API_KEY=.*$", f"GROQ_API_KEY={key}", env_content, flags=re.MULTILINE)
        else:
            env_content += f"\nGROQ_API_KEY={key}\n"

        if req.base_url:
            os.environ["GROQ_BASE_URL"] = req.base_url.strip()
            if re.search(r"^GROQ_BASE_URL=.*$", env_content, flags=re.MULTILINE):
                env_content = re.sub(r"^GROQ_BASE_URL=.*$", f"GROQ_BASE_URL={req.base_url.strip()}", env_content, flags=re.MULTILINE)
            else:
                env_content += f"\nGROQ_BASE_URL={req.base_url.strip()}\n"

        if req.model:
            os.environ["GROQ_MODEL"] = req.model.strip()
            if re.search(r"^GROQ_MODEL=.*$", env_content, flags=re.MULTILINE):
                env_content = re.sub(r"^GROQ_MODEL=.*$", f"GROQ_MODEL={req.model.strip()}", env_content, flags=re.MULTILINE)
            else:
                env_content += f"\nGROQ_MODEL={req.model.strip()}\n"

    elif req.provider.lower() == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = key
        if re.search(r"^ANTHROPIC_API_KEY=.*$", env_content, flags=re.MULTILINE):
            env_content = re.sub(r"^ANTHROPIC_API_KEY=.*$", f"ANTHROPIC_API_KEY={key}", env_content, flags=re.MULTILINE)
        else:
            env_content += f"\nANTHROPIC_API_KEY={key}\n"
    else:
        raise HTTPException(status_code=400, detail="Provider must be 'groq' or 'anthropic'")

    env_path.write_text(env_content, encoding="utf-8")

    from app.llm.model import get_llm
    get_llm.cache_clear()

    return {
        "status": "ok",
        "has_api_key": True,
        "llm_model": get_active_model_info(),
        "provider": req.provider,
    }


@app.get("/config/test-llm")
@app.post("/config/test-llm")
def test_llm_connection():
    """Diagnostic endpoint to safely test LLM connectivity without exposing secrets."""
    from app.llm.model import test_groq_connection
    return test_groq_connection()


@app.get("/history")
def list_history():
    with SessionLocal() as db:
        rows = db.query(ResearchHistory).order_by(ResearchHistory.id.desc()).limit(20).all()
        return [
            {
                "id": r.id,
                "question": r.user_query,
                "answer": r.answer,
                "sources": r.sources,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


@app.delete("/history")
def clear_all_history():
    with SessionLocal() as db:
        deleted = db.query(ResearchHistory).delete()
        db.commit()
        return {"status": "ok", "deleted_count": deleted}


@app.delete("/history/{rid}")
def delete_history_item(rid: int):
    with SessionLocal() as db:
        row = db.get(ResearchHistory, rid)
        if not row:
            raise HTTPException(404, "History record not found")
        db.delete(row)
        db.commit()
        return {"status": "ok", "deleted_id": rid}


@app.delete("/research/{rid}")
def delete_research(rid: int):
    return delete_history_item(rid)



@app.get("/documents")
def list_documents():
    with SessionLocal() as db:
        docs = db.query(Document).order_by(Document.id.desc()).all()
        return [
            {
                "id": d.id,
                "title": d.title,
                "authority": d.authority,
                "source_url": d.source_url,
                "document_type": d.document_type,
                "publication_date": d.publication_date,
                "updated_date": d.updated_date,
                "version": d.version,
                "indexed": d.indexed,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]


@app.get("/documents/{did}/text")
def get_document_text(did: int):
    from app.rag.loader import load_file
    with SessionLocal() as db:
        doc = db.get(Document, did)
        if not doc:
            raise HTTPException(404, "Document not found")
        p = Path(doc.file_path)
        if not p.exists():
            raise HTTPException(404, f"Document file not found at {doc.file_path}")
        try:
            pages = load_file(p, meta={"title": doc.title, "authority": doc.authority})
            full_text = "\n\n".join(pg.page_content for pg in pages)
            return {
                "id": doc.id,
                "title": doc.title,
                "authority": doc.authority,
                "source_url": doc.source_url,
                "document_type": doc.document_type,
                "publication_date": doc.publication_date,
                "updated_date": doc.updated_date,
                "pages_count": len(pages),
                "text": full_text,
            }
        except Exception:
            try:
                raw_text = p.read_text(encoding="utf-8", errors="ignore")
                return {
                    "id": doc.id,
                    "title": doc.title,
                    "authority": doc.authority,
                    "source_url": doc.source_url,
                    "document_type": doc.document_type,
                    "publication_date": doc.publication_date,
                    "updated_date": doc.updated_date,
                    "pages_count": 1,
                    "text": raw_text,
                }
            except Exception as e2:
                raise HTTPException(500, f"Failed to load document text: {e2}")


@app.get("/schemes/raw-budget")
def list_raw_budget_schemes():
    schemes_file = Path("data/raw/maharashtra_agriculture_schemes_2026_2027.json")
    if not schemes_file.exists():
        return []
    import json
    with open(schemes_file, "r", encoding="utf-8") as f:
        return json.load(f)


def local_grounded_research(question: str, language: str = "auto", scheme_id: str | None = None) -> dict:
    from app.agents.classifier import OUT_OF_SCOPE_RESPONSE, classify
    from app.rag.router import NO_DOCUMENTS_RESPONSE, get_route
    from app.utils.language import resolve_language, UI_STRINGS
    from app.agents.farmer_explainer import format_farmer_kcc_answer, format_farmer_general_answer, format_farmer_scheme_answer

    target_lang, detected_lang = resolve_language(language, question)

    scoped_scheme = None
    if scheme_id:
        from app.schemes.pipeline import get_scheme_by_id_or_code
        with SessionLocal() as db:
            s_obj = get_scheme_by_id_or_code(scheme_id, db=db)
            if s_obj:
                scoped_scheme = s_obj.to_dict()

    from app.schemes.pipeline import find_explicit_scheme_in_query, find_matching_scheme_for_query
    explicit_scheme = find_explicit_scheme_in_query(question)
    explicit_dict = explicit_scheme.to_dict() if explicit_scheme else None

    # Handle cross-scheme question when scoped to a specific scheme
    switch_notice = ""
    active_scheme = scoped_scheme
    if scoped_scheme:
        if explicit_dict:
            s_cid = scoped_scheme.get("scheme_id") or str(scoped_scheme.get("id"))
            m_cid = explicit_dict.get("scheme_id") or str(explicit_dict.get("id"))
            if s_cid != m_cid:
                # User is explicitly asking about another scheme (Requirement 6)
                active_scheme = explicit_dict
                if target_lang == "mr":
                    switch_notice = f"> ℹ️ **सूचना:** आपण सध्या **{scoped_scheme.get('scheme_name')}** पाहत आहात, परंतु आपला प्रश्न **{explicit_dict.get('scheme_name')}** बद्दल विचारला गेला आहे. खाली **{explicit_dict.get('scheme_name')}** ची अधिकृत माहिती दिली आहे:\n\n"
                elif target_lang == "hi":
                    switch_notice = f"> ℹ️ **सूचना:** आप वर्तमान में **{scoped_scheme.get('scheme_name')}** देख रहे हैं, लेकिन आपका प्रश्न **{explicit_dict.get('scheme_name')}** के संबंध में है। नीचे **{explicit_dict.get('scheme_name')}** की सत्यापित जानकारी दी गई है:\n\n"
                else:
                    switch_notice = f"> ℹ️ **Notice:** You are currently viewing **{scoped_scheme.get('scheme_name')}**, but your question is about **{explicit_dict.get('scheme_name')}**. Below is verified information for **{explicit_dict.get('scheme_name')}**:\n\n"
        else:
            # Question does not explicitly name another scheme; preserve scoped scheme isolation
            active_scheme = scoped_scheme
    else:
        # General chat: use explicitly mentioned scheme, or heuristic query matching
        if explicit_dict:
            active_scheme = explicit_dict
        else:
            matched_scheme = find_matching_scheme_for_query(question)
            active_scheme = matched_scheme.to_dict() if matched_scheme else None

    classification = classify(question)
    cat = classification.get("category", "out_of_scope")
    scope = classification.get("scope", "out_of_scope")

    if active_scheme:
        scope = "in_scope"
        cat = active_scheme.get("category", cat)

    if scope == "out_of_scope" and not active_scheme:
        out_msg = OUT_OF_SCOPE_RESPONSE
        if target_lang == "mr":
            out_msg = "हा प्रश्न एआय शासकीय संशोधन प्रतिनिधीच्या कार्यक्षेत्राबाहेर आहे. कृपया शासन योजना किंवा शेतीविषयक प्रश्न विचारावा."
        elif target_lang == "hi":
            out_msg = "यह प्रश्न एआई सरकारी अनुसंधान एजेंट के दायरे से बाहर है। कृपया कोई सरकारी योजना या कृषि से संबंधित प्रश्न पूछें।"
        return {
            "status": "out_of_scope",
            "category": cat,
            "scope": scope,
            "language": target_lang,
            "detected_language": detected_lang,
            "final_answer": out_msg,
            "citations": [],
            "practical_steps": [],
            "clarifying_question": None,
            "missing_evidence_warning": False,
            "conflicts": [],
            "unsupported": [],
            "retrieved_chunks": [],
        }

    from app.config import RELEVANCE_THRESHOLD
    from app.tools.document_search import vector_search
    from app.utils.citations import (
        build_citations,
        filter_supported_evidence,
        format_citations_markdown,
        reconcile_citations_with_answer,
    )

    q_lower = question.lower()
    is_kcc = (
        not active_scheme
        and (
            any(k in q_lower for k in ["kisan credit card", "kcc", "crop loan", "किसान क्रेडिट कार्ड", "केसीसी", "पीक कर्ज"])
            or ("credit" in q_lower and "farmer" in q_lower)
        )
    )

    # Retrieval: If scoped to an active scheme, STRICTLY filter ChromaDB to that scheme_id!
    if active_scheme and active_scheme.get("scheme_id"):
        filters = {"scheme_id": active_scheme["scheme_id"]}
        raw_results = vector_search(question, k=8, filters=filters)
        scheme_n = active_scheme.get("scheme_name", "")
        for aq in [
            f"{scheme_n} eligibility criteria benefits installments DBT Aadhaar documents required",
            f"{scheme_n} application procedure guidelines official portal",
        ]:
            for item in vector_search(aq, k=4, filters=filters):
                raw_results.append(item)
    else:
        route = get_route(cat)
        if not route.get("has_documents", True):
            no_doc_msg = NO_DOCUMENTS_RESPONSE
            if target_lang == "mr":
                no_doc_msg = f"या श्रेणीसाठी ({cat}) सध्या कोणतीही अधिकृत शासकीय मार्गदर्शक तत्त्वे किंवा दस्तऐवज अनुक्रमित नाहीत."
            elif target_lang == "hi":
                no_doc_msg = f"इस श्रेणी ({cat}) के लिए वर्तमान में कोई आधिकारिक सरकारी दिशानिर्देश या दस्तावेज अनुक्रमित नहीं हैं।"
            return {
                "status": "no_documents_for_category",
                "category": cat,
                "scope": scope,
                "language": target_lang,
                "detected_language": detected_lang,
                "final_answer": no_doc_msg,
                "citations": [],
                "practical_steps": [],
                "clarifying_question": None,
                "missing_evidence_warning": True,
                "conflicts": [],
                "unsupported": [],
                "retrieved_chunks": [],
            }

        filters = route.get("filter")
        raw_results = vector_search(question, k=8, filters=filters)

        aspect_queries = []
        if active_scheme:
            aspect_queries.append(f"{active_scheme['scheme_name']} eligibility criteria benefits installments DBT Aadhaar documents required")
            aspect_queries.append(f"{active_scheme['scheme_name']} official guidelines procedures")

        if is_kcc:
            aspect_queries.extend([
                "Kisan Credit Card KCC eligibility criteria owner cultivator tenant farmer scale of finance dltc",
                "Kisan Credit Card KCC interest subvention 7% 4% prompt repayment incentive PRI collateral 160000",
                "Kisan Credit Card KCC application procedure documents required land records 7/12 RoR Aadhaar passbook",
                "Kisan Credit Card KCC helpline kisan call centre 1800-180-1551 taluka agriculture officer grievance",
            ])

        # PMFBY / Crop Insurance
        if any(k in q_lower for k in ["pmfby", "fasal bima", "crop insurance", "पीक विमा", "फसल बीमा"]):
            aspect_queries.extend([
                "Pradhan Mantri Fasal Bima Yojana PMFBY crop insurance premium rates Kharif 2% Rabi 1.5% commercial 5%",
                "PMFBY post harvest localized calamities crop insurance compensation claim coverage stages",
            ])

        # Land Records / 7/12
        if any(k in q_lower for k in ["7/12", "ror", "record of rights", "bhulekh", "भूलेख", "उतारा", "सातबारा", "tenant"]):
            aspect_queries.extend([
                "Record of Rights RoR 7/12 extract digital Bhulekh state portal land verification",
                "Tenant farmers self declaration form oral lessees agricultural credit verification",
            ])

        # Fertilizers / Soil Health Card
        if any(k in q_lower for k in ["soil health", "मृदा", "माती", "urea", "युरिया", "यूरिया"]):
            aspect_queries.extend([
                "Soil Health Card 12 parameters macro secondary micronutrient physical testing",
                "Neem Coated Urea nitrification inhibitor 10% 15% slow release nitrogen use efficiency",
            ])

        # PM-KUSUM Solar Pumps
        if any(k in q_lower for k in ["kusum", "कुसुम", "solar pump", "सोलर पंप"]):
            aspect_queries.extend([
                "PM-KUSUM Component B stand-alone solar agriculture pumps 7.5 HP CFA 30% state subsidy 30%",
            ])

        # SMAM Farm Machinery
        if any(k in q_lower for k in ["smam", "mechanization", "यांत्रिकीकरण", "machinery"]):
            aspect_queries.extend([
                "Sub-Mission on Agricultural Mechanization SMAM farm machinery 40% 50% subsidy women small farmers Custom Hiring Centres",
            ])

        if aspect_queries:
            for aq in aspect_queries:
                for item in vector_search(aq, k=4, filters=filters):
                    raw_results.append(item)

    # Deduplicate results by chunk_id/content_hash
    seen_items: dict[tuple, dict] = {}
    for r in raw_results:
        key = (r.get("metadata", {}).get("content_hash"), r.get("metadata", {}).get("chunk_id", r.get("text", "")[:60]))
        if key in seen_items:
            if r.get("similarity_score", 0.0) > seen_items[key].get("similarity_score", 0.0):
                seen_items[key] = r
        else:
            seen_items[key] = r
    raw_results = list(seen_items.values())

    scores = [r.get("similarity_score", 0.0) for r in raw_results]
    relevant_results = [r for r in raw_results if r.get("similarity_score", 0.0) >= RELEVANCE_THRESHOLD]

    log.info(
        "RETRIEVAL: Query='%s' | ScopedScheme='%s' | Cat='%s' | Lang='%s' | Raw count=%d | Accepted=%d",
        question,
        active_scheme.get("scheme_id") if active_scheme else None,
        cat,
        target_lang,
        len(raw_results),
        len(relevant_results),
    )

    # Filter supported evidence
    supported_results, rejected_items = filter_supported_evidence(question, relevant_results, category=cat)

    if not supported_results:
        if active_scheme:
            # Ground directly in the active scheme's verified structured data without cross-scheme hallucination
            answer_body, practical_steps, clarifying_q, missing_docs_flag = format_farmer_scheme_answer(
                question, active_scheme, [], language=target_lang
            )
            citations = []
            if active_scheme.get("official_source_url"):
                citations = [{
                    "citation_id": 1,
                    "marker": "[1]",
                    "source": active_scheme.get("scheme_name", "Official Portal"),
                    "page": 1,
                    "department": active_scheme.get("authority", "Government Department"),
                    "year": "2025-26",
                    "document_type": "Official Scheme Portal",
                    "url": active_scheme.get("official_source_url"),
                    "snippet": active_scheme.get("description", "")[:200],
                }]
            final_answer = switch_notice + answer_body + format_citations_markdown(citations, language=target_lang)
            return {
                "status": "completed",
                "category": cat,
                "scope": scope,
                "language": target_lang,
                "detected_language": detected_lang,
                "final_answer": final_answer,
                "citations": citations,
                "matched_scheme": active_scheme,
                "practical_steps": practical_steps,
                "clarifying_question": clarifying_q,
                "missing_evidence_warning": True,
                "conflicts": [],
                "unsupported": [],
                "retrieved_chunks": [],
            }
        else:
            insuf_msg = "No sufficiently relevant official information was found in the indexed government sources for this question."
            if target_lang == "mr":
                insuf_msg = "या प्रश्नासाठी अनुक्रमित सरकारी दस्तऐवजांमध्ये पुरेशी सुसंगत अधिकृत माहिती आढळली नाही. कृपया स्थानिक शासकीय कार्यालयाशी संपर्क साधावा."
            elif target_lang == "hi":
                insuf_msg = "इस प्रश्न के लिए अनुक्रमित सरकारी स्रोतों में पर्याप्त प्रासंगिक आधिकारिक जानकारी नहीं मिली। कृपया अपने स्थानीय सरकारी कार्यालय से संपर्क करें।"
            return {
                "status": "insufficient_evidence",
                "category": cat,
                "scope": scope,
                "language": target_lang,
                "detected_language": detected_lang,
                "final_answer": insuf_msg,
                "citations": [],
                "practical_steps": [],
                "clarifying_question": None,
                "missing_evidence_warning": True,
                "conflicts": [],
                "unsupported": [],
                "retrieved_chunks": [],
            }

    citations = build_citations(supported_results)

    if active_scheme:
        answer_body, practical_steps, clarifying_q, missing_docs_flag = format_farmer_scheme_answer(
            question, active_scheme, supported_results, language=target_lang
        )
    elif is_kcc:
        answer_body, practical_steps, clarifying_q, missing_docs_flag = format_farmer_kcc_answer(
            question, supported_results, language=target_lang
        )
    else:
        answer_body, practical_steps, clarifying_q, missing_docs_flag = format_farmer_general_answer(
            question, supported_results, category=cat, language=target_lang
        )

    reconciled_answer, reconciled_citations = reconcile_citations_with_answer(answer_body, citations)
    final_answer = switch_notice + reconciled_answer + format_citations_markdown(reconciled_citations, language=target_lang)

    retrieved_chunks = []
    for idx, item in enumerate(supported_results, start=1):
        meta = item.get("metadata", {})
        retrieved_chunks.append({
            "chunk_index": idx,
            "source": meta.get("source") or meta.get("title", "Unknown Source"),
            "page": meta.get("page") or meta.get("page_number", 1),
            "department": meta.get("department") or meta.get("authority", "Government Authority"),
            "year": meta.get("year", "2025-26"),
            "document_type": meta.get("document_type", "Document"),
            "similarity_score": item.get("similarity_score", 0.0),
            "text": item.get("text", "").strip(),
        })

    return {
        "status": "completed",
        "category": cat,
        "scope": scope,
        "language": target_lang,
        "detected_language": detected_lang,
        "final_answer": final_answer,
        "citations": reconciled_citations,
        "matched_scheme": active_scheme or matched_dict,
        "practical_steps": practical_steps,
        "clarifying_question": clarifying_q,
        "missing_evidence_warning": missing_docs_flag,
        "conflicts": [],
        "unsupported": [],
        "retrieved_chunks": retrieved_chunks,
    }


@app.post("/research")
def research(req: ResearchRequest):
    q = req.question.strip()
    from app.utils.language import resolve_language
    target_lang, detected_lang = resolve_language(req.language, q)

    scheme_id = req.scheme_id

    if has_llm_key():
        from app.graph.workflow import run_research
        try:
            state = run_research(q, language=target_lang, scheme_id=scheme_id)
        except Exception as exc:
            log.exception("LLM research failed, falling back to vector search: %s", exc)
            state = local_grounded_research(q, language=target_lang, scheme_id=scheme_id)
    else:
        # Grounded local vector search when no external API key is set
        state = local_grounded_research(q, language=target_lang, scheme_id=scheme_id)

    matched_scheme = state.get("matched_scheme")
    if not matched_scheme and scheme_id:
        from app.schemes.pipeline import get_scheme_by_id_or_code
        with SessionLocal() as db:
            s_obj = get_scheme_by_id_or_code(scheme_id, db=db)
            matched_scheme = s_obj.to_dict() if s_obj else None
    elif not matched_scheme:
        from app.schemes.pipeline import find_explicit_scheme_in_query, find_matching_scheme_for_query
        m = find_explicit_scheme_in_query(q) or find_matching_scheme_for_query(q)
        matched_scheme = m.to_dict() if m else None

    with SessionLocal() as db:
        row = ResearchHistory(
            user_query=q,
            answer=state.get("final_answer", ""),
            sources=state.get("citations", []),
            status=state.get("status", "completed"),
        )
        db.add(row)
        db.commit()
        rid = row.id

    return {
        "id": rid,
        "status": state.get("status"),
        "category": state.get("category"),
        "scope": state.get("scope"),
        "language": state.get("language", target_lang),
        "detected_language": state.get("detected_language", detected_lang),
        "answer": state.get("final_answer"),
        "sources": state.get("citations", []),
        "matched_scheme": matched_scheme,
        "retrieved_chunks": state.get("retrieved_chunks", []),
        "practical_steps": state.get("practical_steps", []),
        "clarifying_question": state.get("clarifying_question"),
        "missing_evidence_warning": state.get("missing_evidence_warning", False),
        "conflicts": state.get("conflicts", []),
        "unsupported": state.get("unsupported", []),
    }


class SchemeCreateRequest(BaseModel):
    scheme_id: str | None = None
    scheme_name: str = Field(min_length=2)
    hindi_name: str = Field(min_length=2)
    category: str = Field(default="General")
    department: str = Field(default="")
    level: str = Field(default="Central / State")
    beneficiary: str = Field(default="Eligible Citizens")
    eligibility: str = Field(default="N/A")
    benefits: str = Field(default="N/A")
    documents: str = Field(default="Aadhaar Card, Bank Passbook")
    state_district: str = Field(default="Central / All India")
    status: str = Field(default="Active")
    official_source_url: str = Field(default="")
    application_url: str = Field(default="")
    authority: str = Field(default="")
    verification_status: str = Field(default="Verified")
    is_discontinued: bool = Field(default=False)


class SchemeExtractionRequest(BaseModel):
    text: str = Field(min_length=10)
    scheme_name: str = ""
    category: str = ""
    authority: str = ""
    source_url: str = ""


@app.get("/schemes/sections")
def list_scheme_sections():
    from app.schemes.pipeline import get_dataset_sections_summary
    return get_dataset_sections_summary()

@app.get("/api/schemes")
def get_api_schemes(limit: int = 50, q: str = "", category: str = "all"):
    from sqlalchemy import or_
    with SessionLocal() as db:
        query = db.query(Scheme)
        if q:
            query = query.filter(
                or_(
                    Scheme.scheme_name.ilike(f"%{q}%"),
                    Scheme.hindi_name.ilike(f"%{q}%"),
                    Scheme.category.ilike(f"%{q}%"),
                )
            )
        if category and category != "all":
            query = query.filter(Scheme.category.ilike(f"%{category}%"))
        schemes = query.limit(limit).all()
        return {
            "schemes": [
                {
                    "id": s.id,
                    "scheme_id": s.scheme_id,
                    "name": s.scheme_name,
                    "scheme_name": s.scheme_name,
                    "category": s.category,
                    "hindi_name": s.hindi_name,
                    "beneficiary": s.beneficiary,
                    "benefits": s.benefits,
                    "eligibility": s.eligibility,
                    "documents": s.documents,
                    "status": s.status,
                    "state_district": s.state_district,
                    "official_source_url": s.official_source_url,
                }
                for s in schemes
            ]
        }


@app.get("/schemes")
def list_schemes(
    response: Response,
    q: str = "",
    category: str = "all",
    state: str = "all",
    status: str = "all",
    section_group: str = "all",
    section: str = "all",
    limit: int = 50,
    offset: int = 0,
    page: int | None = None,
    page_size: int | None = None,
):
    from app.schemes.pipeline import search_schemes_in_db

    if page is not None:
        p_size = max(1, page_size or limit or 10)
        p_num = max(1, page)
        schemes, total_count, total_pages = search_schemes_in_db(
            query=q,
            category=None if category == "all" else category,
            state=None if state == "all" else state,
            status=None if status == "all" else status,
            section_group=None if section_group == "all" else section_group,
            section=None if section == "all" else section,
            page=p_num,
            page_size=p_size,
            return_total=True,
        )
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Total-Pages"] = str(total_pages)
        response.headers["X-Page"] = str(p_num)
        response.headers["X-Page-Size"] = str(p_size)
        return {
            "items": [s.to_dict() for s in schemes],
            "total_count": total_count,
            "page": p_num,
            "page_size": p_size,
            "total_pages": total_pages,
            "has_next": p_num < total_pages,
            "has_prev": p_num > 1,
        }
    else:
        schemes, total_count, total_pages = search_schemes_in_db(
            query=q,
            category=None if category == "all" else category,
            state=None if state == "all" else state,
            status=None if status == "all" else status,
            section_group=None if section_group == "all" else section_group,
            section=None if section == "all" else section,
            limit=limit,
            offset=offset,
            return_total=True,
        )
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Total-Pages"] = str(total_pages)
        return [s.to_dict() for s in schemes]


@app.get("/schemes/{sid}")
def get_scheme(sid: str):
    from app.schemes.pipeline import get_scheme_by_id_or_code
    with SessionLocal() as db:
        scheme = get_scheme_by_id_or_code(sid, db=db)
        if not scheme:
            raise HTTPException(404, f"Scheme '{sid}' not found")
        return scheme.to_dict()


@app.post("/schemes", dependencies=[Depends(require_admin)])
def create_scheme(req: SchemeCreateRequest):
    from app.schemes.updater import detect_and_upsert_scheme
    res = detect_and_upsert_scheme(req.model_dump())
    return res["scheme"].to_dict()


@app.post("/schemes/seed", dependencies=[Depends(require_admin)])
def seed_schemes():
    from app.schemes.pipeline import seed_official_schemes
    count = seed_official_schemes()
    return {"message": f"Successfully seeded {count} official schemes"}


@app.post("/schemes/extract", dependencies=[Depends(require_admin)])
def extract_scheme(req: SchemeExtractionRequest):
    from app.schemes.pipeline import extract_structured_scheme, ingest_scheme_to_db
    extracted = extract_structured_scheme(req.text, default_meta={
        "scheme_name": req.scheme_name,
        "category": req.category,
        "authority": req.authority,
        "source_url": req.source_url,
    })
    saved = ingest_scheme_to_db(extracted)
    return {"extracted": extracted, "saved": saved.to_dict()}


@app.get("/research/{rid}")
def get_research(rid: int):
    with SessionLocal() as db:
        row = db.get(ResearchHistory, rid)
        if not row:
            raise HTTPException(404, "Not found")
        return {"id": row.id, "question": row.user_query, "answer": row.answer,
                "sources": row.sources, "status": row.status, "created_at": row.created_at}


@app.post("/documents/upload", dependencies=[Depends(require_admin)])
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    authority: str = Form("unknown"),
    source_url: str = Form(""),
    document_type: str = Form(""),
    publication_date: str = Form(""),
    updated_date: str = Form(""),
    version: str = Form(""),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"File type {ext or '(none)'} not allowed")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 20 MB)")
    path = RAW_DIR / f"{secrets.token_hex(8)}{ext}"  # never trust the client filename
    path.write_bytes(data)
    with SessionLocal() as db:
        doc = Document(title=title, authority=authority, source_url=source_url,
                       document_type=document_type or ext.lstrip("."),
                       publication_date=publication_date, updated_date=updated_date,
                       version=version, file_path=str(path))
        db.add(doc)
        db.commit()
        return {"id": doc.id, "title": doc.title, "indexed": False}


@app.post("/documents/index", dependencies=[Depends(require_admin)])
def index_documents_endpoint():
    from app.rag.loader import load_file
    from app.rag.retriever import index_documents

    indexed, chunks = 0, 0
    with SessionLocal() as db:
        for doc in db.query(Document).filter(Document.indexed.is_(False)).all():
            meta = {c: getattr(doc, c) for c in
                    ("title", "authority", "source_url", "document_type",
                     "publication_date", "updated_date", "version")}
            pages = load_file(doc.file_path, meta)
            chunks += index_documents(pages)
            doc.content_hash = pages[0].metadata["content_hash"] if pages else ""
            doc.indexed = True
            indexed += 1
        db.commit()
    return {"documents_indexed": indexed, "chunks_added": chunks}


class SyncTriggerRequest(BaseModel):
    sources: list[str] | None = None
    dry_run: bool = False


@app.post("/api/sync/run")
@app.post("/sync/run")
def trigger_sync_pipeline(req: SyncTriggerRequest = None):
    """Trigger the automatic government scheme synchronization pipeline immediately."""
    from app.schemes.updater import sync_all_registered_sources
    source_filter = req.sources if req else None
    return sync_all_registered_sources(source_names=source_filter)


@app.get("/api/sync/status")
@app.get("/sync/status")
def get_sync_status():
    """Get active sync status, last execution results, and scheme count summaries."""
    from app.schemes.updater import get_sync_pipeline_status
    return get_sync_pipeline_status()


@app.get("/api/sync/logs")
@app.get("/sync/logs")
def get_sync_logs(limit: int = 50, offset: int = 0):
    """Get execution logs and failure details for source synchronization runs."""
    from app.database.db import SyncLog
    with SessionLocal() as db:
        total = db.query(SyncLog).count()
        logs = (
            db.query(SyncLog)
            .order_by(SyncLog.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "total": total,
            "items": [l.to_dict() for l in logs],
        }


@app.post("/api/sync/retry")
@app.post("/sync/retry")
def retry_failed_sync():
    """Retry any failed sources from the most recent synchronization runs."""
    from app.schemes.updater import retry_failed_sources
    return retry_failed_sources()


@app.get("/schemes/{sid}/history")
@app.get("/api/schemes/{sid}/history")
def get_scheme_history_endpoint(sid: str):
    """Retrieve full revision history, content hash changes, and diffs for a specific scheme."""
    from app.schemes.pipeline import get_scheme_by_id_or_code
    from app.database.db import SchemeHistory
    with SessionLocal() as db:
        scheme = get_scheme_by_id_or_code(sid, db=db)
        if not scheme:
            raise HTTPException(404, f"Scheme '{sid}' not found")
        canonical_id = scheme.scheme_id
        history = (
            db.query(SchemeHistory)
            .filter(SchemeHistory.scheme_id == canonical_id)
            .order_by(SchemeHistory.recorded_at.desc())
            .all()
        )
        return [h.to_dict() for h in history]


@app.get("/sources/registry")
def get_source_registry_endpoint():
    from app.sources.source_registry import registry
    return [s.to_dict() for s in registry.list_sources()]


@app.get("/sources/scheduler")
def get_scheduler_status_endpoint():
    from app.sources.scheduler import get_scheduler_status
    return get_scheduler_status()


@app.post("/sources/update", dependencies=[Depends(require_admin)])
def trigger_sources_update_endpoint(dry_run: bool = False):
    from app.sources.pipeline import ingest_all_registered_sources
    return ingest_all_registered_sources(dry_run=dry_run)


@app.get("/sources/{sid}")
def get_source(sid: int):
    with SessionLocal() as db:
        doc = db.get(Document, sid)
        if not doc:
            raise HTTPException(404, "Not found")
        return {c: getattr(doc, c) for c in
                ("id", "title", "authority", "source_url", "document_type",
                 "publication_date", "updated_date", "version", "indexed")}


@app.post("/scraper/import-csv")
async def import_scraped_csv(file: UploadFile = File(...)):
    """Import scraped government schemes from CSV, normalize fields, upsert to SQL, and index in ChromaDB."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file."
        )

    try:
        content = await file.read()
        from app.sources.csv_importer import process_scraped_csv
        return process_scraped_csv(content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process CSV: {exc}")


@app.post("/scraper/import-json")
async def import_scraped_json(file: UploadFile = File(...)):
    """Import scraped government schemes from JSON file, normalize fields, upsert to SQL, and index in ChromaDB."""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a JSON file."
        )

    try:
        content = await file.read()
        from app.sources.csv_importer import process_scraped_json
        return process_scraped_json(content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process JSON: {exc}")


@app.post("/scraper/ingest")
async def ingest_scraped_data(request: Request):
    """Direct API / Webhook ingestion endpoint for Apify, web scrapers, and automated pipelines.
    
    Accepts JSON body: array of schemes `[{"scheme_name": "...", "official_url": "..."}]`
    or wrapped object `{"schemes": [...]}` / `{"items": [...]}`.
    Normalizes with Python, deduplicates via canonical scheme IDs, upserts to PostgreSQL/SQLite,
    and indexes into ChromaDB embeddings.
    """
    try:
        body = await request.json()
        from app.sources.csv_importer import process_scraped_json
        return process_scraped_json(body)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to ingest scraped payload: {exc}")



# Static asset handling with dist/public fallback, caching headers, and SVG fallback
frontend_dist = Path("frontend/dist")
frontend_public = Path("frontend/public")


@app.get("/assets/{asset_path:path}")
async def serve_asset(asset_path: str):
    headers = {"Cache-Control": "public, max-age=86400"}
    # 1. Check frontend/dist/assets
    dist_file = frontend_dist / "assets" / asset_path
    if dist_file.is_file():
        return FileResponse(dist_file, headers=headers)

    # 2. Check frontend/public/assets fallback
    pub_file = frontend_public / "assets" / asset_path
    if pub_file.is_file():
        return FileResponse(pub_file, headers=headers)

    # 3. Clean SVG image fallback for missing/broken image requests
    if any(asset_path.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"]):
        fallback_file = frontend_public / "assets" / "scheme_fallback.svg"
        if not fallback_file.is_file():
            fallback_file = frontend_dist / "assets" / "scheme_fallback.svg"
        if fallback_file.is_file():
            return FileResponse(fallback_file, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})

    raise HTTPException(status_code=404, detail="Asset not found")


if frontend_dist.exists():
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")


