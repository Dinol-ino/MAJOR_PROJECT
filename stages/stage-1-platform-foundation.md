# Stage 1: Platform Foundation

## Objective

Replace the fragmented persistence model with a PostgreSQL-backed relational foundation that supports metadata, governance, and future pgvector expansion without breaking the current application shell.

## Target state

- `PostgreSQL` becomes the primary relational system of record.
- `pgvector` is deferred to Stage 3 because the server extension is unavailable on the current Windows PostgreSQL install.
- `Redis` is introduced for conversation/session memory only.
- The current hash-chained audit concept is preserved instead of discarded.

## Key architecture decisions

1. Use one document model for both corpora:
   - `tier1_law`
   - `tier2_user`
   - stored as a `corpus_type` field, not as separate databases
2. Introduce stable identifiers:
   - `workspace_id`
   - `document_id`
   - `upload_id`
   - `chunk_id`
   - `session_id`
3. Split persistence by responsibility:
   - PostgreSQL: metadata, document index, chunk records, embedding manifest rows, permissions
   - Redis: ephemeral chat/session context
   - audit chain: keep as dedicated append-only log until a later stage proves a safe migration path
4. Do not rewrite the frontend yet.
5. Do not fake pgvector support. Keep Stage 1 relational-only and make Stage 3 the vector-storage migration point.

## Schema direction

The relational entities created by Stage 1 are:

- `documents`
- `document_versions`
- `chunks`
- `chunk_embeddings`
- `uploads`
- `sessions`
- `model_catalog`
- `retrieval_events`
- `audit_events`

## Required installs and services

- PostgreSQL 17/18 reachable on `localhost:5432`
- Redis reachable on `localhost:6379`
- Python PostgreSQL driver: `psycopg`
- ORM/migrations: `SQLAlchemy` + `Alembic`
- `pgvector` server extension is not required in Stage 1

## Required `.env` values

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `PGVECTOR_DIMENSIONS`
- `REDIS_URL`
- `SESSION_TTL_SECONDS`
- `CHROMA_LEGACY_ENABLED`

## Implemented in this stage

- Added SQLAlchemy platform foundation under `backend/app/platform/`.
- Added Alembic migration support under `backend/alembic/`.
- Added relational tables for documents, versions, chunks, embedding manifest rows, uploads, sessions, model catalog, retrieval events, and audit events.
- Added Redis session memory wrapper with TTL support.
- Added `scripts/bootstrap_platform.py` to create the target database and apply migrations.
- Updated backend config to load `.env` and expose PostgreSQL/Redis settings.
- Kept Chroma as legacy-only during the transition, but stopped relying on Hugging Face downloads for legacy Chroma tests by adding a deterministic local embedding fallback.
- Updated Docker Compose/backend env plumbing for PostgreSQL and Redis access through the host.

## Current local verification

- PostgreSQL connectivity: passed.
- Redis connectivity: passed.
- Platform bootstrap: passed against the local `dfrag` database.
- Backend tests: `16 passed`.

Command used:

```powershell
cd project/backend
.\venv\Scripts\python.exe scripts\bootstrap_platform.py
.\venv\Scripts\python.exe -m pytest tests
```

## pgvector compatibility decision

Stage 1 does not create `CREATE EXTENSION vector` and does not create any `VECTOR` columns.

The `chunk_embeddings` table is intentionally an embedding manifest table for now:

- `model_name`
- `dimensions`
- `storage_status`
- `embedding_ref`
- `metadata_json`

Stage 3 can add a real pgvector column with a focused migration after the server extension is available.

## In scope

- database and tenancy design
- retrieval persistence design
- session-memory design
- env contract for new services
- cutover strategy away from Chroma

## Out of scope

- OCR
- reranking
- LegalBERT
- Presidio
- Langfuse wiring
- model registry UI
- server-side pgvector installation
- vector column migration

## Risks

1. Moving audit storage too early can destroy the strongest existing trust feature.
2. Mixing session memory with document memory will recreate the same design bug in a different store.
3. Replacing Chroma before the schema is final will create rework.
4. pgvector support must be added later as a deliberate Stage 3 migration, not silently assumed.

## Exit criteria

- PostgreSQL is the approved relational source of truth for retrieval metadata and future retrieval memory.
- Redis is approved only for ephemeral session state.
- The future data model is stable enough for ingestion work to begin.
- Chroma is clearly classified as legacy to be migrated out.
- pgvector is explicitly deferred to Stage 3, not faked in Stage 1.
- Backend tests pass with the Stage 1 foundation in place.
