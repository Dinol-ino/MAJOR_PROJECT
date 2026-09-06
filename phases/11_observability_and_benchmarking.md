# Phase 11 — Observability & Benchmarking

Depends on: Phase 05 (runtime metrics source), Phase 06 (retrieval metrics source), Phase 08 (MCP metrics source), Phase 09 (orchestrator step metrics)
Blocks: Phase 12 (evaluation needs real performance data), later phases' "Performance Requirements" sections that deferred exact numbers to this phase
Modifies: request handling throughout (adds instrumentation)
Introduces: local diagnostics endpoint, correlation IDs, real performance budgets
Validates: budgets are evidence-based, not invented

## Objective
Instrument the system so every previous phase's deferred "measure this, don't assume a number" requirement gets a real answer, and provide a local diagnostics view — no cloud telemetry.

## Current State
Per Phase 00 manifest — likely minimal or absent instrumentation. Prior phases in this roadmap repeatedly deferred concrete latency/resource targets to this phase specifically to avoid inventing numbers.

## Problem
Without real measurement, every performance claim in this project (including report.md's) is unverifiable, and optimization work in later phases would be guesswork.

## Architecture Change

**Metrics tracked** (per request, correlated by request ID):
- API overhead, time-to-first-token, total generation time, retrieval latency (broken down: BM25/dense/PageIndex separately), embedding latency, database latency, MCP latency (per tool call), tool call count, token usage (input/output), cache hit/miss (per cache layer, Phase 04), model load/unload time, CPU/memory/GPU/VRAM usage, failures/retries/timeouts, circuit breaker state changes (Phase 09), security blocks (Phase 07).

**Storage**: local time-series-appropriate store — if PostgreSQL (Phase 02) is sufficient for the expected volume on a single-user local deployment, use it (avoid adding a dedicated metrics DB like Prometheus/InfluxDB unless Phase 02's Postgres proves inadequate under actual load — don't add infrastructure preemptively).

**Diagnostics endpoint**: local-only dashboard (no external exposure) showing current + historical metrics, correlation-ID-based request tracing (full path through Phase 09's orchestrator states, timing per state).

## Files to Add
- `backend/app/observability/metrics.py` — metric collection interface, used by instrumentation points throughout.
- `backend/app/observability/correlation.py` — request ID generation/propagation.
- `backend/app/observability/diagnostics_endpoint.py` — `GET /diagnostics` local dashboard data.
- `backend/app/observability/redaction.py` — ensures logs/metrics never contain raw prompts or legal document content, only structural data (lengths, hashes, categories) — this is not optional given the confidentiality requirement running through the whole project.

## Files to Modify
Every module with a deferred performance requirement in Phases 04–10 — add instrumentation calls at the relevant points.

## Dependencies
Depends on: Phase 05, 06, 08, 09
Blocks: 12, and retroactively informs deferred targets in 04–10
Modifies: instrumentation throughout
Introduces: metrics collection, diagnostics endpoint, correlation IDs
Validates: real performance budgets

## Implementation Steps
1. Implement `correlation.py` first — every request gets an ID at ingress, propagated through all subsequent calls (retrieval, MCP, model inference) so a single request's full timing breakdown is reconstructable.
2. Implement `redaction.py` and apply it at the metrics/logging boundary before anything else logs — verify no raw prompt or document content reaches logs by test, not just by code review.
3. Instrument each phase's request path per the metrics list above.
4. Build `diagnostics_endpoint.py` — local-only, no auth complexity needed beyond confirming it's not exposed externally (bind to localhost or require the same auth as the rest of the API).
5. Run actual benchmarks on real target hardware (the Tier 0 floor machine specifically, per `stages_2/04`) — record real numbers for: cold start, first-token latency per model tier, retrieval latency per path (BM25/dense/PageIndex), concurrent request behavior at 2/5/10 simultaneous requests.
6. **Only after step 5**: write the actual performance budgets that Phases 04–10 deferred, as a `PERFORMANCE_BUDGETS.md` reference document, generated from real numbers.

## Configuration
Metrics retention period, diagnostics endpoint bind address (localhost-only by default) — `settings.py`.

## API Changes
`GET /diagnostics` — dashboard data (latency breakdowns, cache hit rates, resource usage, recent failures).
`GET /diagnostics/trace/{request_id}` — full per-request trace.

## Database Changes
`request_metrics` table (correlation ID, per-stage timings, resource snapshot) — retention-policy-bound (Phase 03's policy pattern), not unbounded growth.

## Security Requirements
No sensitive content (prompts, document text, PII) in logs or metrics — enforced by `redaction.py`, tested explicitly. Diagnostics endpoint not externally reachable in default configuration.

## Performance Requirements
This phase defines the requirements for everything else — instrumentation overhead itself must be low (<5% latency overhead target, verify empirically).

## Testing
- Unit: redaction correctly strips prompt/document content from log output in test fixtures.
- Integration: correlation ID propagates correctly through a full request touching retrieval + MCP + generation.
- Load: benchmark suite runs against Tier 0 hardware, produces the real numbers for `PERFORMANCE_BUDGETS.md`.

## Acceptance Criteria
- Every metric in the tracked list is actually collected and queryable.
- `PERFORMANCE_BUDGETS.md` exists with real, benchmarked numbers — no invented targets remain in any phase file.
- Redaction verified by test to never leak prompt/document content into logs.

## Rollback
Instrumentation is additive and can be disabled via a global flag with zero functional impact on the request path (metrics collection is not on the critical path for correctness).

## Validation Commands
```
pytest backend/tests/observability/ -v
pytest backend/tests/observability/test_redaction.py -v
python -m backend.app.observability.benchmark --tier=0
```
