# Deploying AI Government Research Agent on Render

This guide provides step-by-step instructions for deploying the **AI Government Research Agent** on [Render](https://render.com).

The application is architected as a **unified service**: FastAPI backend, Chroma vectorstore, SQLite/PostgreSQL relational database, and the React (Vite) frontend are all served from a single web service.

---

## Deployment Options

You can deploy using either **Option 1 (Render Blueprint - Easiest)** or **Option 2 (Manual Web Service)**.

---

### Option 1: Render Blueprint (1-Click Deployment)

The repository includes a ready-to-use [`render.yaml`](./render.yaml) specification.

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Configure Render deployment and multi-stage Docker build"
   git push origin main
   ```
2. **Log into Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com).
3. **Create New Blueprint**:
   - Click **New +** in the top right.
   - Select **Blueprint**.
   - Connect your GitHub repository: `samiksha04thakare/government-research-agent`.
4. **Configure Environment Variables**:
   Render will automatically parse `render.yaml` and prompt you for required secrets:
   - **`GROQ_API_KEY`**: Your Groq API Key (get one free at [console.groq.com/keys](https://console.groq.com/keys)).
   - **`ANTHROPIC_API_KEY`**: *(Optional)* Your Anthropic Claude API Key if using Claude.
   - **`ADMIN_TOKEN`**: Automatically generated secure token, or set your own (e.g. `admin123`).
5. **Click "Apply"**:
   Render will build the Docker container and deploy the service.

---

### Option 2: Manual Web Service Deployment

If you prefer to configure the service manually in the Render dashboard:

1. **Push your code to GitHub**.
2. **In Render Dashboard**:
   - Click **New +** -> **Web Service**.
   - Choose **Build and deploy from a Git repository**.
   - Connect `samiksha04thakare/government-research-agent`.
3. **Configure Service Details**:
   - **Name**: `ai-government-research-agent` (or your preferred name)
   - **Region**: Choose the closest region (e.g., *Singapore*, *Oregon*, or *Frankfurt*).
   - **Branch**: `main`
   - **Runtime**: Select **Docker**.
   - **Instance Type**: **Free** (or *Starter* for persistent production workloads).
4. **Health Check Path**:
   - Under **Advanced Settings**, set **Health Check Path** to `/health`.
5. **Environment Variables**:
   Under **Environment Variables**, add the following keys:

   | Key | Value / Description | Required |
   |---|---|---|
   | `PORT` | `10000` *(Render sets this dynamically)* | Optional |
   | `GROQ_API_KEY` | `gsk_...` (Your Groq API key) | Recommended (Free) |
   | `GROQ_MODEL` | `llama-3.3-70b-versatile` | Yes |
   | `ANTHROPIC_API_KEY` | `sk-ant-...` (Your Claude API key) | Optional |
   | `LLM_MODEL` | `claude-sonnet-4-5` | Yes |
   | `ADMIN_TOKEN` | `your-secure-admin-token` | Yes |
   | `DATABASE_URL` | `sqlite:///./research.db` | Yes |
   | `CHROMA_DIR` | `vectorstore` | Yes |
   | `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Yes |
   | `MAX_AGENT_LOOPS` | `2` | Yes |
   | `RELEVANCE_THRESHOLD` | `0.25` | Yes |

6. **Click "Create Web Service"**.

---

## Build & Startup Process Explained

When Render builds the service:
1. **Frontend Stage**: Node.js 20 builds the React Vite application into `frontend/dist/`.
2. **Backend Stage**: Python 3.11 installs CPU-optimized PyTorch and dependencies.
3. **Auto-Bootstrapping**: On container startup:
   - Tables (`Document`, `Scheme`, `ResearchHistory`) are created.
   - 23+ official structured Maharashtra & Central schemes are seeded into the database.
   - Baseline agricultural guidelines and policy texts are automatically indexed into ChromaDB.
4. **Port Binding**: Uvicorn binds to `0.0.0.0` on Render's dynamic `$PORT`.
5. **Unified Delivery**: FastAPI serves the React web interface on `/` and the REST API endpoints on `/research`, `/schemes`, `/documents`, etc.

---

## Verifying Your Deployment

Once Render finishes deploying (marked with a green **Live** badge):

1. **Open the Web Portal**:
   - Click the onrender.com URL (e.g. `https://ai-government-research-agent.onrender.com`).
   - The interactive research portal will load.
2. **Verify Health Endpoint**:
   - Visit `https://your-service.onrender.com/health`.
   - Expected JSON:
     ```json
     {
       "status": "ok",
       "has_api_key": true,
       "llm_model": "llama-3.3-70b-versatile (Groq)",
       "indexed_documents": 13,
       "total_documents": 13,
       "structured_schemes": 23
     }
     ```
3. **Interactive API Documentation**:
   - Visit `https://your-service.onrender.com/docs` to test endpoints via Swagger UI.

---

## Optional: Connecting a Render PostgreSQL Database

If you want long-term persistent database storage beyond the default SQLite file:
1. In Render Dashboard, click **New +** -> **PostgreSQL**.
2. Copy the **Internal Database URL** (e.g., `postgres://user:pass@host/dbname`).
3. In your Web Service settings, update `DATABASE_URL` with this value.
4. The application automatically normalizes `postgres://` to `postgresql://` and connects to the managed database.
