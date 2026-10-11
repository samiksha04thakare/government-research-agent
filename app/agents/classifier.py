import os
import re
from typing import Literal
from pydantic import BaseModel, Field

from app.config import ANTHROPIC_API_KEY, GROQ_API_KEY
from app.utils.logging import get_logger

log = get_logger("classifier")

# The 14 recognized categories plus out_of_scope
ALL_CATEGORIES = [
    "government_schemes",
    "agriculture",
    "crop_problems",
    "pest_management",
    "fertilizers",
    "farmer_questions",
    "jobs_recruitment",
    "education_scholarships",
    "health",
    "documents_certificates",
    "tax_gst",
    "pension",
    "transport",
    "other_government",
    "out_of_scope",
]

AGRICULTURE_CATEGORIES = {
    "agriculture",
    "crop_problems",
    "pest_management",
    "fertilizers",
    "farmer_questions",
}

GOVERNMENT_CATEGORIES = {
    "government_schemes",
    "jobs_recruitment",
    "education_scholarships",
    "health",
    "documents_certificates",
    "tax_gst",
    "pension",
    "transport",
    "other_government",
}


def get_scope_for_category(category: str) -> str:
    """Map a specific category to its high-level scope."""
    if category == "out_of_scope":
        return "out_of_scope"
    if category in AGRICULTURE_CATEGORIES:
        return "agriculture_related"
    return "government_related"


class ClassificationResult(BaseModel):
    category: str = Field(
        description="The detected category: government_schemes, agriculture, crop_problems, pest_management, "
                    "fertilizers, farmer_questions, jobs_recruitment, education_scholarships, health, "
                    "documents_certificates, tax_gst, pension, transport, other_government, or out_of_scope."
    )
    scope: Literal["government_related", "agriculture_related", "out_of_scope"] = Field(
        description="High level scope: government_related, agriculture_related, or out_of_scope."
    )
    reasoning: str = Field(
        default="",
        description="Short reason explaining why this question was classified into this category."
    )


OUT_OF_SCOPE_RESPONSE = (
    "This question is outside the scope of the AI Government Research Agent. "
    "Please ask a government or agriculture-related question."
)

# High-confidence patterns for obvious out-of-scope queries
MATH_PATTERN = re.compile(
    r"^\s*(what\s+is\s+)?[\d\.\s\+\-\*\/\^\(\)%]+\??\s*$",
    re.IGNORECASE,
)
CODING_PATTERN = re.compile(
    r"\b(write|create|build|generate|code|program)\b.*?\b(code|program|script|function|calculator|algorithm|html|css|python|java|c\+\+|javascript|sql)\b|"
    r"^\s*(write|code)\s+a\s+(python|c\+\+|java|javascript|calculator|script)",
    re.IGNORECASE,
)
JOKE_PATTERN = re.compile(
    r"\b(tell\s+me\s+a\s+joke|joke|funny|humor|riddle|pun)\b",
    re.IGNORECASE,
)
WEATHER_PATTERN = re.compile(
    r"^\s*(what('s|\s+is)\s+the\s+weather|weather\s+today|temperature\s+today|forecast\s+today|will\s+it\s+rain\s+today)",
    re.IGNORECASE,
)
SPORTS_CELEBRITY_PATTERN = re.compile(
    r"\b(virat kohli|ms dhoni|rohit sharma|sachin|messi|ronaldo|ipl|fifa|world cup|cricket match|celebrity|actor|actress|bollywood|hollywood|movie|cinema|song)\b",
    re.IGNORECASE,
)
MULTILINGUAL_OUT_OF_SCOPE_PATTERN = re.compile(
    r"(चित्रपट|सिनेमा|फिल्म|तिकीट|क्रिकेट|गाणे|गाना|अभिनेता|अभिनेत्री|हवामान|चुटकुला|विनोद|मजाक)",
    re.IGNORECASE,
)
GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|good\s+morning|good\s+evening|how\s+are\s+you|who\s+are\s+you|what\s+is\s+your\s+name)[\?\!\.]*\s*$",
    re.IGNORECASE,
)


def _has_llm_key() -> bool:
    groq_key = os.getenv("GROQ_API_KEY", "").strip() or GROQ_API_KEY.strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or ANTHROPIC_API_KEY.strip()
    return bool((groq_key and groq_key != "your-groq-key-here") or (anthropic_key and anthropic_key != "your-key-here"))


def heuristic_classify(question: str) -> ClassificationResult:
    q_clean = question.strip()
    q_lower = q_clean.lower()

    # 1. Out-of-scope checks
    if MATH_PATTERN.match(q_clean) and any(ch in q_clean for ch in "+-*/^%"):
        return ClassificationResult(
            category="out_of_scope",
            scope="out_of_scope",
            reasoning="Question is an arithmetic or math calculation."
        )

    if CODING_PATTERN.search(q_clean):
        return ClassificationResult(
            category="out_of_scope",
            scope="out_of_scope",
            reasoning="Question is a programming or software coding request."
        )

    if JOKE_PATTERN.search(q_clean):
        return ClassificationResult(
            category="out_of_scope",
            scope="out_of_scope",
            reasoning="Question is asking for jokes or humor."
        )

    if WEATHER_PATTERN.search(q_clean):
        return ClassificationResult(
            category="out_of_scope",
            scope="out_of_scope",
            reasoning="Question is asking for general weather forecasts."
        )

    if SPORTS_CELEBRITY_PATTERN.search(q_clean) or MULTILINGUAL_OUT_OF_SCOPE_PATTERN.search(q_clean):
        return ClassificationResult(
            category="out_of_scope",
            scope="out_of_scope",
            reasoning="Question is asking about celebrities, sports, or entertainment."
        )

    if GREETING_PATTERN.match(q_clean):
        return ClassificationResult(
            category="out_of_scope",
            scope="out_of_scope",
            reasoning="Input is casual greeting or chit-chat."
        )

    # 2. Check if question directly matches any official government scheme
    try:
        from app.schemes.pipeline import find_matching_scheme_for_query
        matched_scheme = find_matching_scheme_for_query(q_clean)
        if matched_scheme:
            return ClassificationResult(
                category="government_schemes",
                scope="government_related",
                reasoning=f"Question directly references official government scheme: {matched_scheme.scheme_name}."
            )
    except Exception:
        pass

    # 3. Specific Non-Agricultural Government Categories (Health, Pension, Transport, Tax, Jobs, Scholarships)
    # Health (Exclude soil health card / agricultural testing)
    is_soil_health = any(st in q_lower for st in ["soil health", "मृदा स्वास्थ्य", "माती आरोग्य", "माती परीक्षण"])
    health_terms = ["ayushman", "pm-jay", "hospital", "health insurance", "आरोग्य", "स्वास्थ्य", "आयुष्मान", "गोल्डन कार्ड"]
    if not is_soil_health and (any(term in q_lower for term in health_terms) or "health card" in q_lower):
        return ClassificationResult(
            category="health",
            scope="government_related",
            reasoning="Question is about public healthcare or health insurance schemes."
        )

    # Pension
    pension_terms = ["pension", "atal pension", "nps", "eps", "old age pension", "पेन्शन", "पेंशन", "वृद्धावस्था"]
    if any(term in q_lower for term in pension_terms):
        return ClassificationResult(
            category="pension",
            scope="government_related",
            reasoning="Question is about retirement, old age, or social security pensions."
        )

    # Transport (Must use word boundary for 'rc' to avoid matching 'percentage')
    transport_terms = ["driving licence", "learner licence", "rto", "vehicle registration", "challan", "परवाना", "लायसन्स", "आरटीओ", "parivahan", "वाहन"]
    has_rc = bool(re.search(r"\brc\b", q_lower))
    if any(term in q_lower for term in transport_terms) or has_rc:
        return ClassificationResult(
            category="transport",
            scope="government_related",
            reasoning="Question is about motor vehicle registration or driving licences."
        )

    # Tax & GST (Must use exact word boundary for 'कर' and acronyms 'itr', 'gst', 'tds' to avoid matching 'nitrogen', 'करावा', 'कार्यालय')
    tax_terms = ["income tax", "tax return", "pan card", "आयकर", "टॅक्स", "कर भरणा", "कर विवरण"]
    has_tax_acronym = bool(re.search(r"\b(itr|gst|tds)\b", q_lower))
    has_kar_word = bool(re.search(r"(?<![a-zA-Z\u0900-\u097F])कर(?![a-zA-Z\u0900-\u097F])", q_clean))
    if any(term in q_lower for term in tax_terms) or has_tax_acronym or has_kar_word:
        return ClassificationResult(
            category="tax_gst",
            scope="government_related",
            reasoning="Question is about taxation, GST, or income tax filings."
        )

    # Jobs & Recruitment
    jobs_terms = ["recruitment", "vacancy", "vacancies", "sarkari naukri", "upsc", "ssc", "govt job", "भरती", "सरकारी नोकरी"]
    if any(term in q_lower for term in jobs_terms):
        return ClassificationResult(
            category="jobs_recruitment",
            scope="government_related",
            reasoning="Question is about government recruitment or public sector job vacancies."
        )

    # Education & Scholarships
    scholarship_terms = [
        "scholarship", "scholarships", "fellowship", "post-matric",
        "pre-matric", "mahadbt", "student aid", "tuition fee", "शिष्यवृत्ती", "छात्रवृत्ति"
    ]
    if any(term in q_lower for term in scholarship_terms):
        return ClassificationResult(
            category="education_scholarships",
            scope="government_related",
            reasoning="Question is about educational scholarships or student financial assistance."
        )

    # 3. Specific Agricultural Categories
    # Pest Management
    pest_terms = [
        "pest", "pests", "insect", "insects", "bollworm", "fall armyworm",
        "aphid", "whitefly", "caterpillar", "ipm", "cibrc", "insecticide",
        "pesticide", "managing pest", "managing pests", "pest control", "etl",
        "trap", "traps", "pheromone", "neem spray", "nske",
        "कीड", "किडी", "कीटक", "बोंडअळी", "लष्करी अळी", "अळी", "कीट", "कीटनाशक",
        "सापळे", "सापळा", "ट्रैप", "फेरोमोन", "निंबोळी"
    ]
    if any(term in q_lower for term in pest_terms):
        return ClassificationResult(
            category="pest_management",
            scope="agriculture_related",
            reasoning="Question is about pest identification, IPM, or approved insecticide control."
        )

    # Crop Problems & Diseases (Exclude Soil Health Card / soil testing)
    crop_problem_terms = [
        "crop disease", "crop diseases", "chlorosis", "yellowing", "stress",
        "heat stress", "terminal heat stress", "lodging", "blight", "rust",
        "wilt", "crop damage", "crop disorder", "leaf spot", "waterlogging",
        "iron chlorosis", "leaf yellowing", "deficiency",
        "पिवळे पडणे", "पान पिवळे", "पिवळेपणा", "पिवळ", "पीक रोग", "फसल रोग",
        "पीलापन", "पीला", "ब्लाइट", "मर रोग", "नत्र कमतरता", "निचरा", "पाण्याचा निचरा"
    ]
    has_crop_rog = bool(re.search(r"(?<!आ)रोग", q_clean))
    if not is_soil_health and (any(term in q_lower for term in crop_problem_terms) or has_crop_rog):
        return ClassificationResult(
            category="crop_problems",
            scope="agriculture_related",
            reasoning="Question is about crop disorders, physiological stress, or diseases."
        )

    # Fertilizers & Soil Health
    fertilizer_terms = [
        "fertilizer", "fertilizers", "soil health", "soil health card",
        "urea", "neem coated urea", "dap", "npk", "potash", "nitrogen",
        "phosphorus", "micronutrient", "manure", "compost", "dosage of fertilizer",
        "खत", "खते", "खतांची", "युरिया", "यूरिया", "उर्वरक", "खाद", "माती परीक्षण", "मृदा स्वास्थ्य", "माती"
    ]
    if any(term in q_lower for term in fertilizer_terms):
        return ClassificationResult(
            category="fertilizers",
            scope="agriculture_related",
            reasoning="Question is about fertilizers, soil health cards, or nutrient management."
        )

    # Farmer Questions (Land records, 7/12, grievances, helpline)
    farmer_terms = [
        "land record", "7/12", "ror", "bhulekh", "patta", "khatauni",
        "tenant farmer", "sharecropper", "apmc", "mandi", "msp",
        "minimum support price", "farmer welfare", "farmer registration",
        "kisan call centre", "call centre", "helpline", "grievance",
        "७/१२", "७ १२", "सातबारा", "उतारा", "खसरा", "खतौनी", "भूलेख", "बटाईदार", "भाडेकरू",
        "किसान कॉल सेंटर", "कॉल सेंटर", "हेल्पलाइन", "हेल्पलाईन", "तक्रार", "शिकायत", "1800-180-1551"
    ]
    has_farmer_record_or_helpline = any(term in q_lower for term in [
        "7/12", "७/१२", "सातबारा", "उतारा", "भूलेख", "खतौनी", "ror", "land record",
        "kisan call centre", "किसान कॉल सेंटर", "call centre", "1800-180-1551",
        "हेल्पलाइन", "हेल्पलाईन", "तक्रार", "शिकायत", "tenant", "बटाईदार", "भाडेकरू"
    ])
    if has_farmer_record_or_helpline or (any(term in q_lower for term in farmer_terms) and not any(k in q_lower for k in ["kisan credit card", "kcc"])):
        return ClassificationResult(
            category="farmer_questions",
            scope="agriculture_related",
            reasoning="Question pertains to farmer land records, credit access, or marketing welfare."
        )

    # Government Schemes & Subsidies (including KCC, PM-KISAN, PMFBY, policies, BDS outlays)
    scheme_terms = [
        "kisan credit card", "kcc", "pm-kisan", "pm kisan", "pmfby",
        "fasal bima", "crop insurance", "pm-kusum", "pm kusum", "smam",
        "scheme", "schemes", "subsidy", "subsidies", "subvention",
        "yojana", "financial assistance", "dbt", "grant", "welfare scheme",
        "policy 2025", "budget outlay", "bds", "आउटले", "बजेट",
        "किसान क्रेडिट कार्ड", "केसीसी", "पीएम-किसान", "पीक विमा", "फसल बीमा",
        "योजना", "योजनेची", "योजनेचा", "योजनेचे", "अनुदान", "सब्सिडी", "ऋण", "कर्ज", "नमो शेतकरी", "कृषी समृद्धी",
        "लाडकी", "बहीण", "बहिण", "महिला", "ladki", "bahin", "sakhi", "poshan", "anganwadi", "अंगणवाडी", "अंगनवाड़ी", "पोषण"
    ]
    if any(term in q_lower for term in scheme_terms):
        return ClassificationResult(
            category="government_schemes",
            scope="government_related",
            reasoning="Question is about government welfare schemes, credit subsidies, or insurance policies."
        )

    # Farmer General Questions
    if any(term in q_lower for term in ["शेतकरी", "किसान", "farmer", "farmers"]):
        return ClassificationResult(
            category="farmer_questions",
            scope="agriculture_related",
            reasoning="General question about farmer assistance or agricultural guidance."
        )

    # Documents & Certificates
    docs_terms = [
        "birth certificate", "death certificate", "caste certificate",
        "income certificate", "domicile", "ration card", "aadhaar", "voter id",
        "दाखला", "प्रमाणपत्र", "रेशन कार्ड", "राशन कार्ड", "आधार"
    ]
    if any(term in q_lower for term in docs_terms):
        return ClassificationResult(
            category="documents_certificates",
            scope="government_related",
            reasoning="Question is about citizen identity certificates or official documents."
        )

    # General Agriculture
    agri_broad_terms = [
        "farming", "farmer", "farmers", "agriculture", "agricultural", "crop", "crops",
        "paddy", "rice", "wheat", "cotton", "maize", "sugarcane", "soybean",
        "cultivation", "sowing", "harvest", "yield", "irrigation", "icar", "kvk",
        "शेती", "पिके", "पीक", "कापूस", "गहू", "भात", "मका", "सोयाबीन", "बाजरी", "ज्वारी", "कृषी", "फसल", "कृषि"
    ]
    if any(term in q_lower for term in agri_broad_terms):
        return ClassificationResult(
            category="agriculture",
            scope="agriculture_related",
            reasoning="Question is about general agricultural practices or crop management."
        )

    # General Government
    govt_broad_terms = ["government", "govt", "ministry", "department", "policy", "portal", "official"]
    if any(term in q_lower for term in govt_broad_terms):
        return ClassificationResult(
            category="other_government",
            scope="government_related",
            reasoning="Question is about official government administration or policies."
        )

    # Default to out_of_scope
    return ClassificationResult(
        category="out_of_scope",
        scope="out_of_scope",
        reasoning="Question does not match government or agriculture domains."
    )


def classify(question: str) -> dict:
    """Classify user query into category and scope."""
    # Fast check for instant deterministic classification
    fast_check = heuristic_classify(question)
    if fast_check.category in (
        "out_of_scope", "pest_management", "fertilizers",
        "crop_problems", "government_schemes", "education_scholarships"
    ):
        return fast_check.model_dump()

    # Nuanced LLM structured classification if key is configured
    if _has_llm_key():
        try:
            from app.llm.model import get_llm
            llm = get_llm().with_structured_output(ClassificationResult)
            categories_str = ", ".join(ALL_CATEGORIES)
            prompt = (
                "You are an intent and domain classifier for an AI Government & Agriculture Research Agent.\n"
                f"Classify the user's question into EXACTLY one category from this list: [{categories_str}].\n"
                "Also assign the scope as 'government_related', 'agriculture_related', or 'out_of_scope'.\n\n"
                f"Question: {question}"
            )
            result = llm.invoke(prompt)
            if isinstance(result, ClassificationResult):
                return result.model_dump()
            if isinstance(result, dict) and "category" in result:
                if "scope" not in result:
                    result["scope"] = get_scope_for_category(result["category"])
                return result
        except Exception as e:
            log.warning("LLM classification failed (%s), using heuristic result", e)

    return fast_check.model_dump()
