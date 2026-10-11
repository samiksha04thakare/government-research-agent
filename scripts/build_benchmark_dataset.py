"""Script to construct and refine tests/benchmark_questions.json from BENCHMARK_QUERIES
with comprehensive schemas: levels, multilingual metadata, grounding requirements,
expected official domains, and evaluation notes.
"""
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.evaluate_agent import BENCHMARK_QUERIES

CATEGORY_NAMES = {
    "government_schemes": "Government Schemes & Policies",
    "farmer_questions": "Farmer Welfare, Credit & Land Records",
    "crop_problems": "Crop Production & Physiological Disorders",
    "pest_management": "Integrated Pest Management (IPM)",
    "fertilizers": "Fertilizers & Soil Health Management",
    "health": "Health & Medical Wellness",
    "transport": "Transport & Motor Vehicle Licensing",
    "pension": "Social Security & Old Age Pensions",
    "tax_gst": "Taxation & GST Compliance",
    "jobs_recruitment": "Public Sector Employment & Recruitment",
    "out_of_scope": "Out of Scope / Irrelevant Requests",
}

LEVEL_MAP = {
    1: "medium", 2: "medium", 3: "medium", 4: "complex", 5: "medium",
    6: "medium", 7: "medium", 8: "medium", 9: "medium", 10: "complex",
    11: "medium", 12: "medium", 13: "medium", 14: "easy", 15: "medium",
    16: "medium", 17: "medium", 18: "medium", 19: "medium", 20: "medium",
    21: "medium", 22: "medium", 23: "medium", 24: "medium", 25: "medium",
    26: "complex", 27: "complex", 28: "complex", 29: "medium",
    30: "unsupported", 31: "unsupported", 32: "unsupported", 33: "unsupported",
    34: "unsupported", 35: "unsupported", 36: "unsupported",
    37: "out_of_scope", 38: "out_of_scope", 39: "out_of_scope",
    40: "out_of_scope", 41: "out_of_scope", 42: "out_of_scope",
    43: "insufficient_evidence", 44: "insufficient_evidence",
    45: "complex",
}

DOMAIN_MAP = {
    "government_schemes": ["agricoop.nic.in", "myscheme.gov.in", "pmkisan.gov.in", "krishi.maharashtra.gov.in"],
    "farmer_questions": ["agricoop.nic.in", "krishi.maharashtra.gov.in"],
    "crop_problems": ["icar.org.in"],
    "pest_management": ["cibrc.gov.in"],
    "fertilizers": ["soilhealth.dac.gov.in"],
    "health": [],
    "transport": [],
    "pension": [],
    "tax_gst": [],
    "jobs_recruitment": [],
    "out_of_scope": [],
}

EVAL_FOCUS = {
    1: "Verify KCC concessional interest rate (4% with prompt repayment), collateral-free limit (₹1,60,000), 7/12 extract, and Kisan Call Centre helpline in English.",
    2: "Verify Hindi translation fidelity, official 4% interest rate, and required land/identity documents for KCC.",
    3: "Verify Marathi localized terminology (सवलतीचा व्याजदर, 7/12 उतारा, आधार) and KCC eligibility.",
    4: "Verify code-mixed Marathi-English (Marathlish) auto-detection and grounded KCC response.",
    5: "Verify PMFBY seasonal premium rates for Kharif (2%), Rabi (1.5%), and commercial crops (5%).",
    6: "Verify Hindi response for PMFBY seasonal premium rates and insurance coverage.",
    7: "Verify Marathi response for PMFBY seasonal premium rates and insurance coverage.",
    8: "Verify PM-KUSUM Component B standalone solar agriculture pump capital subsidy rates (30% CFA, state share, 7.5 HP max).",
    9: "Verify Sub-Mission on Agricultural Mechanization (SMAM) financial assistance rates for women and small farmers (50% vs 40%).",
    10: "Verify Maharashtra Agriculture Artificial Intelligence Policy 2025-2029 budget outlay (₹10,000 Lakh) and scheme code 1101100034.",
    11: "Verify tenant farmer documentation protocol (Self-declaration, Aadhaar, Bank Passbook) when land ownership title is unavailable.",
    12: "Verify Hindi guidance for tenant and sharecropper agricultural credit documentation.",
    13: "Verify digitally signed 7/12 RoR extract and Mahabhulekh verification procedure in Marathi.",
    14: "Verify national Kisan Call Centre toll-free number (1800-180-1551) and 22 languages support.",
    15: "Verify code-mixed Marathi KCC 7/12 extract and Aadhaar seeding requirements.",
    16: "Verify differential diagnosis of leaf yellowing: Nitrogen deficiency (older leaves), Iron chlorosis (young leaves), and waterlogging.",
    17: "Verify Hindi diagnosis and mitigation for nitrogen deficiency and iron chlorosis.",
    18: "Verify Marathi advisory for wheat yellowing, nitrogen deficiency, and drainage management.",
    19: "Verify code-mixed Marathi-English advisory for cotton leaf chlorosis.",
    20: "Verify ICAR agronomic recommendations for terminal heat stress mitigation in wheat (heat-tolerant varieties, potassium nitrate foliar spray).",
    21: "Verify Economic Threshold Level (8 moths/trap/night or 10% damaged bolls) and IPM biocontrol for pink bollworm in cotton.",
    22: "Verify Hindi advisory for pink bollworm ETL and pheromone trap usage in cotton.",
    23: "Verify Marathi advisory for pink bollworm ETL threshold and integrated management.",
    24: "Verify CIBRC recommendations and ETL for Fall Armyworm (FAW) in maize.",
    25: "Verify Marathi code-mixed IPM advisory for neem oil spray and pheromone traps in cotton.",
    26: "Verify 12 Soil Health Card parameters (Macro, Secondary, Micro, Physical) and NCU slow-release efficiency.",
    27: "Verify Hindi response for 12 Soil Health Card parameters and neem-coated urea benefits.",
    28: "Verify Marathi response for 12 Soil Health Card parameters and neem-coated urea benefits.",
    29: "Verify Marathi code-mixed advisory on balanced NPK fertilizer application based on soil test results.",
    30: "Rejection safety: Ayushman Bharat health query safely rejected with 'no_documents_for_category' and 0 fake citations.",
    31: "Rejection safety: Hindi health query safely rejected with 'no_documents_for_category' without fabricating hospital lists.",
    32: "Rejection safety: Parivahan commercial driving license query safely rejected with 'no_documents_for_category'.",
    33: "Rejection safety: Marathi transport query safely rejected with 'no_documents_for_category'.",
    34: "Rejection safety: Indira Gandhi Old Age Pension query safely rejected with 'no_documents_for_category'.",
    35: "Rejection safety: GST return filing query safely rejected with 'no_documents_for_category'.",
    36: "Rejection safety: UPSC Civil Services recruitment query safely rejected with 'no_documents_for_category'.",
    37: "Rejection safety: Arithmetic calculation query strictly rejected with 'out_of_scope' without querying vectorstore.",
    38: "Rejection safety: Python programming query strictly rejected with 'out_of_scope'.",
    39: "Rejection safety: Cricket World Cup sports inquiry strictly rejected with 'out_of_scope'.",
    40: "Rejection safety: Hindi sports trivia inquiry strictly rejected with 'out_of_scope'.",
    41: "Rejection safety: Marathi cinema ticket booking inquiry strictly rejected with 'out_of_scope'.",
    42: "Rejection safety: Office humor and joke request strictly rejected with 'out_of_scope'.",
    43: "Missing evidence safety: Unindexed vanilla orchid hydroponics in Ladakh cold desert safely triggers 'insufficient_evidence'.",
    44: "Missing evidence safety: Marathi inquiry on unindexed specific district grape subsidy safely triggers 'insufficient_evidence'.",
    45: "Boundary verification: Conflicting/boundary terms on KCC collateral requirements (collateral-free up to ₹1.6 Lakh vs above ₹1.6 Lakh).",
}

refined_dataset = []
for q in BENCHMARK_QUERIES:
    qid = q["id"]
    item = {
        "id": qid,
        "question": q["question"],
        "language": q.get("lang_param", "en"),
        "lang_param": q.get("lang_param", "en"),
        "expected_language": q.get("expected_lang", "en"),
        "expected_lang": q.get("expected_lang", "en"),
        "category": q["category"],
        "category_name": CATEGORY_NAMES.get(q["category"], q["category"]),
        "level": LEVEL_MAP.get(qid, "medium"),
        "type": q["type"],
        "expected_status": q["expected_status"],
        "must_cite": q.get("must_contain_sources", False),
        "must_contain_sources": q.get("must_contain_sources", False),
        "required_claims": q.get("required_claims", []),
        "expected_official_domains": DOMAIN_MAP.get(q["category"], []),
        "evaluation_focus": EVAL_FOCUS.get(qid, ""),
    }
    refined_dataset.append(item)

out_file = Path("tests/benchmark_questions.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(refined_dataset, f, indent=2, ensure_ascii=False)

print(f"Successfully refined {len(refined_dataset)} benchmark questions in {out_file}!")
