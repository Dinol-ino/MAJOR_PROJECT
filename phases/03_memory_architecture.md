# Phase 03 — Layered Memory Architecture

Depends on: Phase 02 (stable PostgreSQL persistence)
Blocks: Phase 09 (agentic orchestrator needs research memory), Phase 10 (research pipeline writes to research memory)
Modifies: any existing undifferentiated memory/history handling
Introduces: 6 explicit memory layers with distinct policies
Validates: no single table holds mixed memory types; no blind embedding of every message

## Objective
Split memory into 6 explicit layers, each with its own retention, isolation, and access policy — replacing whatever undifferentiated storage currently exists.

## Current State
Per Phase 00 manifest. Likely: conversation history exists in some form; semantic/document/research/audit layers are probably not explicitly separated even if data for them exists somewhere.

## Problem
Undifferentiated memory means no policy can be applied consistently — you can't set a sane retention rule or deletion guarantee on "everything in one table," and it risks embedding every message (expensive, low-value, and a privacy surface) rather than selectively persisting what matters.

## Architecture Change

| Layer | Store | Scope | Policy |
|---|---|---|---|
| L1 Request | In-process (request-scoped object, not persisted) | Single request | Discarded on response |
| L2 Conversation | PostgreSQL `messages` (Phase 02) | Session/user | Retention configurable, TTL-based Redis cache for active session, durable in Postgres |
| L3 Semantic | PostgreSQL `semantic_memory` | User | Explicitly selected only — LLM proposes, policy layer validates before persisting, never auto-persists arbitrary content |
| L4 Document | PostgreSQL metadata + ChromaDB embeddings | User/workspace | Indexed on upload, deletion cascades both stores |
| L5 Research | PostgreSQL `research_sessions/sources/findings` | User/session | Full provenance retained (Phase 10 schema), versioned |
| L6 Audit | PostgreSQL `audit_events`, append-only | System | Immutable, hash-chained (Phase 07), never deleted except by explicit, logged retention policy |

## Files to Modify
Existing chat history / memory modules per Phase 00 manifest.

## Files to Add
- `backend/app/memory/request_memory.py` (L1)
- `backend/app/memory/conversation_memory.py` (L2)
- `backend/app/memory/semantic_memory.py` (L3) — includes the validation gate: LLM-proposed facts pass through a policy check (format, no PII unless explicitly consented, not a duplicate) before write.
- `backend/app/memory/document_memory.py` (L4)
- `backend/app/memory/research_memory.py` (L5)
- `backend/app/memory/audit_memory.py` (L6)
- `backend/app/memory/policies.py` — shared retention/dedup/TTL/isolation logic used by all layers, not reimplemented per layer.

## Files to Remove
Any single undifferentiated "memory" table/module, once all 6 layers are live and data migrated — only after Phase 15 regression confirms nothing still reads the old path.

## Dependencies
Depends on: Phase 02
Blocks: 09, 10
Modifies: chat/history handling
Introduces: 6-layer memory model
Validates: session/user isolation tests (also feeds Phase 12's memory eval category)

## Implementation Steps
1. Define the 6 module interfaces first (read/write/delete/list contracts) before migrating data — this forces the isolation/policy questions to be answered up front.
2. Implement `policies.py`: retention (per-layer configurable TTL/max-age), dedup (hash-based for L3/L5), session isolation (identity-bound per Phase 01's Stage-1-equivalent fix), provenance stamping (who/when/source for every write).
3. Migrate existing history data into L2 schema.
4. Implement the L3 validation gate explicitly — this is the item the spec calls out most directly ("LLM must not automatically decide arbitrary long-term memory without policy validation"): proposed semantic facts go through format + dedup + consent check before persisting, rejected facts are logged (not silently dropped) for debuggability.
5. Wire L4 deletion cascade (delete document → delete Postgres metadata row + ChromaDB vectors, verify both succeed or roll back).
6. Wire L6 as append-only from day one — no update/delete path exposed in the module's API surface at all, not just policy-restricted.

## Configuration
Per-layer retention periods, L3 dedup similarity threshold, L2 Redis TTL — all in `settings.py` (Phase 01), no hardcoded values.

## API Changes
- `GET /memory/semantic` — list a user's semantic memory entries (transparency requirement).
- `DELETE /memory/semantic/{id}` — explicit user-initiated deletion.
- `GET /memory/research/{session_id}` — retrieve a research session's findings/provenance.

## Database Changes
New tables per layer (L2/L3/L4-metadata/L5/L6) — see Phase 02's table list. Add `deleted_at` soft-delete columns where retention policy requires audit trail of deletion itself (except L6, which is never deleted at the row level).

## Security Requirements
L6 audit memory must be tamper-evident (ties to Phase 07's hash-chaining requirement) — this phase creates the schema, Phase 07 adds the cryptographic guarantee. Cross-user isolation enforced at query level (every read filtered by authenticated identity, never trusting a client-supplied user/session identifier).

## Performance Requirements
L1 must add near-zero overhead (in-process only). L2 read path (loading conversation context) should hit Redis before Postgres — measure actual latency, don't assume.

## Testing
- Unit: L3 validation gate rejects malformed/duplicate/non-consented facts.
- Integration: L4 deletion cascade leaves no orphaned vectors in ChromaDB.
- Security: cross-user isolation test — user A cannot read user B's L2/L3/L4/L5 data under any crafted request.

## Acceptance Criteria
- All 6 layers implemented with distinct storage and policy.
- No code path embeds every conversational message into L4/vector storage by default.
- L3 write path always passes through the validation gate — no direct-write bypass exists.

## Rollback
Each layer module can be disabled independently (feature-flagged) reverting reads to the prior undifferentiated path if it still exists during transition — remove that fallback only after Phase 15.

## Validation Commands
```
pytest backend/tests/memory/ -v
pytest backend/tests/memory/test_isolation.py -v
```
