# DFrag Architecture Stages

This folder is the architecture migration track for `feat/backend-dinol`.

It is based on:

- the current repository state under `project/`
- the original blueprint in `DFrag_Blueprint.pdf`
- the current execution plan in `PLAN.pdf` / `project/PLAN.md`
- the updated target stack from the attached architecture note

## Current baseline observed in the repo

- Backend remains `FastAPI`.
- Frontend remains `React + Vite`.
- Dense retrieval still has a legacy `ChromaDB` path during staged cutover.
- Sparse retrieval already exists through `BM25`.
- Fusion already exists through `RRF`.
- Upload parsing now routes through the Stage 2 parser contract.
- Raw uploaded files are persisted under `UPLOAD_ROOT`.
- PageIndex metadata is persisted relationally in PostgreSQL chunks.
- Generation is routed through `Ollama`.
- Audit persistence is a hash-chained `SQLite` log.
- Legacy Tier-2 retrieval can still be scoped to `session_id` until Stage 3 retrieval migration completes.

## Locked optimization decisions

These decisions are the target unless a later stage explicitly changes them:

1. Keep `FastAPI`, `React`, and `Docker` as the outer application shell.
2. Use PostgreSQL as the relational source of truth from Stage 1 onward.
3. Defer pgvector server integration to Stage 3 because the current Windows PostgreSQL server does not expose the `vector` extension.
4. Keep one dense embedding stack only when Stage 3 starts: `jina-embeddings-v3`.
5. Keep `BM25 + RRF`, then add a reranker instead of introducing more retrieval layers.
6. Move ingestion to `PyMuPDF` first, with `PaddleOCR` only as a fallback for scanned pages.
7. Preserve the three-layer defense concept, but upgrade it with a `LegalBERT` classifier and chunk trust scoring.
8. Keep the existing append-only audit-chain idea; do not remove it just because the storage layer changes.
9. Add `Redis` for session memory, `Langfuse` for tracing/evals, and output verification with `Presidio` plus a `DeBERTa-v3` NLI checkpoint.
10. Treat a full admin model registry as optional until the core retrieval-defense pipeline is stable.

## Stage order

- `stage-0-baseline-audit.md`
- `stage-1-platform-foundation.md`
- `stage-2-ingestion-pageindex.md`
- `stage-3-retrieval-ranking.md`
- `stage-4-defense-trust.md`
- `stage-5-generation-output-guard.md`
- `stage-6-memory-observability-admin.md`
- `stage-7-cutover-hardening.md`

## Working rule

Only move to the next stage when the previous stage exit criteria are met and `project/phase/STATUS.md` is updated.

## Setup before future stages

Already active after Stage 2:

- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- Alembic migrations for the relational foundation
- Durable upload storage through `UPLOAD_ROOT`
- Relational document/version/upload/chunk persistence
- Deterministic PageIndex metadata for uploaded PDF/TXT/DOCX files

Needed before later stages:

- pgvector server extension before Stage 3 vector columns are added
- local model runtime plan for `google/gemma-3-4b-it`
- access plan for `jinaai/jina-embeddings-v3`
- optional `PaddleOCR` installation and OCR runtime dependencies if scanned PDFs must be parsed
- Python package plan for `Presidio` and the chosen `DeBERTa-v3` NLI checkpoint
- Langfuse deployment choice: cloud or self-hosted

The active environment variables are listed in `.env` and `.env.example`.