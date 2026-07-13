# DFrag (Defensive RAG)

A Security-Hardened, Privacy-Preserving Legal AI Workspace for Indian Law.

DFrag sits as a defensive wrapper system between a user and locally running language models. It provides Indian legal knowledge adaptation via persistent retrieval memory while defending every request through a three-layer defense pipeline.

---

## Key Features

1. **Two-Tier Persistent Retrieval Memory**:
   - **Tier 1**: Pre-loaded Indian Law DB (indexed by Act & Section).
   - **Tier 2**: User-uploaded documents (up to 300 PDFs) stored per session.
2. **Three-Layer Defense Pipeline**:
   - **Layer 1: Input Guard**: Enforces length limits, blocks direct prompt injections, jailbreaks, and SQL/command probes.
   - **Layer 2: Trusted Context**: Strips embedded instructions from retrieved text chunks and wraps them in secure `<data>` xml boundary tags with defensive system prompt rules.
   - **Layer 3: Output Guard**: Enforces deterministic token/entity overlap checks (Jaccard similarity on content words) to prevent model hallucinations and system-prompt text leakages.
3. **Auditing & Traceability**:
   - Cryptographically hash-chained append-only SQLite log records verifying all sanitization and generation histories.

---

## Technology Stack

- **Model Runtime**: Ollama (Qwen2.5:3B default)
- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite (Vanilla CSS)
- **Vector DB / Search**: ChromaDB + BM25 Hybrid Ranker
- **Database**: SQLite (Audit Log)
- **Containerization**: Docker Compose

---

## Setup & Running

### Prerequisites
1. Install [Ollama](https://ollama.com/) locally.
2. Pull the default model:
   ```bash
   ollama pull qwen2.5:3b
   ```

### Option 1: Docker Compose (Recommended)
From the root directory:
```bash
docker compose up --build
```
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

### Option 2: Local Manual Setup

#### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your web browser.

---

## Development Guidelines

- Refer to `skills/AGENT_RULES.md` for team coordination and subtree boundaries.
- Run `pytest backend/tests/` to execute unit tests.
- Run `python backend/tests/attack_suite/run_comparison.py` to evaluate defensive efficacy against prompt injection and SQL probe payloads.
