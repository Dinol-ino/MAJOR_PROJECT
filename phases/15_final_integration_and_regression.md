# Phase 15 — Final Integration & Regression

Depends on: Phases 00–14, all complete
Blocks: Phase 16 (release gate)
Modifies: nothing new — this phase is verification only
Introduces: nothing new
Validates: the complete system, end-to-end, against every acceptance criterion from every prior phase

## Objective
Confirm the whole system works together — no duplicate subsystems, no dead routes, no phase's fix was silently undone by a later phase.

## Current State
All prior phases' acceptance criteria individually met (precondition for entering this phase, not something this phase establishes).

## Problem
Phases were built sequentially; integration bugs (a later phase's change breaking an earlier phase's guarantee) are only caught by testing the whole system together, not by any single phase's isolated tests.

## Architecture Change
None — this phase is audit and regression only.

## Files to Modify
None expected — if this phase finds a genuine integration bug, the fix belongs in the owning phase's files, tracked as a regression against that phase's acceptance criteria, not patched ad hoc here.

## Dependencies
Depends on: 00–14
Blocks: 16
Modifies: (regressions only, attributed to owning phase)
Introduces: nothing
Validates: entire system

## Implementation Steps
1. Re-run every phase's validation commands (00 through 14) against the final integrated state — not just each phase's own isolated test run at the time it was built.
2. Search the codebase for duplicate subsystems: confirm no old additive-injection-scoring code remains alongside the Phase 07 hard gate, no old undifferentiated memory table remains alongside Phase 03's layered model, no direct-dispatch MCP path remains alongside Phase 08's gateway.
3. Search for dead routes: any API endpoint not reachable from the current frontend, or superseded by a later phase's endpoint, removed or explicitly justified as still-needed.
4. Search for fake/decorative UI: any button or view (e.g. the original "MCP tools view") that doesn't actually call real backend logic — per Phase 00's manifest findings, confirm every such element identified there is now wired to real functionality, per Phase 08/14.
5. Confirm no untested critical path: cross-reference Phase 12/13's coverage against the full request-handling flow (Phase 09's state machine) — every state should have both unit and at least one E2E-relevant test.
6. Confirm no uncontrolled agent loop is reachable: attempt to construct a request that would exceed Phase 09's ceilings, confirm it's bounded in the integrated system, not just in Phase 09's isolated tests.
7. Confirm no unrestricted tool access: attempt an out-of-policy tool call in the integrated system (not just Phase 08's isolated test).
8. Confirm no hidden network calls: run the full test suite with network access blocked except for the explicit allowlist test cases in Phase 10 — anything else attempting network access fails loudly.
9. Confirm no cloud dependency for core operation: run the full offline-mode flow (chat, retrieval, memory, citations) with network fully disabled at the OS/firewall level, not just application-config OFFLINE mode — this is a stronger test than Phase 10's own isolation test and should be run here as the final word on the "local-first" guarantee.

## Configuration
None new.

## API Changes
None new — audit only.

## Database Changes
None new — if migrations from different phases conflict (e.g. two phases both add a column with the same name to different intended purposes), resolve here and treat as a regression against whichever phase's schema was authoritative.

## Security Requirements
Full security suite (Phase 07/12) re-run against integrated system; specifically re-verify the hard gate, audit ledger integrity, and cross-user isolation together (a bug in how memory isolation interacts with MCP request context, for example, wouldn't necessarily be caught by either phase's isolated tests).

## Performance Requirements
Full benchmark suite (Phase 11) re-run against integrated system; confirm no phase's addition silently regressed another phase's latency budget (e.g. Phase 10's research pipeline adding overhead to the simple local-only path, which should not happen given the freshness-detection gate).

## Testing
This entire phase is testing — see Implementation Steps.

## Acceptance Criteria
- Every phase's own acceptance criteria still hold in the integrated system.
- Zero duplicate subsystems found.
- Zero dead/decorative routes or UI elements found.
- Offline mode verified at the OS/firewall level, not just application config.
- Full security and performance suites pass against the integrated system.

## Rollback
This phase produces a go/no-go signal for Phase 16 — if it fails, the specific owning phase is reopened for a fix, not this phase itself.

## Validation Commands
```
pytest backend/tests/ -v
npx playwright test
python -m backend.app.observability.benchmark --tier=0 --full
# OS-level network block, then:
pytest backend/tests/research/test_provenance_completeness.py backend/tests/network/test_offline_isolation.py -v
```
