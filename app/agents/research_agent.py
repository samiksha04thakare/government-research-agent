import re
from app.agents.verifier import format_evidence
from app.llm.model import get_llm
from app.utils.language import resolve_language
from app.utils.logging import get_logger

log = get_logger("research_agent")

SYSTEM_PROMPT_EN = """You are an official Government Research Assistant.

Answer the user's question ONLY using the provided verified government documents and structured scheme data.

Rules:
1. Do not use information that is not present in the context.
2. Do not guess or invent figures.
3. If the answer cannot be found in the context, say:
   "The available government documents do not contain enough information to answer this question."
4. Preserve numbers, dates, scheme names and percentages exactly (e.g. ₹6,000, ₹3,00,000, 4%, 7%, 72 hours).
5. Mention the source document and official portal when available.
6. Cite verified claims using evidence markers like [1] or [2].
7. Include:
   - 📌 Scheme Name & Overview
   - 🎯 Beneficiaries & Eligibility
   - 💰 Benefits & Financial Assistance
   - 📄 Required Documents
   - 🔗 Official Government Source"""

SYSTEM_PROMPT_HI = """आप एक आधिकारिक सरकारी अनुसंधान सहायक (Government Research Assistant) हैं।

प्रदान किए गए आधिकारिक सरकारी दस्तावेजों और संरचित योजना विवरण (Structured Scheme Data) के आधार पर प्रश्न का संपूर्ण उत्तर स्पष्ट, प्रामाणिक और व्यवस्थित हिन्दी में (देवनागरी लिपि में) दें।

नियम:
1. केवल आधिकारिक संदर्भ (Official Context) में दी गई जानकारी का ही उपयोग करें। कोई भी काल्पनिक या असत्यापित जानकारी न जोड़ें।
2. संख्याएं (जैसे ₹6,000, ₹3,00,000, 4%, 7%), तिथियां, योजना का नाम और पात्रता की शर्तें ठीक वैसे ही लिखें जैसे संदर्भ में हैं।
3. संदर्भ से सत्यापित दावों के लिए उद्धरण चिह्न जैसे [1], [2] का उपयोग करें।
4. उत्तर में निम्नलिखित खंड स्पष्ट रूप से प्रस्तुत करें:
   - 📌 योजना का नाम एवं उद्देश्य (Scheme Name & Overview)
   - 🎯 पात्रता एवं लाभार्थी (Eligibility & Beneficiaries)
   - 💰 वित्तीय लाभ एवं सहायता राशि (Benefits & Assistance)
   - 📄 आवश्यक दस्तावेज़ (Required Documents Checklist)
   - 🔗 आधिकारिक सरकारी स्रोत एवं पोर्टल (Official Source)
5. भाषा सरल, स्पष्ट, प्राकृतिक और आम नागरिकों/किसानों के लिए समझने योग्य होनी चाहिए। पूरा उत्तर हिन्दी में होना चाहिए।"""

SYSTEM_PROMPT_MR = """तुम्ही एक अधिकृत शासकीय संशोधन सहाय्यक (Government Research Assistant) आहात.

प्रदान केलेल्या अधिकृत सरकारी कागदपत्रांच्या आणि संरचित योजना तपशीलांच्या (Structured Scheme Data) आधारे विचारलेल्या प्रश्नाचे संपूर्ण उत्तर स्पष्ट, प्रामाणिक आणि व्यवस्थित मराठी भाषेत (देवनागरी लिपीमध्ये) द्या.

नियम:
1. फक्त दिलेल्या अधिकृत संदर्भामधील (Official Context) माहितीचाच वापर करा. बाहेरील किंवा काल्पनिक माहिती वापरू नका.
2. आकडेवारी (उदा. ₹6,00,000, ₹3,00,000, 4%, 7%, 72 तास), तारखा, योजनांचे मूळ नाव आणि निकष संदर्भामध्ये आहेत तसेच तंतोतंत लिहा.
3. संदर्भामधील पडताळणी केलेल्या दाव्यांसाठी [1], [2] यांसारख्या अधिकृत संदर्भ चिन्हांचा (Citation Markers) वापर करा.
4. उत्तरात खालील विभाग स्पष्टपणे समाविष्ट करा:
   - 📌 योजनेचे नाव आणि स्वरूप (Scheme Name & Overview)
   - 🎯 पात्रता आणि लाभार्थी (Eligibility & Beneficiaries)
   - 💰 आर्थिक लाभ आणि सवलती (Benefits & Assistance)
   - 📄 आवश्यक कागदपत्रे (Required Documents)
   - 🔗 अधिकृत शासकीय स्रोत आणि पोर्टल (Official Source)
5. भाषा सोपी, नैसर्गिक आणि सर्वसामान्य शेतकरी व नागरिकांना सहज समजेल अशी अस्खलित मराठी असावी. संपूर्ण उत्तर मराठीत तयार करा."""


def synthesize_answer(
    question: str,
    evidence: list[dict],
    matched_scheme: dict | None = None,
    language: str = "en",
) -> str:
    """Synthesize grounded answer using both retrieved vector chunks and structured scheme data."""
    target_lang, detected_lang = resolve_language(language, question)

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

    if target_lang == "mr":
        system_prompt = SYSTEM_PROMPT_MR
        lang_instruction = (
            "संपूर्ण उत्तर नैसर्गिक, अस्खलित आणि वाचनीय मराठी भाषेत देवनागरी लिपीत तयार करा. "
            "केवळ प्रश्नाचा अनुवाद करू नका, तर संपूर्ण स्पष्टीकरण आणि माहिती मराठीत द्या. "
            "सरकारी आकडेवारी, योजनांची नावे आणि संदर्भ चिन्हे ([1], [2]) तंतोतंत जतन करा."
        )
    elif target_lang == "hi":
        system_prompt = SYSTEM_PROMPT_HI
        lang_instruction = (
            "संपूर्ण उत्तर स्पष्ट, स्वाभाविक और पठनीय हिन्दी भाषा में देवनागरी लिपि में तैयार करें। "
            "केवल प्रश्न का अनुवाद न करें, बल्कि संपूर्ण जानकारी और विवरण हिन्दी में दें। "
            "आधिकारिक संख्याएं, योजनाओं के नाम एवं संदर्भ चिह्न ([1], [2]) सुरक्षित रखें।"
        )
    else:
        system_prompt = SYSTEM_PROMPT_EN
        lang_instruction = (
            "Generate the complete answer in natural, official, readable English. "
            "Preserve all scheme names, eligibility terms, figures, dates, and citation markers ([1], [2])."
        )

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
        if matched_scheme and target_lang == "mr":
            return (
                f"## 📌 {matched_scheme.get('hindi_name') or matched_scheme.get('scheme_name')} ({matched_scheme.get('scheme_name')})\n\n"
                f"**स्थिती:** {matched_scheme.get('status')} | **श्रेणी:** {matched_scheme.get('category')} | **राज्य/जिल्हा:** {matched_scheme.get('state_district')}\n\n"
                f"### 🎯 पात्रता व लाभार्थी\n"
                f"- **लाभार्थी:** {matched_scheme.get('beneficiary')}\n"
                f"- **पात्रता निकष:** {matched_scheme.get('eligibility')}\n\n"
                f"### 💰 आर्थिक लाभ व सहाय्य\n"
                f"{matched_scheme.get('benefits')}\n\n"
                f"### 📄 आवश्यक कागदपत्रे\n"
                f"{matched_scheme.get('documents')}\n\n"
                f"### 🔗 अधिकृत शासकीय स्रोत\n"
                f"- **पोर्टल:** {matched_scheme.get('official_source_url')}\n"
                f"- **विभाग:** {matched_scheme.get('authority')}"
            )
        elif matched_scheme and target_lang == "hi":
            return (
                f"## 📌 {matched_scheme.get('hindi_name')} ({matched_scheme.get('scheme_name')})\n\n"
                f"**स्थिति:** {matched_scheme.get('status')} | **श्रेणी:** {matched_scheme.get('category')} | **राज्य/क्षेत्र:** {matched_scheme.get('state_district')}\n\n"
                f"### 🎯 पात्रता एवं लाभार्थी\n"
                f"- **लाभार्थी:** {matched_scheme.get('beneficiary')}\n"
                f"- **पात्रता:** {matched_scheme.get('eligibility')}\n\n"
                f"### 💰 वित्तीय लाभ एवं सहायता\n"
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
