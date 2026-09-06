# Phase 04 — Performance & Caching Architecture

Depends on: Phase 02 (stable persistence to cache in front of), Phase 03 (conversation memory read path benefits from caching)
Blocks: Phase 05 (model routing benefits from prompt/response caching), Phase 06 (retrieval caching)
Modifies: retrieval and generation request paths
Introduces: L1–L3 caching only (L4/L5 explicitly evaluated and rejected below unless evidence says otherwise)
Validates: cache hit rate, no cross-session cache leakage

## Objective
Add a caching strategy that measurably reduces latency/resource use on a local single-machine deployment, without adding layers that don't earn their complexity.

## Current State
Per Phase 00 manifest — prior audit confirmed BM25 was rebuilt per-query (no caching at all in retrieval). Response/prompt caching status unknown, verify.

## Problem
No caching means repeated identical or near-identical queries redo full retrieval + generation work every time — wasted latency and resource consumption on hardware that's already constrained (3–15B local models).

## Architecture Change

Evaluate all 5 proposed layers against this project's actual constraints, don't implement all 5 by default:

| Layer | Decision | Reasoning |
|---|---|---|
| L1 in-process cache | **Implement** | Near-zero cost, catches exact-duplicate requests within a session (e.g. UI double-submit) |
| L2 retrieval cache | **Implement** | BM25/vector/PageIndex retrieval is the most expensive pre-generation step; caching by normalized-query+corpus-version hash directly fixes the confirmed per-query-rebuild problem |
| L3 embedding cache | **Implement** | Embedding the same query text repeatedly (common in multi-turn refinement) is pure waste; cache by text hash |
| L4 model/prompt cache | **Reject by default** | Ollama already handles KV-cache/context reuse internally for a loaded model; a second application-level prompt cache adds complexity without clear evidence of benefit on a single local model instance — revisit only if profiling (Phase 11) shows prompt-processing time as a bottleneck independent of Ollama's own caching |
| L5 response cache | **Reject by default** | Legal answers are query+context+conversation-state dependent; caching full responses risks serving stale or wrong-context answers, and given local single-user usage the hit rate is unlikely to justify the staleness risk — revisit only with evidence of repeated identical full-conversation-state queries |

## Files to Add
- `backend/app/cache/base.py` — shared cache interface (get/set/invalidate, TTL, max size).
- `backend/app/cache/l1_process_cache.py`
- `backend/app/cache/l2_retrieval_cache.py`
- `backend/app/cache/l3_embedding_cache.py`
- `backend/app/cache/keys.py` — key construction utilities, enforcing the required context in every key (see below).

## Files to Modify
Retrieval module (Phase 06 dependency — wire cache lookups in), embedding invocation points.

## Dependencies
Depends on: Phase 02, 03
Blocks: 05, 06
Modifies: retrieval/embedding call sites
Introduces: L1–L3 caching
Validates: Phase 11's cache hit-rate metric

## Implementation Steps
1. Define cache key convention: **must include** session/user identity (where result is user-scoped), document/corpus version hash (so a corpus update invalidates stale cached retrieval — ties to `stages_2/02`'s corpus versioning), model/embedding-model version (so swapping InLegalBERT versions doesn't serve stale vectors).
2. Implement L1 as a simple bounded in-process dict/LRU, request-scoped or short-TTL — no persistence, no cross-process sharing needed for a local single-instance app.
3. Implement L2 keyed on normalized query text + corpus version + retrieval params (top-k, filters) — invalidated automatically when corpus version changes (Phase 06/Stage 2 re-ingestion writes a new version hash).
4. Implement L3 keyed on exact text hash — safe to cache aggressively since embeddings are deterministic per model version.
5. Never cache anything from L3 (semantic memory) or L5 (research memory) results globally across users — cache keys must be session/user-scoped wherever the underlying data is.

## Configuration
Per-cache TTL, max size (item count or memory bound), enable/disable flags — all in `settings.py`. Defaults should be conservative for the Tier 0 hardware floor (small max size) with room to increase on higher tiers (ties to Phase 05 hardware detection).

## API Changes
None user-facing. Internal: retrieval/embedding call sites now check cache before computing.

## Database Changes
None — these caches are in-process/in-memory, not persisted stores. If Redis is already present (per `stages_2` memory architecture, used for L2 conversation memory), L2/L3 caches may optionally use it for cross-request persistence within a session, but this is not required.

## Security Requirements
Cache keys must never allow one user's cached result to be served to another — enforced by construction (identity always part of the key where relevant), verified by test, not just by convention.

## Performance Requirements
Retrieval cache hit should eliminate BM25/vector/PageIndex computation entirely for a hit — measure actual latency delta, target documented in Phase 11 after real benchmarking (don't invent a number now).

## Testing
- Unit: cache key construction includes required scoping fields.
- Integration: corpus version bump invalidates stale L2 entries.
- Security: cross-user cache isolation test.

## Acceptance Criteria
- L1–L3 implemented and wired into retrieval/embedding paths.
- L4/L5 explicitly not implemented, with this decision documented (not silently skipped).
- Cache hit rate is observable (feeds Phase 11).
- No cross-session/cross-user cache leakage under test.

## Rollback
Each cache layer is a wrapper around the existing uncached call — disable via config flag to bypass and hit the underlying computation directly, no data migration needed to roll back.

## Validation Commands
```
pytest backend/tests/cache/ -v
pytest backend/tests/cache/test_isolation.py -v
```
