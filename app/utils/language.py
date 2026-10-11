"""Language detection, resolution, and multilingual localization utilities for Step 8.

Supports:
- English ('en')
- Hindi ('hi')
- Marathi ('mr')

Preserves all official numbers, scheme names, percentages, dates, and citation markers.
"""
import re
from typing import Literal

SupportedLanguage = Literal["en", "hi", "mr"]

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "हिंदी (Hindi)",
    "mr": "मराठी (Marathi)",
}

# Distinctive word sets for distinguishing Hindi and Marathi in Devanagari script
MARATHI_KEYWORDS = {
    "आहे", "नाही", "करावा", "करावे", "करावी", "साठी", "कसा", "कशी", "काय",
    "शेतकरी", "शेतकऱ्यांना", "अर्ज", "माहिती", "पिकांची", "जमीन", "खाते",
    "हप्ता", "मिळेल", "लागेल", "कोणते", "कोणत्या", "कशा", "योजनांची",
    "पद्धत", "पात्रता", "कागदपत्रे", "कर्ज", "अनुदान", "नियम", "पिकांचे"
}

HINDI_KEYWORDS = {
    "है", "नहीं", "करें", "करे", "हेतु", "के लिए", "कैसे", "क्या", "किसान",
    "किसानों", "आवेदन", "जानकारी", "फसल", "भूमि", "खाता", "किस्त", "मिलेगा",
    "लगेगा", "कौन", "कौनसे", "होगा", "योजनाओं", "तरीका", "पात्रता",
    "दस्तावेज", "ऋण", "सब्सिडी", "नियम", "फसलों"
}


def detect_language(text: str) -> SupportedLanguage:
    """Detect whether text is Hindi, Marathi, or English."""
    if not text or not isinstance(text, str):
        return "en"

    # Check for Devanagari script (U+0900 to U+097F)
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    if not has_devanagari:
        return "en"

    tokens = set(re.findall(r"[\u0900-\u097F]+", text.lower()))
    marathi_matches = len(tokens.intersection(MARATHI_KEYWORDS))
    hindi_matches = len(tokens.intersection(HINDI_KEYWORDS))

    # Marathi specific characters or morphology checks
    # e.g., ळ (U+0933) is prominent in Marathi and absent from modern standard Hindi
    if "\u0933" in text or "साठी" in text or "करावे" in text or "आहे" in text:
        return "mr"

    if marathi_matches > hindi_matches:
        return "mr"
    elif hindi_matches > 0:
        return "hi"

    # Fallback to Hindi for general Devanagari without distinct Marathi markers
    return "hi"


def resolve_language(preferred: str | None, text: str) -> tuple[SupportedLanguage, SupportedLanguage]:
    """Resolve target language based on user preference and detected query language.
    
    Returns (target_language, detected_language).
    """
    detected = detect_language(text)
    pref = (preferred or "").strip().lower()
    if pref in ("en", "hi", "mr"):
        return pref, detected  # type: ignore[return-value]
    return detected, detected


# Multilingual section headings and labels for farmer-friendly outputs
UI_STRINGS = {
    "en": {
        "summary_title": "Kisan Credit Card (KCC) Scheme Overview",
        "eligibility_title": "Eligibility Criteria (Who is Eligible)",
        "application_title": "Application Procedure & Required Documents",
        "financial_title": "Interest Rates, Credit Limit & Financial Benefits",
        "contact_title": "Where to Get Help & Who to Contact",
        "practical_steps_title": "Practical Next Steps for Farmers",
        "clarifying_question_title": "Need More Help?",
        "missing_docs_notice": "Official application procedures or document lists are not provided in current verified records.",
        "missing_evidence_notice": "Detailed official guidelines are not fully indexed for this specific query. Please consult your local Taluka Agriculture Officer.",
        "advisory_disclaimer": "Information is strictly grounded in verified government guidelines. Always verify with your local bank or agriculture department before making financial decisions.",
        "official_sources_heading": "Official Sources & Information Freshness",
        "page": "Page",
        "official_date": "Official Document Date",
        "check_date": "Verified Check Date",
    },
    "hi": {
        "summary_title": "किसानों के लिए संक्षेप में जानकारी",
        "eligibility_title": "पात्रता (कौन आवेदन कर सकता है)",
        "application_title": "आवेदन की प्रक्रिया और आवश्यक दस्तावेज",
        "financial_title": "ऋण सीमा और ब्याज दर के लाभ",
        "contact_title": "कहाँ से मदद लें और किससे संपर्क करें",
        "practical_steps_title": "किसानों के लिए व्यावहारिक कदम",
        "clarifying_question_title": "क्या आपको और सहायता चाहिए?",
        "missing_docs_notice": "सत्यापित सरकारी दस्तावेजों में इस योजना की विस्तृत आवेदन प्रक्रिया या दस्तावेज सूची उपलब्ध नहीं है।",
        "missing_evidence_notice": "इस प्रश्न के लिए आधिकारिक रिकॉर्ड में पर्याप्त विवरण उपलब्ध नहीं है। कृपया अपने नजदीकी कृषि विभाग या कृषि विज्ञान केंद्र (KVK) से संपर्क करें।",
        "advisory_disclaimer": "यह जानकारी पूरी तरह से आधिकारिक सरकारी दिशानिर्देशों पर आधारित है। वित्तीय या प्रशासनिक निर्णय लेने से पहले अपने नजदीकी बैंक शाखा या कृषि कार्यालय से पुष्टि अवश्य करें।",
        "official_sources_heading": "आधिकारिक स्रोत और ताजगी की जानकारी",
        "page": "पृष्ठ",
        "official_date": "आधिकारिक दस्तावेज दिनांक",
        "check_date": "सत्यापन जांच दिनांक",
    },
    "mr": {
        "summary_title": "शेतकऱ्यांसाठी सोप्या भाषेत माहिती",
        "eligibility_title": "पात्रता (कोणाला लाभ मिळतो)",
        "application_title": "अर्ज कसा करावा आणि लागणारी कागदपत्रे",
        "financial_title": "कर्ज मर्यादा आणि सवलतीचे व्याजदर",
        "contact_title": "मदत आणि संपर्कासाठी माहिती",
        "practical_steps_title": "शेतकऱ्यांसाठी प्रत्यक्ष करावयाच्या गोष्टी",
        "clarifying_question_title": "तुम्हाला अधिक माहिती हवी आहे का?",
        "missing_docs_notice": "सध्याच्या पडताळणी केलेल्या सरकारी दस्तऐवजांमध्ये विशिष्ट अर्ज प्रक्रिया किंवा कागदपत्रांची यादी उपलब्ध नाही.",
        "missing_evidence_notice": "या विशिष्ट प्रश्नासाठी अधिकृत दस्तऐवजांमध्ये संपूर्ण माहिती उपलब्ध नाही. कृपया आपल्या तालुका कृषी अधिकारी किंवा कृषी विज्ञान केंद्राशी (KVK) संपर्क साधावा.",
        "advisory_disclaimer": "ही माहिती थेट पडताळणी केलेल्या अधिकृत सरकारी नोंदींवर आधारित आहे. कोणताही आर्थिक किंवा प्रशासकीय निर्णय घेण्यापूर्वी स्थानिक बँक किंवा कृषी कार्यालयाशी संपर्क साधावा.",
        "official_sources_heading": "अधिकृत स्रोत आणि माहितीची पडताळणी",
        "page": "पान",
        "official_date": "अधिकृत दस्तऐवज तारीख",
        "check_date": "पडताळणी तारीख",
    },
}
