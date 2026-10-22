# 🚀 Deploying AI Government Research Agent Frontend on Vercel

This guide explains how to deploy the **AI Government Research Agent** React (Vite) frontend to [Vercel](https://vercel.com) and connect it to your hosted FastAPI backend.

---

## 🏗️ Architecture Overview

| Component | Platform | Why |
|---|---|---|
| **Frontend (React / Vite)** | **Vercel** | Ultra-fast global Edge CDN, automatic SSL, instant preview deployments. |
| **Backend (FastAPI + Chroma + ML)** | **Render / Docker** | Persistent Docker environment required for heavy ML libraries (`torch`, `sentence-transformers`, `chromadb`). |

---

## ⚡ 1-Click / Step-by-Step Vercel Deployment

### Step 1: Push your code to GitHub
Ensure your latest changes are pushed to GitHub:
```bash
git add .
git commit -m "Configure Vercel deployment"
git push origin main
```

### Step 2: Import Project on Vercel
1. Log into your [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **"Add New..."** ➔ **"Project"**.
3. Under *Import Git Repository*, select **`samiksha04thakare/government-research-agent`**.

### Step 3: Configure Build & Environment Settings
Vercel will detect the configuration automatically via [`vercel.json`](./vercel.json).

- **Framework Preset**: `Vite`
- **Root Directory**: `./` *(or select `frontend` if preferred)*
- **Build Command**: `cd frontend && npm install && npm run build` *(automatic)*
- **Output Directory**: `frontend/dist` *(automatic)*

#### Required Environment Variable:
Under **Environment Variables**, add:

| Key | Example Value | Description |
|---|---|---|
| `VITE_API_URL` | `https://your-backend.onrender.com` | The public URL of your deployed FastAPI backend |

> **Note for Local Testing:** If running locally, `VITE_API_URL` defaults to `http://localhost:8000` via Vite dev proxy.

### Step 4: Click "Deploy"
Vercel will build and deploy your React frontend in ~30 seconds. You will receive a live URL:
`https://government-research-agent.vercel.app`

---

## ⚙️ CORS & API Verification

The FastAPI backend (`app/main.py`) already has unrestricted CORS configured:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
This ensures your Vercel frontend can make requests to all endpoints (`/health`, `/schemes`, `/api/schemes`, `/research`, etc.) without CORS errors.
