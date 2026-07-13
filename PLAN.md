# DFrag — Execution Plan

Defense-hardened Legal RAG · 3 devs · 15-hour build · local-first stack

## 0. Design fixes applied on top of the blueprint

| Blueprint claim | Problem | Fix locked for build |
| :--- | :--- | :--- |
| Layer 3 "grounding check" done by the LLM judging itself | Weak model self-judging its own hallucination has high false-negative rate | Deterministic **token/entity overlap** between answer and retrieved `<data>` chunks (threshold, e.g. $\ge 0.4$ Jaccard on content words). No second LLM call. |
| 3 devs all writing to shared Tier-1 ChromaDB | Local persistence isn't safe for concurrent writers across machines | Tier-1 build is a **one-time seed script** (`scripts/seed_tier1.py`), run locally by each dev, output dir gitignored. Never commit the Chroma binary dir. |
| "SQL injection structurally impossible" | True only if enforced | Added as a **PR checklist item**: no f-string/format SQL, parameterized only — checked before every merge to `main`. |
| Layer 1 regex/keyword injection detection | Bypassable via encoding/translation | Documented explicitly as a **known limitation** in report; attack suite must include one Layer-1-bypass case that L2/L3 still catch, to demonstrate defense-in-depth, not reliance on L1 alone. |

## 1. Repository structure

```
dfrag/
├── PLAN.md                     # this file — source of truth
├── skills/                     # agent/dev conventions
│   ├── AGENT_RULES.md
│   ├── api-contract.md
│   ├── coding-conventions.md
│   └── security-checklist.md
├── phase/                      # phase tracking
│   ├── phase-0-setup.md
│   ├── phase-1-parallel-build.md
│   ├── phase-2-integration.md
│   ├── phase-3-defense-wireup.md
│   ├── phase-4-polish.md
│   └── STATUS.md               # single-line status per phase
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint, routes only
│   │   ├── config.py           # env vars, model name, paths
│   │   ├── schemas.py          # pydantic request/response models
│   │   ├── retrieval/
│   │   │   ├── tier1_law.py    # Tier-1 law (Indian Law DB) retrieval
│   │   │   ├── tier2_user.py    # Tier-2 user PDF retrieval
│   │   │   ├── hybrid_rank.py  # BM25 + dense fusion
│   │   │   └── pageindex.py    # act/chapter/section tree builder
│   │   ├── defense/
│   │   │   ├── layer1_input_guard.py
│   │   │   ├── layer2_trusted_context.py
│   │   │   ├── layer3_output_guard.py
│   │   │   └── audit_log.py    # hash-chained SQLite
│   │   ├── model/
│   │   │   ├── ollama_client.py
│   │   │   └── recommend.py    # hardware -> model recommendations
│   │   ├── ingestion/
│   │   │   ├── pdf_extract.py  # pdfplumber wrapper
class Settings(BaseModel):
│   │   │   └── chunker.py      # section-aware chunker
│   │   └── routes/
│   │       ├── chat.py
│   │       ├── upload.py
│   │       ├── recommend.py
│   │       └── audit.py
│   ├── scripts/
│   │   └── seed_tier1.py       # law DB seeding script
│   ├── tests/
│   │   ├── test_defense_layers.py
│   │   ├── test_retrieval.py
│   │   └── attack_suite/
│   │       ├── attacks.json    # 10 attack prompts
│   │       ├── run_comparison.py
│   │       └── malicious.pdf   # hidden instruction PDF
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx
│   │   │   ├── ShieldToggle.jsx
│   │   │   ├── SourcesPanel.jsx
│   │   │   ├── MicButton.jsx
│   │   │   ├── UploadButton.jsx
│   │   │   └── HardwareForm.jsx
│   │   ├── api/
│   │   │   └── client.js       # API client wrapper
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── data/
│   └── acts_raw/               # raw acts folder
├── docker-compose.yml
└── README.md
```

## 2. Branching strategy

- `main`: always demoable, protected, no direct pushes.
- `dev`: integration branch, merges land here first.
  - `feat/frontend-a` (Person A - UI Developer)
  - `feat/rag-core-b` (Sweedan - RAG & Retrieval)
  - `feat/defense-c` (Dinol - Security & Defense)
- `main` is only merged from `dev` at the end of Phase 2 and Phase 3 (two demoable checkpoints).
- Each person branches `feat/*` off `dev`, rebases onto `dev` before opening a PR.

## 3. API contract

Refer to `skills/api-contract.md` for JSON details.

## 4. Skills / conventions

Refer to files in `skills/`.

## 5. Phase structure

Refer to files in `phase/`.

---

## 6. Backend Developer Workspace Isolation Guide (Sweedan & Dinol)

To build the DFrag backend without merge conflicts or overlapping modifications, Sweedan and Dinol work in strictly separate files (subtrees) and merge via standard pull requests targeting the `dev` branch.

### Division of Labor

| Developer | Area | Key Subtree / Files | Responsibilities |
| :--- | :--- | :--- | :--- |
| **Sweedan** | RAG Core & Ingestion | `backend/app/retrieval/`<br>`backend/app/ingestion/`<br>`backend/scripts/` | - Section-aware metadata extractor (`pageindex.py`) & chunker (`chunker.py`).<br>- Secure PDF extraction using `pdfplumber` (`pdf_extract.py`).<br>- Tier-1 (Indian law DB) & Tier-2 (User upload) query search interface.<br>- Dense vector retrieval & BM25 hybrid ranking fusion (`hybrid_rank.py`).<br>- DB seed logic (`seed_tier1.py`). |
| **Dinol** | Defense, Model & Logs | `backend/app/defense/`<br>`backend/app/model/`<br>`backend/tests/` | - Regex & length validation checks (`layer1_input_guard.py`).<br>- Trusted context formatter & XML boundary builder (`layer2_trusted_context.py`).<br>- Grounding token similarity overlap & system leak checks (`layer3_output_guard.py`).<br>- Cryptographic hash-chained SQLite logger (`audit_log.py`).<br>- Ollama server calls & model hardware mappings (`ollama_client.py` & `recommend.py`).<br>- Attack suite evaluation script (`run_comparison.py`). |

### Rules for Conflict Prevention
1. **Never edit each other's directories**: Sweedan must not commit changes to files in `backend/app/defense/` or `backend/app/model/`, and Dinol must not modify files in `backend/app/retrieval/` or `backend/app/ingestion/`.
2. **Frozen Interface Contract (`schemas.py` and `api-contract.md`)**: The API paths, request bodies, and response structures are frozen in `schemas.py` and `api-contract.md`. If a schema change is absolutely necessary, both developers must align first and increment the version comment inside `schemas.py`.
3. **Route Registration**: Registration of API routers inside `backend/app/main.py` is the only point of overlap. Both developers should register their respective routes as clean blueprints:
   - Sweedan owns `/upload` route registration.
   - Dinol owns `/chat`, `/recommend`, and `/audit` route registration.

---

## 7. Agent Quota Recovery & Resumability Protocol

When using AI coding agents (such as Claude Code, Antigravity, or other LLM subagents) to build features, the agent's context window quota or token limit may expire mid-task. The following protocol guarantees safe state handoffs:

### 1. The Resume File: `phase/STATUS.md`
Every agent startup or session resume **must** read `phase/STATUS.md` first.
- The `STATUS.md` file tracks the single active phase, current task, modified files, and developer owner.
- When an agent is forced to stop due to quota depletion, it must edit `STATUS.md` to document the current state before exiting.

### 2. File State Format in `phase/STATUS.md`
Format of the status line:
`Phase [Number] — [STATUS] — [Date-Time] — [Developer Name] (Active: [File Path] | Task: [Description] | Last Git Commit: [Hash])`

### 3. Step-by-Step Recovery Workflow
1. **Agent Startup**: Read `phase/STATUS.md`.
2. **Locate Phase File**: Open the corresponding phase checklist file (e.g. `phase/phase-1-parallel-build.md`).
3. **Identify Work In Progress**: Look for `[/]` (in-progress) or `[ ]` (pending) items marked with the developer's name (e.g. `[Sweedan]` or `[Dinol]`).
4. **Execute & Commit**: Proceed with code edits, run corresponding module tests, commit changes using Conventional Commits.
5. **Update Checklists**: Mark the item as completed (`[x]`) and update `phase/STATUS.md`.
