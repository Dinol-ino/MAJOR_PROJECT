# Phase 02 — PostgreSQL as Production Persistence Layer

Depends on: Phase 01 (config registry for pool/timeout settings)
Blocks: Phase 03 (memory layers need a stable persistence layer)
Modifies: DB connection/session handling throughout backend
Introduces: async SQLAlchemy engine, Alembic migrations, connection pooling
Validates: restart recovery, transaction integrity, no dual-source-of-truth with SQLite

## Objective
Make PostgreSQL a real production persistence layer — pooled, async, migrated, health-checked — and settle, per data class, which store is authoritative.

## Current State
Per Phase 00 manifest — report claims "SQLite/PostgreSQL memory," ambiguous on which is authoritative for what. Verify: is PostgreSQL actually wired into request-handling code, or present but unused? Confirm before writing a single migration.

## Problem
Two persistence layers claiming the same role is a duplicated source of truth — exactly what the architecture principle forbids. This has to be resolved explicitly, not left ambiguous.

## Architecture Change
Current (ambiguous/dual) → Transitional (PostgreSQL primary, SQLite read-only fallback for local-only dev) → Target (PostgreSQL sole authoritative store for relational data; SQLite removed from production path).

**Authoritative store per data class:**
| Data | Store |
|---|---|
| Sessions, messages, conversation memory | PostgreSQL |
| Semantic memory (facts/preferences) | PostgreSQL (structured) |
| Document memory (indexed user docs — metadata) | PostgreSQL |
| Document memory (embeddings) | ChromaDB |
| Legal corpus text + provenance metadata | PostgreSQL (metadata) + filesystem or ChromaDB (content/embeddings) |
| Research memory (sessions/sources/citations/findings) | PostgreSQL |
| Audit ledger | PostgreSQL, append-only table with hash-chaining (see Phase 07 for cryptographic requirements) |
| Cache (retrieval/response) | In-process or Redis if already present — never PostgreSQL |

## Files to Modify
`backend/app/db/*` (exact files from Phase 00 manifest) — replace sync/SQLite-only connections with async engine.

## Files to Add
- `backend/app/db/engine.py` — async SQLAlchemy engine, connection pool config from `settings.py`.
- `backend/alembic/` — migration directory, initial migration capturing current schema (whatever Phase 00 finds actually exists).
- `backend/app/db/health.py` — health check endpoint logic (DB reachable, pool not exhausted).

## Files to Remove
SQLite connection code, only after Phase 00 confirms no production path still depends on it and after data migration (if any real data exists in SQLite) is verified complete.

## Dependencies
Depends on: Phase 01
Blocks: Phase 03
Modifies: all DB-touching modules
Introduces: Alembic, async engine
Validates: Phase 03's memory layers can read/write reliably

## Implementation Steps
1. From Phase 00 manifest, confirm actual current schema (don't assume — generate `alembic revision --autogenerate` against the real DB to see what Alembic thinks exists vs what code expects; reconcile discrepancies before writing new migrations).
2. Introduce async engine with pool size/timeout from config (Phase 01).
3. Add retry-with-backoff for transient connection failures (not silent infinite retry — bounded, configurable).
4. Add health check endpoint (`/health/db`) verifying pool + basic query.
5. Define transaction boundaries explicitly per write path — no implicit autocommit for multi-step writes (e.g. writing a message + updating conversation `last_message_at` must be one transaction).
6. Add indexes/FKs/uniqueness constraints per the schema (user_id FKs everywhere data is user-scoped, unique constraint on session tokens, etc.).
7. Startup migration validation: app refuses to start if migrations are pending/inconsistent with code expectations, rather than starting in a broken state.

## Configuration
`DATABASE_URL`, `DB_POOL_SIZE`, `DB_POOL_TIMEOUT`, `DB_STATEMENT_TIMEOUT` — env vars per Phase 01's deployment-config convention.

## API Changes
`GET /health/db` — new endpoint, returns pool status and last successful query latency.

## Database Changes
Full schema migration set via Alembic — exact DDL depends on Phase 00 findings; at minimum: `conversations`, `messages`, `semantic_memory`, `document_memory`, `research_sessions`, `research_sources`, `audit_events`, `legal_documents`, `document_versions` (provenance schema from `stages_2/02`).

## Security Requirements
Connection strings never logged. Statement timeout prevents runaway queries from being a DoS vector. Foreign keys enforce user-scoping at the DB level, not just application logic (defense in depth against an application bug leaking cross-user data).

## Performance Requirements
Connection pool sized against actual hardware tier (Phase 05's hardware detection) — don't hardcode pool size; a Tier 0 machine shouldn't get a pool sized for a server deployment.

## Testing
- Unit: transaction rollback on partial failure.
- Integration: restart recovery — kill the process mid-write, confirm no partial/corrupt state on restart.
- Load: concurrent connection exhaustion behavior (graceful queueing/rejection, not crash).

## Acceptance Criteria
- Single authoritative store per data class, documented and enforced (no code path writes conversation data to SQLite).
- App fails to start on pending/broken migrations.
- Restart-recovery test passes with zero data loss for committed transactions.

## Rollback
Alembic downgrade to prior revision; if SQLite removal already happened, rollback requires restoring from the pre-removal branch — document this explicitly as a harder rollback than most phases, test it once before considering the phase done.

## Validation Commands
```
alembic upgrade head
alembic check
pytest backend/tests/db/ -v
```
