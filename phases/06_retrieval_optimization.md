# Phase 06 — Retrieval Optimization (ChromaDB + BM25 + RRF + PageIndex)

Depends on: Phase 04 (retrieval caching), Phase 05 (model routing, for any reranking model use)
Blocks: Phase 08 (MCP research tools feed results through this same retrieval quality bar), Phase 10 (current-law research builds on this)
Modifies: existing retrieval module
Introduces: PageIndex fusion strategy, retrieval metrics, incremental BM25/embedding pipeline
Validates: Recall@K/Precision@K/MRR/nDCG measured, not assumed

## Objective
Keep the existing retrieval stack (justified below) and fix its confirmed inefficiencies, formally integrating PageIndex rather than treating it as a bolt-on.

## Current State
Per Phase 00 manifest — confirm PageIndex wiring specifics (which documents, how invoked, how results merge today). Prior audit confirmed BM25 rebuilt per-query and embedding model was a placeholder — verify both against manifest; `stages_2/02` already specifies the InLegalBERT fix, treat as done only if manifest confirms it.

## Problem
Rebuilding BM25 per query and using non-semantic placeholder embeddings both directly degrade retrieval quality and latency — this is likely the single largest contributor to poor "LLM response quality" (item 1 in your original priority list), since generation quality is bounded by what retrieval actually surfaces.

## Architecture Change — ADR: Why Keep This Stack

- **ChromaDB**: no evidence it's insufficient; replacing it would be technology churn without a demonstrated failure mode.
- **BM25**: essential for exact statute/section-number matches that dense embeddings handle poorly — keep.
- **RRF**: standard, cheap, effective fusion method for combining sparse+dense results — no reason to replace.
- **PageIndex** (confirmed integrated): genuinely well-suited here specifically because Indian statutes have real hierarchical structure (Act → Chapter → Section → Sub-section) that a tree-reasoning index can navigate the way a lawyer would — jumping to the right section via structural reasoning rather than pure similarity match. Keep and formalize its role rather than leaving it as an ad hoc addition.

**Fusion strategy:** PageIndex is invoked when a query implies structural/document-internal navigation (e.g. "what does Section 302 IPC say" — a query PageIndex's tree reasoning is well-suited to resolve directly). BM25+dense+RRF handles cross-corpus semantic queries (e.g. "what protections exist for tenants facing eviction" — spans many documents, no single structural anchor). A lightweight routing check (Phase 05's Tier 0 classifier) decides which path a query takes; results can also be combined when a query benefits from both (multi-hop questions).

## Files to Modify
Existing retrieval module (`retrieval.py` or equivalent per manifest), embedding invocation code, BM25 index build code, PageIndex integration point.

## Files to Add
- `backend/app/retrieval/fusion_router.py` — decides PageIndex vs hybrid-search vs both per query.
- `backend/app/retrieval/bm25_index.py` — persistent, incrementally updated index (replaces rebuild-per-query).
- `backend/app/retrieval/metrics.py` — Recall@K, Precision@K, MRR, nDCG, citation hit rate computation for eval (Phase 12).

## Dependencies
Depends on: Phase 04, 05
Blocks: 08, 10
Modifies: retrieval module
Introduces: fusion router, persistent BM25 index
Validates: retrieval metrics feed Phase 12

## Implementation Steps
1. Confirm InLegalBERT is actually producing stored embeddings (Phase 00 manifest) — if not, this is the highest-priority fix in this phase, re-embed the full corpus once confirmed.
2. Build persistent BM25 index: on corpus write (Stage 2/`stages_2` ingestion), update incrementally; on query, load from persisted state — never rebuild from scratch per query.
3. Implement `fusion_router.py`'s classification step (Tier 0 model or deterministic heuristic — e.g. presence of a section-number pattern in the query strongly suggests PageIndex path; try deterministic first per the project's own "deterministic before LLM" principle, only escalate to a model classifier if heuristics prove insufficient).
4. Wire result caching (Phase 04's L2) keyed on query + corpus version + retrieval params.
5. Implement metadata filtering: exclude `superseded_by`-flagged documents by default (per `stages_2/02`'s corpus schema), enforce jurisdiction filtering.
6. Implement reranking only if evidence from Phase 12 eval shows RRF fusion alone is insufficient — don't add a reranking model preemptively without measured need.
7. Deduplicate near-identical chunks in results before passing to context assembly (common when the same provision appears in both a bare act and an amendment referencing it).

## Configuration
Top-k per retrieval path, RRF weighting, PageIndex-vs-hybrid routing threshold, dedup similarity threshold — all in `settings.py`.

## API Changes
None new user-facing; internal retrieval interface returns richer metadata (which path — PageIndex/hybrid/both — produced each result, for observability).

## Database Changes
None beyond what `stages_2/02`'s corpus metadata schema already specifies (verify it's actually implemented per manifest).

## Security Requirements
Retrieved content remains untrusted at this layer already (enforced downstream in Phase 07's context sanitization) — this phase's responsibility is quality/correctness, not sanitization, but must not weaken that boundary (e.g. don't let PageIndex's tree-reasoning step execute anything from document content as instructions during index navigation).

## Performance Requirements
BM25 query-time cost should drop to near-zero rebuild overhead (measure before/after). Retrieval latency budget set after Phase 11 benchmarking — not invented here.

## Testing
- Retrieval quality: Recall@K/Precision@K/MRR/nDCG against the curated test set (`stages_2/07`'s legal-accuracy set, extended).
- Regression: exact section-number queries and natural-language paraphrase queries of the same provision both retrieve correctly.
- Superseded-provision exclusion test (from `stages_2/02`).

## Acceptance Criteria
- BM25 index is not rebuilt per query (verified by profiling).
- InLegalBERT (not placeholder) confirmed producing all stored embeddings.
- PageIndex fusion routing measurably improves structural-query accuracy over hybrid-only baseline (A/B against Phase 12 eval set).
- Retrieval metrics are computed and tracked, not just claimed.

## Rollback
Fusion router can be disabled via config flag, falling back to hybrid-only (BM25+dense+RRF) retrieval — isolates whether an issue originates in PageIndex integration specifically.

## Validation Commands
```
pytest backend/tests/retrieval/ -v
python -m backend.app.retrieval.metrics --benchmark
```
