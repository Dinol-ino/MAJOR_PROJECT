# Phase 10 — Online/Offline Legal Research & Current-Law Handling

Depends on: Phase 08 (MCP gateway), Phase 09 (bounded orchestrator hosts this pipeline)
Blocks: Phase 12 (research/freshness eval categories), Phase 14 (UI must surface mode + provenance)
Modifies: existing corpus/retrieval freshness handling (largely absent per prior audit — this phase builds it)
Introduces: OFFLINE/ONLINE mode boundary, freshness detection, bounded research pipeline, provenance schema
Validates: offline network isolation, no fabricated sources, correct current-vs-static distinction

## Objective
Give DFrag an explicit answer to "is this law still current" — distinguishing static indexed knowledge from information that may have changed since indexing, with a hard-enforced offline/online boundary.

## Current State
Per Phase 00 manifest — this capability almost certainly does not exist yet in any form; the original project state (per memory) had no mechanism to detect staleness or perform online research at all. Treat as new build, not hardening, unless manifest says otherwise.

## Problem
A legal RAG system that can't distinguish "this is what the indexed corpus says" from "this may have been amended since" risks confidently presenting stale law as current — one of the most serious failure modes for a legal tool.

## Architecture Change

**Hard mode boundary:**
```
OFFLINE (default): no internet, no external MCP, no remote API, no telemetry — verified by network policy, not just absence of code paths.
ONLINE (opt-in, explicit): allowlisted domains only (legal_sources.yaml, Phase 01), TLS validated, rate-limited, timeouts enforced, all content sanitized (Phase 07) before reaching the LLM, full provenance logged.
```
Mode is always visible to the user (frontend, Phase 14) and never switches silently — a query requiring current information while in OFFLINE mode gets an explicit "this may be outdated, enable online mode for current information" response, never a silent online call.

**Research pipeline** (runs inside Phase 09's orchestrator, RETRIEVE/TOOL CALL states):
```
Question → Freshness Detection → Research Plan → Authoritative Source Search (Phase 08's CURRENT_LAW/CASE_LAW_SEARCH/GOVERNMENT_SOURCE categories)
→ Source Validation → Document Extraction → Evidence Ranking → Conflict Detection
→ Citation Construction → Legal Synthesis → Verification (Phase 07's output validator)
```

**Freshness detection**: heuristic + corpus metadata check — if the query concerns a provision whose `last_verified_at` (per `stages_2/02` schema) is older than a configurable staleness threshold, or the query explicitly asks about "current"/"latest"/"recent" status, flag freshness-required. Prefer deterministic heuristics first (keyword/date-based), escalate to a lightweight model classifier only if ambiguous (consistent with Phase 05's deterministic-first principle).

**Provenance schema** (per evidence object, exactly as specified):
```
source_id, source_type, source_title, source_url, jurisdiction, act, section,
document_version, publication_date, retrieval_timestamp, content_hash, trust_level, retrieval_method
```
No evidence object is usable in synthesis without this schema populated — the model never fabricates a citation without a backing evidence object carrying this provenance.

## Files to Add
- `backend/app/research/freshness.py`
- `backend/app/research/pipeline.py` — the 10-step pipeline above.
- `backend/app/research/source_validator.py` — confirms a fetched source matches an allowlisted domain and expected content type before extraction proceeds.
- `backend/app/research/conflict_detector.py` — flags when online-retrieved content contradicts local corpus content (e.g. corpus shows a provision as current, online source shows it repealed) — surfaces the conflict rather than silently picking one.
- `backend/app/network/mode_enforcer.py` — the actual network policy boundary; all outbound calls in the codebase must route through this, which checks current mode before permitting any request.

## Files to Modify
Phase 08's gateway (wires CURRENT_LAW/CASE_LAW_SEARCH/GOVERNMENT_SOURCE categories to this pipeline).

## Dependencies
Depends on: Phase 08, 09
Blocks: 12, 14
Modifies: MCP gateway wiring
Introduces: mode enforcer, research pipeline, provenance schema
Validates: Phase 12's research/freshness eval category

## Implementation Steps
1. Implement `mode_enforcer.py` first — this is the actual security boundary, must exist and be verifiably enforced (e.g. attempt an outbound call in OFFLINE mode in a test, confirm it's blocked at this layer, not just "there's no code path that calls out") before building the research pipeline on top of it.
2. Implement `freshness.py` heuristics against corpus metadata (`stages_2/02` schema) and query text patterns.
3. Implement the pipeline stages in order, each stage bounded by Phase 09's ceilings (max sources, max depth, max time, max tool calls, max tokens) — research stops once sufficient evidence is gathered, not exhaustively.
4. Implement `source_validator.py`: every fetched document checked against `legal_sources.yaml` allowlist before extraction; reject anything not on the list, don't attempt best-effort extraction from unlisted sources.
5. Implement `conflict_detector.py`: compares online evidence against local corpus for the same provision (by act/section match); if conflicting, both are surfaced with provenance rather than one silently overriding the other — this is a case for LLM synthesis to explain, not for the pipeline to resolve unilaterally.
6. Wire provenance capture at every extraction point — no evidence object skips required fields; incomplete provenance = evidence discarded, not used with gaps.

## Configuration
`legal_sources.yaml` (allowlisted domains), staleness threshold, max research pipeline sources/depth/time (Phase 09 ceilings, research-specific values), `NETWORK_MODE` (OFFLINE default).

## API Changes
- `GET /system/mode` — current OFFLINE/ONLINE status (frontend polls or subscribes to this).
- `POST /system/mode` — explicit user action to enable ONLINE mode (never automatic).
- Research results include `mode_used`, freshness flag, and full provenance per citation.

## Database Changes
Extends L5 research memory (Phase 03) with the provenance schema fields; `conflict_flags` table or column for detected online-vs-local conflicts.

## Security Requirements
This phase is where SSRF risk concentrates (online mode fetches external URLs) — `source_validator.py`'s allowlist check is the primary control, TLS validation and timeout enforcement are secondary controls, all mandatory. Tool-result content is untrusted (Phase 07's sanitizer applies here specifically). Network activity logged (L6 audit) regardless of mode, so OFFLINE mode's "zero network calls" guarantee is independently auditable, not just asserted.

## Performance Requirements
Research pipeline latency is inherently higher than local-only retrieval (external network round-trips) — bounded by Phase 09's ceilings so worst case is predictable; measure actual latency in Phase 11, surface to user as expected (e.g. a progress indicator) rather than a silent long wait.

## Testing
- Security: OFFLINE mode network-isolation test — attempt any outbound call, confirm block at `mode_enforcer.py`.
- Security: source validator rejects a non-allowlisted domain even if the LLM's tool-call request names it.
- Integration: conflict detector correctly surfaces a deliberately-conflicting test fixture (local corpus says X, mock online source says not-X) without silently picking one.
- Provenance: every evidence object used in a synthesized answer has complete provenance fields, verified by test.

## Acceptance Criteria
- OFFLINE mode provably makes zero network calls (verified by network-level test, not code review alone).
- ONLINE mode only ever fetches allowlisted domains.
- No synthesized answer cites a source lacking full provenance.
- Mode is always visible and never switches without explicit user action.

## Rollback
ONLINE mode can be globally disabled via config, collapsing the system to offline-only behavior (Phase 06's local retrieval) with zero functional loss to the offline path — this phase is purely additive to what exists.

## Validation Commands
```
pytest backend/tests/research/ -v
pytest backend/tests/network/test_offline_isolation.py -v
pytest backend/tests/research/test_provenance_completeness.py -v
```
