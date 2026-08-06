---
title: Cybersecurity Panel
emoji: 🛡️
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
app_port: 7860
---

# Cybersecurity Panel

AI cybersecurity guidance through a panel of specialized advisors, led by **AI Jerry Huaute, CISSP**, built on Neon AI's Collaborative Conversational AI (CCAI) framework and BrainForge Security models. Collaboration between Jerry Huaute and Neon.ai.

## Hugging Face Spaces

Single Docker image from the repo-root [`Dockerfile`](Dockerfile):

1. Builds the React frontend at image-build time with `REACT_APP_API_URL=""` (same-origin fetches).
2. Serves the SPA from FastAPI on port **7860** with `/api/...` and `/auth/...` on the same origin.
3. Persists auth, profiles, chat sessions, onboarding, canvas, and user knowledge in **SQLite** (`aiosqlite`) at `${DATA_DIR}/cybersecurity_panel.db`. Mount a Hugging Face Storage Bucket at `/data` so data survives rebuilds. Vector store: ChromaDB under the same data dir.

### Required Space secrets

| Secret | Purpose |
|--------|---------|
| `JWT_SECRET_KEY` | Signs auth tokens (long random string) |
| `VLLM_API_KEY` / Neon HANA creds | Neon vLLM / BrainForge Security endpoint |
| `OPENAI_API_KEY` | GPT fallback / large-model path |
| `GEMINI_API_KEY` | Optional Gemini provider |

Also loadable from a shared env file at `C:\Users\dream\.secrets\shared.env` for local development (`SHARED_ENV` / compose `env_file`).

## Local development

### Production-shaped container (matches Spaces)

```bash
# PowerShell
$env:COMPOSE_DATE = Get-Date -Format "yyyyMMdd"
docker compose up --build
# App: http://localhost:7861
```

### Hot-reload development (recommended while coding)

```bash
$env:COMPOSE_DATE = Get-Date -Format "yyyyMMdd"
docker compose --profile dev up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000  (docs at /docs)
```

Backend uses `uvicorn --reload`; frontend uses CRA with file polling. Source is bind-mounted from `multi_llm_chatbot_backend/`, `frontend/`, `personas/`, and `cybersecurity_config.yaml`.

### Without Docker

1. Load secrets from `C:\Users\dream\.secrets\shared.env` (or set `JWT_SECRET_KEY`, `OPENAI_API_KEY`, `VLLM_API_KEY`, etc.).
2. Backend: `cd multi_llm_chatbot_backend && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
3. Frontend: `cd frontend && npm ci && set REACT_APP_API_URL=http://localhost:8000 && npm start`

## Architecture

| Layer | Tech |
|-------|------|
| Frontend | React (CRA) in `frontend/` |
| Backend | FastAPI in `multi_llm_chatbot_backend/` |
| DB | SQLite via Mongo-shaped shim (`app/core/db.py`) |
| Vectors | ChromaDB (document RAG) |
| Primary LLM | Neon vLLM — `BrainForge/Security` |
| Fallback | OpenAI GPT (resilient race), Gemini, Ollama |

### Advisors

Personas live in `personas/cyber_advisors/*.yaml` (Jerry Huaute lead + specialist panel). App config: `cybersecurity_config.yaml`.

### Features

- Panel chat with streaming multi-advisor responses; Jerry Huaute always on the panel, urgency triage puts the incident expert first, generated follow-up chips after each panel reply
- User profile: stated + inferred facts, dual LLM summaries (short for Neon, long for large models)
- Security Journey progress tracks (ITIL, NIST CSF, CIS, certs, personal digital security, custom)
- Document upload + RAG, export (TXT/PDF/DOCX)
- Model Status health probes and provider selection (Settings → Model Status)

## Project layout

```
cybersecurity-panel/
├── cybersecurity_config.yaml
├── personas/cyber_advisors/
├── tracks/                 # Security Journey track definitions
├── multi_llm_chatbot_backend/
├── frontend/
├── Dockerfile              # HF Spaces / prod
├── Dockerfile.dev          # hot-reload targets
├── docker-compose.yml
├── PLAN.md                 # overhaul plan
└── README.md
```

## Tests

```bash
cd multi_llm_chatbot_backend
pip install -r requirements.txt -r test_requirements.txt
python -m pytest app/tests/unit -q
```

## License / credit

© Neon AI. Built with Jerry Huaute, CISSP. CCAI and BrainForge are Neon.ai technologies.
