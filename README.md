# AI Government Research Agent

Source-grounded government research using Agentic RAG, LangGraph and an LLM.
Implements the architecture in the project documentation (FastAPI + LangGraph + ChromaDB + React).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # add ANTHROPIC_API_KEY and ADMIN_TOKEN
uvicorn app.main:app --reload                          # http://localhost:8000/docs

cd frontend && npm install && npm run dev              # http://localhost:5173
```

## First run: index some official documents

1. Upload (admin token required):
   ```bash
   curl -X POST http://localhost:8000/documents/upload \
     -H "X-Admin-Token: $ADMIN_TOKEN" \
     -F "file=@data/raw/scheme_guidelines.pdf" \
     -F "title=Scheme Guidelines" -F "authority=Ministry of X" \
     -F "source_url=https://example.gov.in/guidelines.pdf" \
     -F "publication_date=2025-04-01"
   ```
2. Build the index: `curl -X POST http://localhost:8000/documents/index -H "X-Admin-Token: $ADMIN_TOKEN"`
3. Ask a question in the UI or `POST /research {"question": "..."}`.

## Agent flow (app/graph/workflow.py)

```
analyze_query -> plan_research -> retrieve -> grade_evidence
                                     ^             |
                                     |   weak & loops left
                                refine_query <-----+
                                                   | sufficient
                                                   v
                                 synthesize -> verify -> cite -> END
                       (no evidence after retries) -> insufficient -> END
```

## Implementation phases (from the documentation)

| Phase | Where it lives | Status |
|---|---|---|
| 1 Basic RAG | `app/rag/*` | done |
| 2 Agent | `app/graph/*`, `app/agents/planner.py` | done |
| 3 Government sources | `app/tools/government_search.py` | stub - add official API connectors |
| 4 Verification | `app/agents/verifier.py`, `app/utils/citations.py` | done (LLM-based conflict check) |
| 5 Application | `app/main.py`, `frontend/` | done |
| 6 Production | `Dockerfile`, `docker-compose.yml` | basic; add monitoring, LangSmith |
| 7 Advanced | multilingual, multi-agent, reports | not started |

## Tests

```bash
pytest tests/          # unit tests need no API key
```
`tests/benchmark_questions.json` is a starter set; grow it to 30-50 questions and score
retrieval, groundedness, citation correctness, freshness and conflict handling as PASS/FAIL.

## Security notes
- Secrets only in `.env` (git-ignored). Admin endpoints need `X-Admin-Token`.
- Retrieved text is wrapped in `<evidence>` tags and treated as data (prompt-injection defence).
- Web fetching is limited to `APPROVED_DOMAINS` in `app/config.py`.
- Agent retries are capped by `MAX_AGENT_LOOPS`.
