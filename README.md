# 🏛️ AI Government Research Agent

> **Source-grounded, multi-agent government research platform built with Agentic RAG, LangGraph, FastAPI, ChromaDB, PostgreSQL, and React (Vite).**

Provides verifiable, multilingual research and query assistance for Indian central and state government guidelines, policies, agricultural advisories, and citizen welfare programs with strict 1-to-1 official citations and information freshness auditing.

---

## 🏗️ End-to-End System Architecture

```
                      Official Government Portals
           (india.gov.in, myscheme.gov.in, agricoop.nic.in, etc.)
                                 │
                                 ▼
                     Apify / Scrapers / Crawlers
                     (HTML, JSON, JSONL, CSV, PDF)
                                 │
                                 ▼
                FastAPI Unified Ingestion Gateway
         (/scraper/ingest, /scraper/import-json, /scraper/import-csv)
                                 │
                                 ▼
                    Python Validation & Cleaning
      (URL domain check, currency normalization, text sanitization)
                                 │
                                 ▼
                 Deduplication & Canonical ID Map
                                 │
               ┌─────────────────┴─────────────────┐
               ▼                                   ▼
      PostgreSQL / SQLite                     ChromaDB
    (Structured Database)             (Vector Embeddings & Chunks)
               │                                   │
               └─────────────────┬─────────────────┘
                                 │
                                 ▼
                      Agentic RAG Orchestrator
             (Classifier ➔ Category Router ➔ Retriever)
                                 │
                                 ▼
                       LangGraph Multi-Agent
           (Evaluator ➔ Synthesizer ➔ Verifier ➔ Citations)
                                 │
                                 ▼
                 Multilingual Citizen Web Portal
                   (English, Hindi हिंदी, Marathi मराठी)
```

---

## ⚡ Core Capabilities

1. **Automated Scraper & Ingestion Pipeline**:
   - Ingests direct payloads from Apify webhooks, scraper scripts, CSV datasets, and JSON/JSONL dumps.
   - Built-in heuristic enrichment for national portals (`india.gov.in`, `myscheme.gov.in`).
   - Cleans HTML clutter, validates official `.gov.in` / `.nic.in` domains, and maps canonical records.

2. **Dual-Storage Engine**:
   - **Relational Storage (PostgreSQL / SQLite)**: Stores tabular metadata (benefits, eligibility criteria, required documents, jurisdiction, authority).
   - **Vector Database (ChromaDB)**: Dense semantic search using `sentence-transformers/all-MiniLM-L6-v2`.

3. **Multi-Agent RAG Orchestration (LangGraph)**:
   - **Query Classifier**: Detects domain (agriculture, scholarships, entrepreneurship, welfare, health, out-of-scope).
   - **Router**: Dispatches to targeted document collections and SQL tables.
   - **Evidence Evaluator**: Filters retrieved chunks for actual factual support, discarding irrelevant text.
   - **Synthesizer & Verifier**: Assembles clear, practical steps for citizens and cross-checks for conflicting information.

4. **Multilingual Localization (English, Hindi, Marathi)**:
   - Dynamic language switching (`en`, `hi`, `mr`).
   - Preserves all official figures, program names, dates, percentages, and citations in natural Devanagari script.

5. **Strict Grounding & Citation Auditing**:
   - Numbered markers (`[1]`, `[2]`) map 1-to-1 to official sources.
   - Strictly distinguishes verified check date (`last_checked`) from document revision date (`last_updated`).
   - Displays advisory disclaimer against taking financial action without direct portal verification.

---

## 🚀 Quick Start (Local Unified Server)

The entire application runs as a **unified single-port service** (FastAPI serves the React SPA frontend and all API endpoints on port 8000).

### Windows
```cmd
start.bat
```
*(Or run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`)*

### Linux / macOS
```bash
chmod +x start.sh
./start.sh
```

### URLs
- **Web Portal:** [http://localhost:8000](http://localhost:8000)
- **Swagger UI API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health & Readiness Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 📡 API Ingestion Endpoints

### 1. Direct Webhook / Scraper Ingestion
```http
POST /scraper/ingest
Content-Type: application/json
```
Accepts JSON arrays or wrapped objects (`{"items": [...]}` / `{"schemes": [...]}`), including Web Scraper JSONL format:
```json
[
  {
    "web_scraper_order": "1792218108-8",
    "web_scraper_start_url": "https://www.india.gov.in/my-government/schemes",
    "data": "Apply for New Ujjwala 2.0 Connection",
    "image": "https://static2.india.gov.in/npiprod/uploads/ujjwala_77aade7ab0.jpg"
  }
]
```

### 2. Scraped File Uploads
- `POST /scraper/import-json` — Upload scraped JSON or JSONL files.
- `POST /scraper/import-csv` — Upload scraped CSV files with normalized columns.
- `POST /documents/upload` — Upload official PDF, TXT, or DOCX guidelines.

### 3. Citizen Research Query
```http
POST /research
Content-Type: application/json

{
  "question": "What is the subsidy and interest rate under Kisan Credit Card?",
  "language": "mr"
}
```

---

## 🧪 Testing & Validation

The test suite contains **110+ comprehensive automated tests** validating retrieval quality, deduplication, citation fidelity, and multilingual generation:

```bash
pytest
```

To run focused pipeline tests:
```bash
# Scraper and CSV/JSON ingestion tests
pytest tests/test_csv_importer.py

# Citation auditing & information freshness tests
pytest tests/test_citations_and_freshness.py

# Multilingual Hindi/Marathi translation tests
pytest tests/test_multilingual_translation_fix.py
```

---

## ☁️ Deployment on Render

This repository is pre-configured with a ready-to-deploy multi-stage [Dockerfile](./Dockerfile) and [render.yaml](./render.yaml).

For complete step-by-step instructions, see **[RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md)**.
