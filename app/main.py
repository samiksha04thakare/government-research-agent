import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
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
        if db.query(Scheme).count() == 0:
            from app.schemes.pipeline import seed_official_schemes
            seed_official_schemes(db=db)
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


class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    language: str = Field(default="auto", description="Response language: 'auto', 'en', 'hi', or 'mr'")


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
    return {
        "status": "ok",
        "has_api_key": has_llm_key(),
        "llm_model": get_active_model_info(),
        "indexed_documents": indexed_count,
        "total_documents": total_count,
        "structured_schemes": schemes_count,
    }


class ApiKeyUpdateRequest(BaseModel):
    provider: str = Field(description="'groq' or 'anthropic'")
    api_key: str = Field(description="The API key value")


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


def local_grounded_research(question: str, language: str = "auto") -> dict:
    from app.agents.classifier import OUT_OF_SCOPE_RESPONSE, classify
    from app.rag.router import NO_DOCUMENTS_RESPONSE, get_route
    from app.utils.language import resolve_language, UI_STRINGS
    from app.agents.farmer_explainer import format_farmer_kcc_answer, format_farmer_general_answer

    target_lang, detected_lang = resolve_language(language, question)

    classification = classify(question)
    cat = classification.get("category", "out_of_scope")
    scope = classification.get("scope", "out_of_scope")

    if scope == "out_of_scope":
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

    from app.config import RELEVANCE_THRESHOLD
    from app.tools.document_search import vector_search
    from app.utils.citations import (
        build_citations,
        filter_supported_evidence,
        format_citations_markdown,
        reconcile_citations_with_answer,
    )

    # Filtered ChromaDB retrieval based on category route
    filters = route.get("filter")
    raw_results = vector_search(question, k=8, filters=filters)

    q_lower = question.lower()
    is_kcc = (
        any(k in q_lower for k in ["kisan credit card", "kcc", "crop loan", "किसान क्रेडिट कार्ड", "केसीसी", "पीक कर्ज"])
        or ("credit" in q_lower and "farmer" in q_lower)
    )

    from app.schemes.pipeline import find_matching_scheme_for_query
    matched_scheme = find_matching_scheme_for_query(question)
    matched_dict = matched_scheme.to_dict() if matched_scheme else None

    aspect_queries = []
    if matched_scheme:
        aspect_queries.append(f"{matched_scheme.scheme_name} eligibility criteria benefits installments DBT Aadhaar documents required")
        aspect_queries.append(f"{matched_scheme.scheme_name} official guidelines procedures")

    if is_kcc:
        aspect_queries.extend([
            "Kisan Credit Card KCC eligibility criteria owner cultivator tenant farmer scale of finance dltc",
            "Kisan Credit Card KCC interest subvention 7% 4% prompt repayment incentive PRI collateral 160000",
            "Kisan Credit Card KCC application procedure documents required land records 7/12 RoR Aadhaar passbook",
            "Kisan Credit Card KCC helpline kisan call centre 1800-180-1551 taluka agriculture officer grievance",
            "किसान क्रेडिट कार्ड KCC आवेदन प्रक्रिया आवश्यक दस्तावेज 7/12 खतौनी आधार पासबुक",
            "किसान क्रेडिट कार्ड KCC हेल्पलाइन किसान कॉल सेंटर 1800-180-1551 कृषि अधिकारी",
            "किसान क्रेडिट कार्ड KCC अर्ज प्रक्रिया कागदपत्रे 7/12 उतारा आधार बँक पासबुक",
            "किसान क्रेडिट कार्ड KCC हेल्पलाईन किसान कॉल सेंटर 1800-180-1551 तालुका कृषी अधिकारी",
        ])

    # PMFBY / Crop Insurance
    if any(k in q_lower for k in ["pmfby", "fasal bima", "crop insurance", "पीक विमा", "फसल बीमा", "विमा हप्ता", "प्रीमियम"]):
        aspect_queries.extend([
            "Pradhan Mantri Fasal Bima Yojana PMFBY crop insurance premium rates Kharif 2% Rabi 1.5% commercial 5%",
            "PMFBY post harvest localized calamities crop insurance compensation claim coverage stages",
        ])

    # Land Records / 7/12 / Tenant farmers
    if any(k in q_lower for k in ["7/12", "ror", "record of rights", "bhulekh", "भूलेख", "उतारा", "खतौनी", "बटाईदार", "काश्तकार", "भाडेकरू", "सातबारा", "tenant"]):
        aspect_queries.extend([
            "Record of Rights RoR 7/12 extract digital Bhulekh state portal land verification",
            "Tenant farmers self declaration form oral lessees agricultural credit verification",
            "Documents required farmer verification Aadhaar mobile active bank passbook DBT",
        ])

    # Grievance / Kisan Call Centre
    if any(k in q_lower for k in ["helpline", "call centre", "कॉल सेंटर", "हेल्पलाइन", "हेल्पलाईन", "1800-180-1551", "तक्रार", "शिकायत"]):
        aspect_queries.extend([
            "Kisan Call Centre 1800-180-1551 24/7 22 regional languages grievance redressal taluka agriculture officer",
        ])

    # Pest Management (Pink Bollworm, Fall Armyworm, IPM)
    if any(k in q_lower for k in ["bollworm", "बोंडअळी", "बॉलवर्म", "armyworm", "लष्करी", "आर्मीवर्म", "कीड", "कीट", "ipm", "neem", "निंबोळी", "pheromone", "सापळे", "ट्रैप"]):
        aspect_queries.extend([
            "pink bollworm cotton ETL 8 moths per trap pheromone trap NSKE 5% neem seed kernel extract",
            "Fall Armyworm maize Spodoptera frugiperda IPM pheromone traps 5 per acre push pull strategy",
        ])

    # Fertilizers / Soil Health Card / Neem Coated Urea
    if any(k in q_lower for k in ["soil health", "मृदा", "माती", "urea", "युरिया", "यूरिया", "खत", "उर्वरक", "neem coated", "निम कोटेड", "npk"]):
        aspect_queries.extend([
            "Soil Health Card 12 parameters macro secondary micronutrient physical testing",
            "Neem Coated Urea nitrification inhibitor 10% 15% slow release nitrogen use efficiency",
        ])

    # Crop Problems / Yellowing / Heat Stress
    if any(k in q_lower for k in ["yellowing", "chlorosis", "पिवळ", "पीला", "heat stress", "उष्णता", "तणाव", "nitrogen", "नत्र"]):
        aspect_queries.extend([
            "crop leaf yellowing Nitrogen deficiency older leaves waterlogging Iron chlorosis younger leaves",
            "wheat terminal heat stress grain filling light irrigation potassium nitrate spray",
        ])

    # PM-KUSUM Solar Pumps
    if any(k in q_lower for k in ["kusum", "कुसुम", "solar pump", "सोलर पंप", "सौर"]):
        aspect_queries.extend([
            "PM-KUSUM Component B stand-alone solar agriculture pumps 7.5 HP CFA 30% state subsidy 30%",
        ])

    # SMAM Farm Machinery
    if any(k in q_lower for k in ["smam", "mechanization", "यांत्रिकीकरण", "machinery", "ट्रॅक्टर", "यंत्र"]):
        aspect_queries.extend([
            "Sub-Mission on Agricultural Mechanization SMAM farm machinery 40% 50% subsidy women small farmers Custom Hiring Centres",
        ])

    # Maharashtra Agriculture AI / BDS Outlay
    if any(k in q_lower for k in ["artificial intelligence", "ai policy", "कृत्रिम बुद्धिमत्ता", "1101100034", "outlay", "bds"]):
        aspect_queries.extend([
            "Maharashtra Agriculture Artificial Intelligence Policy 2025-2029 Scheme Code 1101100034 10000 Lakh",
        ])

    if aspect_queries:
        seen_items: dict[tuple, dict] = {
            (r.get("metadata", {}).get("content_hash"), r.get("metadata", {}).get("chunk_id", r.get("text", "")[:60])): r
            for r in raw_results
        }
        for aq in aspect_queries:
            for item in vector_search(aq, k=4, filters=filters):
                key = (item.get("metadata", {}).get("content_hash"), item.get("metadata", {}).get("chunk_id", item.get("text", "")[:60]))
                if key in seen_items:
                    if item.get("similarity_score", 0.0) > seen_items[key].get("similarity_score", 0.0):
                        seen_items[key]["similarity_score"] = item["similarity_score"]
                else:
                    seen_items[key] = item
        raw_results = list(seen_items.values())

    scores = [r.get("similarity_score", 0.0) for r in raw_results]

    # Filter by strict configurable relevance threshold
    relevant_results = [r for r in raw_results if r.get("similarity_score", 0.0) >= RELEVANCE_THRESHOLD]

    decision = "ACCEPTED" if relevant_results else "REJECTED_LOW_RELEVANCE"
    log.info(
        "RETRIEVAL: Query='%s' | Category='%s' | Lang='%s' | Retrieved document count=%d | Documents accepted after relevance filtering=%d | Relevance scores=%s | Final decision='%s' (Threshold=%.2f)",
        question,
        cat,
        target_lang,
        len(raw_results),
        len(relevant_results),
        scores,
        decision,
        RELEVANCE_THRESHOLD,
    )

    if not relevant_results:
        insuf_msg = "No sufficiently relevant official information was found in the indexed government sources for this question."
        if target_lang == "mr":
            insuf_msg = "या प्रश्नासाठी अनुक्रमित सरकारी दस्तऐवजांमध्ये पुरेशी सुसंगत अधिकृत माहिती आढळली नाही. कृपया स्थानिक कृषी कार्यालयाशी संपर्क साधावा."
        elif target_lang == "hi":
            insuf_msg = "इस प्रश्न के लिए अनुक्रमित सरकारी स्रोतों में पर्याप्त प्रासंगिक आधिकारिक जानकारी नहीं मिली। कृपया अपने स्थानीय कृषि कार्यालय से संपर्क करें।"
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

    # Step 7 Citation Audit: Inspect actual content of retrieved documents to determine whether they support claims (Requirements 5 & 6)
    supported_results, rejected_items = filter_supported_evidence(question, relevant_results, category=cat)
    if not supported_results:
        log.warning(
            "CONTENT VERIFICATION REJECTED: Retrieved %d documents passed threshold but 0 contain supporting content for query '%s'. Rejection reasons: %s",
            len(relevant_results),
            question,
            [r.get("rejection_reason") for r in rejected_items],
        )
        insuf_msg = "No sufficiently relevant official information was found in the indexed government sources for this question."
        if target_lang == "mr":
            insuf_msg = "या प्रश्नासाठी अनुक्रमित सरकारी दस्तऐवजांमध्ये पुरेशी सुसंगत अधिकृत माहिती आढळली नाही. कृपया स्थानिक कृषी कार्यालयाशी संपर्क साधावा."
        elif target_lang == "hi":
            insuf_msg = "इस प्रश्न के लिए अनुक्रमित सरकारी स्रोतों में पर्याप्त प्रासंगिक आधिकारिक जानकारी नहीं मिली। कृपया अपने स्थानीय कृषि कार्यालय से संपर्क करें।"
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

    if matched_scheme and not is_kcc:
        from app.agents.farmer_explainer import format_farmer_scheme_answer
        answer_body, practical_steps, clarifying_q, missing_docs_flag = format_farmer_scheme_answer(
            question, matched_dict, supported_results, language=target_lang
        )
    elif is_kcc:
        answer_body, practical_steps, clarifying_q, missing_docs_flag = format_farmer_kcc_answer(
            question, supported_results, language=target_lang
        )
    else:
        answer_body, practical_steps, clarifying_q, missing_docs_flag = format_farmer_general_answer(
            question, supported_results, category=cat, language=target_lang
        )

    # Reconcile citation markers with citation list (Requirement 2)
    reconciled_answer, reconciled_citations = reconcile_citations_with_answer(answer_body, citations)
    final_answer = reconciled_answer + format_citations_markdown(reconciled_citations)

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
        "matched_scheme": matched_dict,
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
    lang = req.language or "auto"

    if has_llm_key():
        from app.graph.workflow import run_research
        try:
            state = run_research(q, language=lang)
        except Exception as exc:
            log.exception("LLM research failed, falling back to vector search")
            state = local_grounded_research(q, language=lang)
    else:
        # Grounded local vector search when no external API key is set
        state = local_grounded_research(q, language=lang)

    matched_scheme = state.get("matched_scheme")
    if not matched_scheme:
        from app.schemes.pipeline import find_matching_scheme_for_query
        m = find_matching_scheme_for_query(q)
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
        "language": state.get("language", "en"),
        "detected_language": state.get("detected_language", "en"),
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
    scheme_name: str = Field(min_length=2)
    hindi_name: str = Field(min_length=2)
    category: str = Field(default="General")
    beneficiary: str = Field(default="Eligible Citizens")
    eligibility: str = Field(default="N/A")
    benefits: str = Field(default="N/A")
    documents: str = Field(default="Aadhaar Card, Bank Passbook")
    state_district: str = Field(default="Central / All India")
    status: str = Field(default="Active")
    official_source_url: str = Field(default="")
    authority: str = Field(default="")


class SchemeExtractionRequest(BaseModel):
    text: str = Field(min_length=10)
    scheme_name: str = ""
    category: str = ""
    authority: str = ""
    source_url: str = ""


@app.get("/schemes")
def list_schemes(
    response: Response,
    q: str = "",
    category: str = "all",
    state: str = "all",
    status: str = "all",
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
            limit=limit,
            offset=offset,
            return_total=True,
        )
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Total-Pages"] = str(total_pages)
        return [s.to_dict() for s in schemes]


@app.get("/schemes/{sid:int}")
def get_scheme(sid: int):
    with SessionLocal() as db:
        scheme = db.get(Scheme, sid)
        if not scheme:
            raise HTTPException(404, "Scheme not found")
        return scheme.to_dict()


@app.post("/schemes", dependencies=[Depends(require_admin)])
def create_scheme(req: SchemeCreateRequest):
    from app.schemes.pipeline import ingest_scheme_to_db
    created = ingest_scheme_to_db(req.model_dump())
    return created.to_dict()


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


# Mount frontend static distribution if built
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")

