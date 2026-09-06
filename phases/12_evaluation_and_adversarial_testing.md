# Phase 12 — Evaluation & Adversarial Testing (Extended)

Depends on: Phase 07 (security), Phase 08 (MCP), Phase 10 (research), Phase 11 (real performance data)
Blocks: Phase 15 (final regression depends on this suite existing and passing)
Modifies: existing eval harness (`stages_2/07`'s RAGAS-based harness — extend, don't replace)
Introduces: security, memory, and MCP eval categories on top of the existing retrieval/generation categories
Validates: everything — this is the project's regression backbone

## Objective
Extend the existing RAGAS-based eval harness (`stages_2/07`) into full coverage across security, retrieval, generation, memory, MCP, and performance — running continuously, not as a one-time gate.

## Current State
Per Phase 00 manifest — `stages_2/07` already specified RAGAS + adversarial suite; confirm whether it's actually running in CI or was only ever specified. Report.md's "tests currently reported as passing" needs its own verification here specifically — what tests, covering what, actually run.

## Problem
An eval harness that only covers retrieval/generation misses exactly the categories this phase set introduces (security hard-gate behavior, MCP authorization, memory isolation, offline enforcement) — without eval coverage, regressions in those areas ship silently.

## Architecture Change

**Security eval**: injection/jailbreak pattern suite (Phase 07), indirect injection via crafted retrieved/MCP content, PII leakage detection, tool poisoning attempts (Phase 08) — pass/fail against the hard-gate behavior specifically (not "usually blocks," must always block for the defined test set).

**Retrieval eval**: Recall@K, Precision@K, MRR, nDCG (Phase 06), citation hit rate, retrieval latency — tracked as trends, not just pass/fail.

**Generation eval**: faithfulness, citation correctness + completeness, hallucination rate, answer relevance (RAGAS, local-judge-configured per `stages_2/03`).

**Memory eval** (new): memory retrieval accuracy (L2/L3 correct recall), session isolation (Phase 03's cross-user test, run here as a standing regression case), deletion correctness (L3/L4 delete actually removes data from all stores), stale-memory behavior (does the system correctly avoid treating old L2 context as current fact when contradicted by fresh retrieval).

**MCP eval** (new): unauthorized tool call rejection (Phase 08), malicious tool result handling (sanitizer effectiveness), timeout behavior, offline enforcement (Phase 10's network isolation, tested here as a standing regression case, not just once in Phase 10).

**Performance eval**: latency/throughput/memory/CPU-GPU utilization/cache hit rate, against the real budgets Phase 11 established.

**Frontend**: Playwright critical-flow suite (Phase 13) referenced here as the frontend eval category, not duplicated.

## Files to Modify
`stages_2/07`'s existing harness code — extend with new test categories, don't rewrite what's working.

## Files to Add
- `backend/tests/eval/security_suite.py`
- `backend/tests/eval/memory_suite.py`
- `backend/tests/eval/mcp_suite.py`
- `backend/tests/eval/legal_accuracy_set/` — the curated question/citation test set from `stages_2/03`, extended with cases specific to the new research pipeline (freshness-required questions, conflict-detection cases).

## Dependencies
Depends on: Phase 07, 08, 10, 11
Blocks: 15
Modifies: existing eval harness
Introduces: security/memory/MCP eval categories
Validates: the entire system, continuously

## Implementation Steps
1. Confirm `stages_2/07`'s harness is actually wired into CI (Phase 00 manifest) — if it exists only as a spec, implement it now as the foundation before extending.
2. Add security suite: run Phase 07's adversarial test cases as an automated regression set, not manual spot-checks.
3. Add memory suite: automate the isolation/deletion/staleness tests specified in Phase 03 as standing regression cases.
4. Add MCP suite: automate Phase 08's unauthorized-call and malicious-result tests, and Phase 10's offline-isolation test, as standing regression cases (they were written once per-phase — this is where they become permanent).
5. Extend the legal-accuracy test set with freshness/conflict cases from Phase 10.
6. Wire all suites to run on every PR touching the relevant subsystem, with trend tracking (not just latest-run pass/fail) per `stages_2/07`'s original design.

## Configuration
Judge model (local Ollama, per `stages_2/03`), eval suite trigger scope per changed files, trend-tracking retention.

## API Changes
None — this is a dev/CI harness, not a runtime component.

## Database Changes
`eval_runs` table — historical trend data (score per category per run, git commit reference).

## Security Requirements
Eval judge and any eval-time model calls remain local (per `stages_2/03`'s existing requirement) — no exception introduced by the new categories, since memory/MCP eval fixtures may include realistic-looking legal document content that shouldn't leave the machine either.

## Performance Requirements
Full suite runtime should stay practical for CI (target set after Phase 11 gives real per-test timing data — if the full suite becomes too slow, split into fast-path-per-PR and full-nightly, don't just let it grow unbounded).

## Testing
This phase *is* testing infrastructure — its own "testing" is: does the harness correctly fail when a known-bad fixture is introduced (mutation testing the eval suite itself — deliberately break the hard gate in a test branch, confirm the security suite catches it).

## Acceptance Criteria
- All six eval categories implemented and running in CI.
- Trend data available across at least the categories touched by Phases 07–11's changes.
- Mutation test confirms the security/memory/MCP suites actually catch deliberately introduced regressions, not just passing vacuously.

## Rollback
Individual suite categories can be disabled via CI config if a specific suite proves flaky, but this should be treated as a bug to fix, not a permanent state — track disabled suites explicitly, don't let them silently stay off.

## Validation Commands
```
pytest backend/tests/eval/ -v --tb=short
python -m backend.tests.eval.mutation_check
```
