import re
from app.agents.verifier import format_evidence
from app.llm.model import get_llm
from app.utils.logging import get_logger

log = get_logger("research_agent")

SYSTEM_PROMPT_EN = """You are an official Government Research Assistant.

Answer the user's question ONLY using the provided verified government documents and structured scheme data.

Rules:
1. Do not use information that is not present in the context.
2. Do not guess or invent figures.
3. If the answer cannot be found in the context, say:
   "The available government documents do not contain enough information to answer this question."
4. Preserve numbers, dates, scheme names and percentages exactly (e.g. ₹6,000, 4%, 7%, 72 hours).
5. Mention the source document and official portal when available.
6. Cite verified claims using evidence markers like [1] or [2].
7. Include:
   - 📌 Scheme Name & Overview
   - 🎯 Beneficiaries & Eligibility
   - 💰 Benefits & Financial Assistance
   - 📄 Required Documents
   - 🔗 Official Government Source"""

SYSTEM_PROMPT_HI = """आप एक आधिकारिक सरकारी अनुसंधान सहायक (Government Research Assistant) हैं।

प्रदान किए गए आधिकारिक सरकारी दस्तावेजों और संरचित योजना विवरण (Structured Scheme Data) के आधार पर प्रश्न का उत्तर स्पष्ट, प्रामाणिक और व्यवस्थित हिन्दी में दें।

नियम:
1. केवल आधिकारिक संदर्भ (Official Context) में दी गई जानकारी का ही उपयोग करें।
2. संख्याएं (जैसे ₹6,000, 4%, 7%), तिथियां, योजना का नाम और पात्रता की शर्तें ठीक वैसे ही लिखें जैसे संदर्भ में हैं।
3. संदर्भ से सत्यापित दावों के लिए उद्धरण चिह्न जैसे [1], [2] का उपयोग करें।
4. उत्तर में निम्नलिखित खंड स्पष्ट रूप से प्रस्तुत करें:
   - 📌 योजना का नाम एवं उद्देश्य (Scheme Name & Overview)
   - 🎯 पात्रता एवं लाभार्थी (Eligibility & Beneficiaries)
   - 💰 वित्तीय लाभ एवं सहायता राशि (Benefits & Assistance)
   - 📄 आवश्यक दस्तावेज़ (Required Documents Checklist)
   - 🔗 आधिकारिक सरकारी स्रोत एवं पोर्टल (Official Source)
5. भाषा सरल, स्पष्ट और आम नागरिकों/किसानों के लिए समझने योग्य होनी चाहिए।"""


def _contains_hindi(text: str) -> bool:
    """Check if text contains Devanagari script."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def synthesize_answer(
    question: str,
    evidence: list[dict],
    matched_scheme: dict | None = None,
    language: str = "auto",
) -> str:
    """Synthesize grounded answer using both retrieved vector chunks and structured scheme data."""
    is_hindi = language == "hi" or (language == "auto" and _contains_hindi(question))
    
    context_parts = []
    
    # 1. Inject Structured Scheme Data if available
    if matched_scheme:
        scheme_context = (
            f"=== STRUCTURED SCHEME DATA FROM OFFICIAL DATABASE ===\n"
            f"Scheme Name: {matched_scheme.get('scheme_name')}\n"
            f"Hindi Name: {matched_scheme.get('hindi_name')}\n"
            f"Category: {matched_scheme.get('category')}\n"
            f"Beneficiary: {matched_scheme.get('beneficiary')}\n"
            f"Eligibility: {matched_scheme.get('eligibility')}\n"
            f"Benefits: {matched_scheme.get('benefits')}\n"
            f"Documents Required: {matched_scheme.get('documents')}\n"
            f"State/District: {matched_scheme.get('state_district')}\n"
            f"Status: {matched_scheme.get('status')}\n"
            f"Official Portal: {matched_scheme.get('official_source_url')}\n"
            f"Authority: {matched_scheme.get('authority')}\n"
            f"======================================================"
        )
        context_parts.append(scheme_context)

    # 2. Inject Vector Retrieval Evidence Chunks
    if evidence:
        context_parts.append("=== RETRIEVED OFFICIAL GUIDELINES & SECTIONS ===")
        context_parts.append(format_evidence(evidence))

    full_context = "\n\n".join(context_parts)

    system_prompt = SYSTEM_PROMPT_HI if is_hindi else SYSTEM_PROMPT_EN
    lang_instruction = "उत्तर कृपया प्रमाणिक हिन्दी में दें।" if is_hindi else "Please respond in English."

    prompt = (
        f"Context:\n{full_context}\n\n"
        f"Question:\n{question}\n\n"
        f"Instruction: {lang_instruction}\n\n"
        f"Answer:"
    )

    try:
        msg = get_llm().invoke([
            ("system", system_prompt),
            ("human", prompt),
        ])
        content = msg.content if isinstance(msg.content, str) else "".join(
            b.get("text", "") for b in msg.content if isinstance(b, dict)
        )
        return content
    except Exception as exc:
        log.warning("LLM invocation failed in synthesize_answer: %s", exc)
        # Fallback to structured formatting
        if matched_scheme and is_hindi:
            return (
                f"## 📌 {matched_scheme.get('hindi_name')} ({matched_scheme.get('scheme_name')})\n\n"
                f"**स्थिति:** {matched_scheme.get('status')} | **श्रेणी:** {matched_scheme.get('category')} | **राज्य/क्षेत्र:** {matched_scheme.get('state_district')}\n\n"
                f"### 🎯 पात्रता एवं लाभार्थी\n"
                f"- **लाभार्थी:** {matched_scheme.get('beneficiary')}\n"
                f"- **पात्रता:** {matched_scheme.get('eligibility')}\n\n"
                f"### 💰 वित्तीय लाभ\n"
                f"{matched_scheme.get('benefits')}\n\n"
                f"### 📄 आवश्यक दस्तावेज़\n"
                f"{matched_scheme.get('documents')}\n\n"
                f"### 🔗 आधिकारिक सरकारी स्रोत\n"
                f"- **पोर्टल:** {matched_scheme.get('official_source_url')}\n"
                f"- **विभाग:** {matched_scheme.get('authority')}"
            )
        elif matched_scheme:
            return (
                f"## 📌 {matched_scheme.get('scheme_name')}\n\n"
                f"**Status:** {matched_scheme.get('status')} | **Category:** {matched_scheme.get('category')} | **State/District:** {matched_scheme.get('state_district')}\n\n"
                f"### 🎯 Eligibility & Beneficiary\n"
                f"- **Beneficiary:** {matched_scheme.get('beneficiary')}\n"
                f"- **Eligibility:** {matched_scheme.get('eligibility')}\n\n"
                f"### 💰 Benefits\n"
                f"{matched_scheme.get('benefits')}\n\n"
                f"### 📄 Documents Required\n"
                f"{matched_scheme.get('documents')}\n\n"
                f"### 🔗 Official Government Source\n"
                f"- **Source URL:** {matched_scheme.get('official_source_url')}\n"
                f"- **Authority:** {matched_scheme.get('authority')}"
            )
        raise exc
