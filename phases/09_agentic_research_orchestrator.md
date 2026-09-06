# Phase 09 — Bounded Agentic Research Orchestrator

Depends on: Phase 07 (security check step), Phase 08 (tool calls go through MCP gateway)
Blocks: Phase 10 (online/offline research pipeline runs inside this orchestrator's RETRIEVE/TOOL CALL steps)
Modifies: existing chat/query handling flow
Introduces: bounded state machine, execution ceilings, circuit breaker
Validates: no infinite loops, no unrestricted tool/network/filesystem/shell access

## Objective
Wrap query handling in a bounded state machine so multi-step research (retrieval + optional tool calls + synthesis) has hard limits, not open-ended agent autonomy.

## Current State
Per Phase 00 manifest — likely a direct request→retrieve→generate flow today, without explicit step/tool/token/time ceilings. Confirm whether any existing "agentic" behavior already exists that this phase needs to bound rather than build fresh.

## Problem
An unbounded agent loop is both a reliability risk (can hang/loop) and a security risk (uncontrolled recursive tool calls, unbounded resource consumption) — explicitly called out as unacceptable for this project.

## Architecture Change

```
REQUEST → CLASSIFY → SECURITY CHECK (Phase 07) → PLAN → RETRIEVE (Phase 06)
→ OPTIONAL TOOL CALL (Phase 08, bounded) → EVIDENCE VALIDATION → SYNTHESIS
→ LEGAL/CITATION VERIFICATION (Phase 07's output validator) → OUTPUT
```

Implemented as an explicit state machine, not an LLM-driven free-form loop — each transition is code-controlled, the LLM produces content within a state, it does not decide the state machine's next state via free text parsing alone (use structured output, per Phase 01's system prompt requiring schema-conformant responses, to determine e.g. "requests a tool call" vs "ready to synthesize").

**Hard ceilings** (config-driven, `settings.py`):
- Max steps per request (e.g. 8 — actual number tuned empirically, not invented here)
- Max tool calls per request
- Max tokens (input + output combined budget)
- Max execution time (wall clock, triggers cancellation)
- Max retrieved documents
- Max network requests (only relevant when Phase 10's online mode is active)
- Retry budget (bounded retries on transient failure, not infinite)
- Circuit breaker: N consecutive failures of a given step type within a time window → that step type is temporarily disabled, surfaced to user/logs

## Files to Add
- `backend/app/orchestrator/state_machine.py` — the bounded workflow itself.
- `backend/app/orchestrator/limits.py` — ceiling enforcement, reads config, raises a typed `LimitExceeded` exception when hit (never silently truncates without logging).
- `backend/app/orchestrator/circuit_breaker.py`
- `backend/app/orchestrator/cancellation.py` — user-initiated or timeout-initiated cancellation, ensures partial state is cleaned up (no orphaned tool calls or half-written memory).

## Files to Modify
Existing chat/query request handler — becomes the entry point into this state machine rather than a direct retrieve-then-generate call.

## Dependencies
Depends on: Phase 07, 08
Blocks: 10
Modifies: chat request handler
Introduces: bounded state machine, execution limits, circuit breaker
Validates: Phase 12's MCP/agentic eval categories

## Implementation Steps
1. Define the state machine explicitly (states + allowed transitions) — reject any transition not in the defined graph, don't allow the LLM's output to induce an undefined state.
2. Implement `limits.py`: every step checks against remaining budget (steps/tools/tokens/time/docs/network) before executing; exceeding any limit transitions to a bounded FAILURE state with a clear reason, not an unbounded retry.
3. Implement circuit breaker keyed per step-type (e.g. if MCP tool calls fail 3 times in a row, disable tool-calling for the remainder of this request, fall back to local-retrieval-only synthesis rather than hanging).
4. Implement cancellation: user can cancel mid-request; orchestrator ensures in-flight tool calls are also cancelled (ties to Phase 08's gateway cancellation support) and no partial write lands in L5 research memory without being marked incomplete.
5. Wire every state transition to L6 audit memory (Phase 03/07) — full trace of what happened for a given request is reconstructable.
6. Explicitly forbid (by construction, not just policy) filesystem access, shell access, and arbitrary code execution from any step — the state machine's step implementations only call Phase 06 retrieval, Phase 08's gateway, and Phase 05's model router; there is no generic "execute" capability exposed at all.

## Configuration
All ceilings above, in `settings.py`, with separate profiles possible for hardware tiers (a Tier 0 machine may warrant tighter ceilings than Tier 2, to keep worst-case latency bounded — decide based on Phase 11 benchmarking, not assumption).

## API Changes
`POST /research/cancel/{request_id}` — explicit cancellation endpoint.
`GET /research/{request_id}/trace` — full state-machine trace for a completed/failed request (debugging/transparency).

## Database Changes
Research trace ties into L5 (`research_sessions`) — each step logged with state, duration, outcome.

## Security Requirements
No step in the state machine has capabilities beyond what's explicitly wired (retrieval, gateway-mediated tool calls, model inference) — this is the primary control against an uncontrolled agent, enforced architecturally, not just documented as a rule.

## Performance Requirements
Ceilings must be tight enough to bound worst-case latency to something usable interactively — exact numbers set from Phase 11 benchmarking on real hardware, not guessed here.

## Testing
- Unit: each ceiling correctly triggers `LimitExceeded` at the boundary.
- Integration: circuit breaker disables a failing step type after threshold, request still completes (degraded, not hung).
- Security: attempt to induce an undefined state transition via crafted model output fails safely.

## Acceptance Criteria
- No test scenario can produce an infinite loop or unbounded resource consumption.
- Cancellation cleanly stops in-flight work with no orphaned state.
- Full trace reconstructable for any request via audit memory.

## Rollback
Orchestrator can be bypassed via config flag reverting to the simpler direct retrieve→generate flow (no tool calls, no multi-step research) — useful if the state machine itself introduces instability.

## Validation Commands
```
pytest backend/tests/orchestrator/ -v
pytest backend/tests/orchestrator/test_limits.py -v
pytest backend/tests/orchestrator/test_circuit_breaker.py -v
```
