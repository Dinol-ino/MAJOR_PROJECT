# DFrag (Defensive RAG) — Enterprise Legal AI Workspace

A Security-Hardened, Privacy-Preserving Legal AI Workspace for Indian Law.

DFrag sits as a defensive wrapper system between users and locally running language models. It provides Indian legal knowledge adaptation via persistent retrieval memory while defending every request through a 3-layer security pipeline.

---

## Architecture & Key Features

1. **Two-Tier Persistent Retrieval Memory**:
   - **Tier 1 (Statutory Law)**: Indian Law DB pre-seeded and indexed by Act, Chapter, and Section.
   - **Tier 2 (User Documents)**: Per-session PDF document ingestion (up to 300 files) using `pdfplumber` with section-aware chunking.
   - **Hybrid Retrieval**: Dense vector embeddings fused with sparse BM25 ranking via Reciprocal Rank Fusion (RRF). Supported storage backends: PostgreSQL + pgvector with ChromaDB fallback.

2. **Three-Layer Security Defense Pipeline**:
   - **Layer 1 (Input Guard)**: Enforces input bounds, detects prompt injection payloads, jailbreak probes, and SQL/command injection strings before model execution.
   - **Layer 2 (Trusted Context)**: Strips embedded instructions from retrieved context chunks, wrapping them inside secure `<data>` XML tags with strict defensive prompt isolation.
   - **Layer 3 (Output Guard)**: Deterministic token overlap grounding check (Jaccard similarity thresholding) and system-prompt leak detection to prevent hallucinations and model leakage.

3. **Stage 5 Intelligent Model Runtime**:
   - Multi-backend model runtime manager supporting **Ollama**, **llama.cpp**, **Transformers**, and **Mock** runtimes.
   - Non-blocking hardware detection, automatic model registry recommendations based on VRAM/RAM profile, and dynamic model downloading.
   - Dynamic token budgeting, context building, hallucination detection, confidence scoring, and citation generation.

4. **Auditing & Cryptographic Integrity**:
   - Cryptographically hash-chained SQLite audit logger verifying query sanitization and generation history against tampering.

---

## Directory Structure

```text
defensive_rag/
└── project/
    ├── backend/
    │   ├── alembic/              # Database schema migrations
    │   ├── app/
    │   │   ├── defense/          # Layer 1, 2, 3 security guards & audit log
    │   │   ├── ingestion/        # PDF extraction & section chunker
    │   │   ├── model/            # Ollama client connection manager
    │   │   ├── retrieval/        # Statutory & user document hybrid rankers
    │   │   ├── routes/           # FastAPI routers (chat, upload, audit, recommend, models)
    │   │   ├── runtime/          # Stage 5 runtime abstraction, context & confidence engines
    │   │   ├── system/           # Hardware detector & model registry
    │   │   ├── config.py         # Application settings
    │   │   ├── main.py           # FastAPI entrypoint
    │   │   └── schemas.py        # Request/response Pydantic models
    │   ├── scripts/              # Seed scripts (seed_tier1.py)
    │   ├── tests/                # Test suite & attack suite benchmarks
    │   ├── Dockerfile
    │   └── requirements.txt
    ├── frontend/                 # React + Vite application
    ├── data/                     # Acts raw data & evaluation datasets
    ├── docs/                     # Architectural & evaluation documentation
    │   ├── security-testing/     # Attack benchmarks & evaluation reports
    │   └── ollama-service-architecture.md
    ├── phase/                    # Project build status & phase logs
    ├── skills/                   # Dev conventions, security checklist & API contract
    ├── advanced_stages/          # Enterprise stage specifications (00-07)
    ├── docker-compose.yml        # Docker orchestrator
    ├── PLAN.md                   # Core execution plan
    └── README.md                 # Primary workspace reference guide
```

---

## Setup & Execution

### Prerequisites
* Docker & Docker Desktop (recommended) OR Python 3.10+ and Node.js 18+
* [Ollama](https://ollama.com/) running locally with target model (e.g. `ollama pull qwen2.5:3b`)

---

### Option 1: Running with Docker (Recommended)

From the `project` root directory:

```bash
docker compose up -d --build
```

* **Frontend UI**: [http://localhost:3000](http://localhost:3000)
* **Backend API & Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

*Note: Subsequent runs can omit `--build` for instant cached startup (`docker compose up -d`).*

---

### Option 2: Local Manual Setup

#### 1. Backend Service
```bash
cd project/backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Service
```bash
cd project/frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your web browser.

---

## Testing & Efficacy Verification

* **Execute Unit Tests**:
  ```bash
  cd project/backend
  .\venv\Scripts\python.exe -m unittest discover tests
  ```

* **Evaluate Security Attack Suite**:
  ```bash
  cd project/backend
  .\venv\Scripts\python.exe tests/attack_suite/run_comparison.py
  ```

---

## Environment & Security Policy

* Secrets and API tokens must be defined in `.env` (copied from `.env.example`).
* Never commit hardcoded tokens, passwords, or credentials.
* Refer to [skills/security-checklist.md](file:///c:/defensive_rag/project/skills/security-checklist.md) prior to merging code changes.
