# Phase 14 — Frontend Performance & Consensus-Inspired UX (Incremental)

Depends on: Phase 10 (mode/provenance data must exist before UI can surface it), Phase 11 (streaming/latency instrumentation informs perceived-performance work)
Blocks: Phase 15
Modifies: existing frontend (per Phase 00 manifest — "mixed" Consensus UI claim resolved here)
Introduces: incremental UX improvements only where the audit shows a real gap
Validates: Playwright suite (Phase 13) continues passing after changes

## Objective
Extend whatever Consensus-inspired redesign already exists, rather than assuming it's complete (per report.md) or absent — resolved by Phase 00's manifest, addressed here.

## Current State
Per Phase 00 manifest — this claim was specifically called "mixed," meaning some Consensus-derived UI elements likely exist. This phase's first implementation step is enumerating exactly which principles are already reflected in the UI and which aren't, using the six principles from the original spec as a checklist:

- Research-first interaction
- Source-oriented answers
- Citation visibility
- Evidence-backed results
- Progressive disclosure
- Confidence/transparency
- Fast perceived performance

## Problem
Building new UI for principles already implemented would be wasted, duplicate work; skipping principles that aren't implemented leaves the UX gap the redesign was meant to close.

## Architecture Change
No wholesale redesign. Per-principle gap analysis, then targeted additions:

- If citation visibility exists but doesn't show provenance (Phase 10's schema — jurisdiction, effective date, superseded status), extend the existing citation component rather than replacing it.
- If mode visibility (OFFLINE/ONLINE, Phase 10) doesn't exist in the UI at all, add it — this is a hard requirement from Phase 10, not optional polish.
- If streaming exists but perceived performance is still poor, investigate specific causes (Phase 11 instrumentation: is TTFT actually slow, or is it a rendering/reflow issue) before assuming a UI rewrite is needed.
- If progressive disclosure (e.g. expandable evidence/citation detail) doesn't exist, add it as a targeted component, not a page redesign.

## Files to Modify
Existing frontend components per manifest's gap analysis — exact list depends on findings, not enumerated speculatively here.

## Files to Add
- `frontend/src/components/ModeIndicator.tsx` (if Phase 00 confirms this doesn't exist) — surfaces OFFLINE/ONLINE state (Phase 10), required, not optional.
- `frontend/src/components/ProvenancePanel.tsx` (if citation display lacks full provenance fields) — jurisdiction/effective-date/superseded-status/source-trust-level display.
- `frontend/src/components/ConfidenceIndicator.tsx` (if confidence/transparency principle isn't yet reflected) — surfaces the `confidence` field from Phase 07's output schema.

## Dependencies
Depends on: Phase 10, 11
Blocks: 15
Modifies: existing frontend components (per gap analysis)
Introduces: only the components confirmed missing by the gap analysis
Validates: Phase 13's E2E suite

## Implementation Steps
1. Run the 7-principle gap analysis against the actual current frontend (Phase 00 manifest evidence + direct inspection of frontend component tree).
2. Prioritize the two hard requirements first regardless of "nice to have" status: mode visibility (Phase 10 mandates this be always visible) and full citation provenance (Phase 10 mandates citations carry complete provenance — if the UI truncates or omits fields, that's a compliance gap, not a style choice).
3. Address perceived-performance issues only with Phase 11 data in hand — e.g. if TTFT is actually fast but the UI waits for a full response before rendering anything, that's a frontend streaming-consumption bug, not a backend latency problem, and should be fixed as such.
4. Add progressive disclosure/confidence indicators as incremental additions to existing layout, not a rebuild.
5. Re-run Phase 13's Playwright suite after each change — no regression in existing critical flows.

## Configuration
None new — frontend reads mode/provenance/confidence directly from API responses (Phase 07/10's schemas), no separate frontend config needed.

## API Changes
None — consumes existing Phase 07/10 response schemas; if any required field is currently missing from an API response the frontend needs, that's flagged back to the relevant phase, not patched around in the frontend.

## Database Changes
None.

## Security Requirements
No new attack surface — frontend must not render tool-result or retrieved content as executable (e.g. no `dangerouslySetInnerHTML` on retrieved/generated text without sanitization) — verify existing rendering approach, tighten if the manifest shows raw HTML injection risk in citation/answer rendering.

## Performance Requirements
Perceived performance improvements validated against Phase 11's real TTFT/streaming data, not assumed from UI changes alone.

## Testing
Extend Phase 13's Playwright specs to cover the new/modified components (`ModeIndicator`, `ProvenancePanel`, `ConfidenceIndicator`) explicitly.

## Acceptance Criteria
- Mode is visibly and always shown in the UI.
- Citations display full provenance per Phase 10's schema.
- No Playwright regression introduced by this phase's changes.
- Gap analysis document exists, showing which of the 7 principles were already present vs newly added.

## Rollback
Component-level changes are independently revertable (each new component is additive, existing components are modified incrementally with git history as the rollback path) — no phase-wide rollback mechanism needed beyond normal version control.

## Validation Commands
```
npm run build
npx playwright test frontend/e2e/citation_rendering.spec.ts frontend/e2e/mcp_mode_switching.spec.ts
```
