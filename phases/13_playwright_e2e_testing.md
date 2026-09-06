# Phase 13 — Playwright E2E Testing (Frontend Only)

Depends on: Phase 12 (sits alongside as the frontend eval category)
Blocks: Phase 15 (final regression includes this suite)
Modifies: nothing in runtime architecture — this phase is explicitly scoped to test infrastructure only
Introduces: E2E browser test suite
Validates: critical user-facing flows work end-to-end

## Objective
Add Playwright as an automated browser-testing layer for the frontend — explicitly not a runtime component, per the scope boundary already established.

## Current State
Per Phase 00 manifest — confirm whether Playwright is currently used anywhere in the runtime path (e.g. misused for corpus scraping at request time, which would be a scope violation) versus only as a dev dependency, if used at all.

## Problem
No automated frontend regression coverage means UI-breaking changes (streaming, mode indicators, citation rendering) ship undetected.

## Architecture Change
Playwright added as a dev/test dependency only. If Phase 00 finds it wired into any runtime path, that's flagged as a violation to fix in this phase (move to test-only), not a reason to keep it there.

**Critical flows to cover:**
- Chat streaming (tokens appear incrementally, not just final response).
- Upload workflow (document ingestion, including a malicious-PDF test case using a sanitization-triggering fixture).
- Citation rendering (citations visible, clickable/expandable, correctly attributed).
- Shield/security behavior (a crafted injection attempt in the UI shows the correct refusal, not a silent failure).
- MCP mode switching (OFFLINE/ONLINE toggle, Phase 10's mode visibility requirement).
- Offline mode (attempt an online-requiring query while offline, confirm correct UI messaging, no silent network call).
- Online mode (when enabled, confirm source attribution renders per Phase 10's provenance requirement).
- Error states (model load failure, retrieval failure, MCP timeout — each should show a clear, non-alarming message, not a raw stack trace).
- Accessibility (keyboard navigation, screen-reader labels on key interactive elements — baseline coverage, not exhaustive WCAG audit).

## Files to Add
- `frontend/e2e/chat_streaming.spec.ts`
- `frontend/e2e/upload_workflow.spec.ts`
- `frontend/e2e/citation_rendering.spec.ts`
- `frontend/e2e/shield_behavior.spec.ts`
- `frontend/e2e/mcp_mode_switching.spec.ts`
- `frontend/e2e/error_states.spec.ts`
- `frontend/e2e/accessibility.spec.ts`
- `frontend/playwright.config.ts`

## Dependencies
Depends on: Phase 12
Blocks: 15
Modifies: nothing in `backend/`
Introduces: `frontend/e2e/`
Validates: Phase 15's final regression, Phase 16's release gate frontend criteria

## Implementation Steps
1. Confirm (Phase 00 manifest) whether Playwright is already a dependency anywhere; if it's runtime-wired, relocate that usage out of the request path first (flag as a Phase 07/08 scope issue if found there, not silently left).
2. Install as a dev dependency (`npm install -D @playwright/test`, `playwright install chromium` per `stages_2/09`'s prerequisite note — same browser binary requirement applies here).
3. Write the critical-flow specs above against the running dev server (local, no external dependency).
4. Wire into CI alongside Phase 12's backend eval suite.

## Configuration
`playwright.config.ts` — base URL (local dev server), timeout, retry policy for flaky-prone tests (streaming/network-dependent tests get slightly more retry tolerance than pure UI tests).

## API Changes
None.

## Database Changes
None — E2E tests should use a disposable/seeded test database, never point at real user data.

## Security Requirements
E2E test fixtures (the malicious-PDF test case, injection-attempt test case) must be clearly marked as test-only artifacts, not accidentally left in a location the real ingestion pipeline would pick up.

## Performance Requirements
E2E suite runtime kept practical for CI — parallelize independent specs, don't let this become the bottleneck in the CI pipeline.

## Testing
This phase's tests are the deliverable; meta-test: confirm each spec actually fails when the corresponding feature is deliberately broken (same mutation-testing principle as Phase 12).

## Acceptance Criteria
- All critical flows listed above have passing E2E coverage.
- Playwright confirmed not used anywhere in the runtime request path.
- CI runs the suite on every frontend-touching PR.

## Rollback
E2E suite is purely additive test infrastructure — no rollback risk to the application itself; a flaky/broken spec can be temporarily skipped in CI with an explicit tracked issue, not silently ignored.

## Validation Commands
```
npx playwright test
npx playwright test --reporter=list
```
