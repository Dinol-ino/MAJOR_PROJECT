# Stage 0: Baseline Audit and Freeze

## Objective

Freeze the migration target before touching code.

## Stage decision

Stage 0 is complete when the repo baseline is documented tightly enough that Stage 1 can start without re-deciding storage, model, ingestion, or environment direction.

## Why this stage exists

The repository already has a working but narrower architecture. The next iteration should reuse what is strong, remove what is redundant, and avoid rewriting stable components without a gain.

## Current-state findings from the repo

1. The retrieval core is already hybrid:
   - dense search in `backend/app/retrieval/tier1_law.py` and `tier2_user.py`
   - sparse search with `BM25`
   - fusion with `fuse_bm25_dense`
2. The defense story is already real:
   - layer 1 input filtering
   - layer 2 trusted context wrapping
   - layer 3 deterministic output validation
3. The main architecture gap is storage and document structure:
   - `ChromaDB` is still the system of record
   - metadata is thin
   - no durable hierarchical `PageIndex`
4. Upload handling is still too narrow:
   - PDF only
   - no OCR fallback
   - no structured document metadata beyond `act` and `section`
5. Session memory semantics are inconsistent with the intended product:
   - Tier-2 retrieval is keyed by `session_id`
   - current design does not support "new session, same uploaded document memory"
6. Audit scoping is incomplete:
   - `/audit/{session_id}` returns all rows, not session-filtered rows
7. Current `.env` only covers the original stack.
8. The repo already contains local runtime artifacts:
   - `backend/chroma_db/`
   - `backend/audit_log.db`
   - `backend/venv/`
   - `frontend/node_modules/`
9. The repo is already dirty outside this stage work:
   - several frontend files are modified
   - Stage 0 should not touch those files

## Verified baseline behavior

### Test execution results

1. `pytest project/backend/tests` from repo root fails collection.
   - reason: `ModuleNotFoundError: No module named 'app'`
   - implication: the current generic test command in docs is not sufficient from the repo root
2. `.\venv\Scripts\python.exe -m pytest tests` from `project/backend` is the valid backend test entrypoint.
   - result: `11 passed, 1 failed`
   - failure: `tests/test_retrieval.py::TestRetrieval::test_retrievers_integration`
   - cause: `Tier1LawRetrieval` tries to resolve `BAAI/bge-small-en` through Hugging Face, but the current environment is blocked by proxy/network settings
3. Stage 0 conclusion:
   - defense-layer tests are passing
   - most retrieval tests are passing
   - one retrieval integration test is externally dependent on model download availability

### Operational baseline

- Current backend runtime is local-first and expects `Ollama`.
- Current retrieval stack is not fully offline on a cold machine unless the embedding model has already been cached locally.
- Current project docs overstate the simplicity of the backend test command.

## Architecture freeze for the next build

1. Keep the existing FastAPI route surface unless a later stage explicitly changes the contract.
2. Keep the current three-layer defensive identity.
3. Keep hybrid retrieval as a core behavior.
4. Replace storage and model plumbing in layers, not in a single cutover.
5. Do not introduce extra model families where one model per task is enough.
6. Do not build the admin model registry before the main retrieval-defense pipeline is stable.

## In-scope outputs for this stage

- stage folder created
- migration order defined
- setup prerequisites listed
- target env variables documented
- real baseline test/verification notes captured
- required directories/files identified
- manual setup and external dependency notes captured
- `STATUS.md` updated with the architecture completion handoff

## Out of scope

- any code migration
- schema changes
- dependency installation
- container edits
- API contract edits

## Directories and files that matter for Stage 0

### Architecture and planning

- `project/stages/README.md`
- `project/stages/stage-0-baseline-audit.md`
- `project/phase/STATUS.md`
- `project/PLAN.md`
- `project/README.md`

### Backend baseline under audit

- `project/backend/app/config.py`
- `project/backend/app/main.py`
- `project/backend/app/routes/`
- `project/backend/app/retrieval/`
- `project/backend/app/defense/`
- `project/backend/app/model/`
- `project/backend/app/ingestion/`
- `project/backend/tests/`
- `project/backend/requirements.txt`
- `project/backend/chroma_db/`
- `project/backend/audit_log.db`

### Frontend baseline under audit

- `project/frontend/src/`
- `project/frontend/package.json`

### Skills and contract files used to constrain the stage

- `project/skills/api-contract.md`
- `project/skills/security-checklist.md`
- `project/skills/coding-conventions.md`
- `project/skills/AGENT_RULES.md`

## Requirements captured at Stage 0

### Current repo/runtime requirements

- Python 3.10+ for the backend
- backend virtual environment at `project/backend/venv/`
- Node.js/npm for the frontend
- local `Ollama` runtime for chat generation in the current stack
- cached or downloadable Hugging Face model assets for `BAAI/bge-small-en`

### Required for the next architecture stages

- PostgreSQL with `pgvector`
- Redis
- local runtime decision for `google/gemma-3-4b-it`
- access plan for `jinaai/jina-embeddings-v3`
- package/runtime plan for `PyMuPDF`, `PaddleOCR`, `Presidio`, and a `DeBERTa-v3` NLI checkpoint
- Langfuse deployment choice and keys

## Manual setup and external dependencies

### Current stack

- `Ollama` must be installed locally for `/chat` to generate answers
- at least one local Ollama model must be pulled, currently `qwen2.5:3b` by default
- if Hugging Face model files are not already cached, retrieval tests may attempt a network download for `BAAI/bge-small-en`
- Docker Desktop is optional, only needed if running through `docker compose`

### Future stack placeholders already added to `.env`

- `HF_TOKEN`
- PostgreSQL connection values
- `REDIS_URL`
- Langfuse host/public/secret keys

### External apps/services to expect later

- PostgreSQL server
- Redis server
- Ollama or alternative local model runtime
- optional Langfuse deployment

## Stage 0 test matrix

1. Planning integrity
   - confirm stage sequence exists under `project/stages/`
   - confirm Stage 1 has a clear next implementation boundary
2. Status handoff
   - confirm `project/phase/STATUS.md` marks Stage 0 complete and Stage 1 ready
3. Backend baseline tests
   - supported command: `.\venv\Scripts\python.exe -m pytest tests` from `project/backend`
   - expected current result: one externally blocked retrieval failure may remain until embedding assets are locally available
4. Documentation consistency
   - `.env` and `.env.example` must list future-stage placeholders without changing the current active stack
5. Safety check
   - Stage 0 must not modify user-owned frontend work already in progress

## Exit criteria

- The migration target is explicit.
- Every later stage has a clear boundary.
- Setup prerequisites are known before implementation starts.
- No architectural ambiguity remains around storage, ingestion, retrieval, defense, or observability.
- The current baseline test reality is documented honestly.
- Stage 1 can start without reopening Stage 0 questions.

## Status update rule

When this stage is accepted, `STATUS.md` should mark Stage 0 as finalized and Stage 1 as the next implementation entrypoint.
