"""Tests for Step 9 / Benchmark Dataset Verification.

Ensures that tests/benchmark_questions.json is strictly formatted, comprehensive,
and adheres to all benchmark evaluation invariants:
1. Complete schema validation across all questions.
2. Groundedness constraints for supported queries.
3. Safety invariants for unindexed, out-of-scope, and missing-evidence questions.
4. Multilingual representation (English, Hindi, Marathi, Code-mixed).
5. Comprehensive domain taxonomy coverage.
"""
import json
from pathlib import Path
import pytest

BENCHMARK_PATH = Path(__file__).resolve().parent / "benchmark_questions.json"

REQUIRED_FIELDS = {
    "id",
    "question",
    "language",
    "expected_language",
    "category",
    "category_name",
    "level",
    "type",
    "expected_status",
    "must_cite",
    "required_claims",
    "expected_official_domains",
    "evaluation_focus",
}

VALID_TYPES = {"supported", "unsupported", "out_of_scope", "missing_evidence"}
VALID_STATUSES = {
    "completed",
    "no_documents_for_category",
    "out_of_scope",
    "insufficient_evidence",
}
VALID_LANGUAGES = {"en", "hi", "mr", "auto"}
VALID_EXPECTED_LANGS = {"en", "hi", "mr"}


@pytest.fixture(scope="module")
def benchmark_data():
    assert BENCHMARK_PATH.exists(), f"Benchmark dataset missing at {BENCHMARK_PATH}"
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list), "Benchmark dataset must be a JSON array"
    return data


def test_benchmark_dataset_count(benchmark_data):
    """The refined benchmark dataset must contain at least 45 questions."""
    assert len(benchmark_data) >= 45, f"Expected >= 45 questions, found {len(benchmark_data)}"


def test_benchmark_dataset_schema_integrity(benchmark_data):
    """Every question must conform strictly to the required schema."""
    seen_ids = set()
    for item in benchmark_data:
        assert isinstance(item, dict)
        missing = REQUIRED_FIELDS - set(item.keys())
        assert not missing, f"Question ID {item.get('id')} missing fields: {missing}"

        qid = item["id"]
        assert isinstance(qid, int) and qid > 0
        assert qid not in seen_ids, f"Duplicate question ID: {qid}"
        seen_ids.add(qid)

        assert isinstance(item["question"], str) and len(item["question"].strip()) >= 5
        assert item["type"] in VALID_TYPES, f"Invalid type in ID {qid}: {item['type']}"
        assert item["expected_status"] in VALID_STATUSES, f"Invalid status in ID {qid}: {item['expected_status']}"
        assert item["language"] in VALID_LANGUAGES, f"Invalid language in ID {qid}: {item['language']}"
        assert item["expected_language"] in VALID_EXPECTED_LANGS, f"Invalid expected_lang in ID {qid}"
        assert isinstance(item["must_cite"], bool)
        assert isinstance(item["required_claims"], list)
        assert isinstance(item["expected_official_domains"], list)
        assert isinstance(item["evaluation_focus"], str) and len(item["evaluation_focus"]) > 0


def test_supported_questions_grounding_invariants(benchmark_data):
    """Supported questions must expect completed status, citations, and claim keywords."""
    supported = [q for q in benchmark_data if q["type"] == "supported"]
    assert len(supported) >= 30, f"Expected at least 30 supported questions, found {len(supported)}"

    for q in supported:
        qid = q["id"]
        assert q["expected_status"] == "completed", f"ID {qid} must expect 'completed'"
        assert q["must_cite"] is True, f"ID {qid} must require citations"
        assert len(q["required_claims"]) > 0, f"ID {qid} must define required claims"
        assert len(q["expected_official_domains"]) > 0, f"ID {qid} must specify expected official domains"


def test_rejection_safety_invariants(benchmark_data):
    """Unsupported, out-of-scope, and missing-evidence questions must not require citations or claims."""
    rejections = [q for q in benchmark_data if q["type"] in {"unsupported", "out_of_scope", "missing_evidence"}]
    assert len(rejections) >= 15, f"Expected at least 15 safety rejection questions, found {len(rejections)}"

    for q in rejections:
        qid = q["id"]
        assert q["must_cite"] is False, f"Rejection ID {qid} must not require citations"
        assert q["required_claims"] == [], f"Rejection ID {qid} must have empty required claims"
        if q["type"] == "unsupported":
            assert q["expected_status"] == "no_documents_for_category"
        elif q["type"] == "out_of_scope":
            assert q["expected_status"] == "out_of_scope"
        elif q["type"] == "missing_evidence":
            assert q["expected_status"] == "insufficient_evidence"


def test_multilingual_distribution(benchmark_data):
    """Dataset must provide comprehensive multilingual coverage (EN, HI, MR, and code-mixed)."""
    langs = {q["language"] for q in benchmark_data}
    assert {"en", "hi", "mr", "auto"}.issubset(langs)

    en_count = sum(1 for q in benchmark_data if q["language"] == "en")
    hi_count = sum(1 for q in benchmark_data if q["language"] == "hi")
    mr_count = sum(1 for q in benchmark_data if q["language"] == "mr")
    auto_count = sum(1 for q in benchmark_data if q["language"] == "auto")

    assert en_count >= 20, f"Expected >= 20 English questions, got {en_count}"
    assert hi_count >= 8, f"Expected >= 8 Hindi questions, got {hi_count}"
    assert mr_count >= 10, f"Expected >= 10 Marathi questions, got {mr_count}"
    assert auto_count >= 3, f"Expected >= 3 code-mixed auto questions, got {auto_count}"


def test_category_coverage(benchmark_data):
    """Dataset must test across multiple government and agricultural categories."""
    categories = {q["category"] for q in benchmark_data}
    expected_categories = {
        "government_schemes",
        "farmer_questions",
        "crop_problems",
        "pest_management",
        "fertilizers",
        "health",
        "transport",
        "pension",
        "tax_gst",
        "jobs_recruitment",
        "out_of_scope",
    }
    assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"
