# Phase 08 — MCP Gateway & Tools

Depends on: Phase 07 (context sanitization, hard-gate security must exist before any tool call is possible)
Blocks: Phase 09 (agentic orchestrator invokes tools through this gateway), Phase 10 (online legal research uses these tool categories)
Modifies: existing MCP tools view (if Phase 00 confirms one exists) — likely UI-only currently, needs a real backend gateway behind it
Introduces: Policy Engine, Tool Permission Layer, formal tool categories
Validates: unauthorized tool call rejection, malicious tool result handling (feeds Phase 12)

## Objective
Build the actual MCP architecture — policy-gated, allowlisted, typed, audited — behind whatever "MCP tools view" currently exists, rather than treating a UI button as the whole subsystem.

## Current State
Per Phase 00 manifest — this is one of the three most likely **PARTIAL** verdicts (along with crypto ledger and Consensus UI). A frontend "MCP tools view" existing does not imply a policy engine or permission layer exists behind it — verify specifically whether tool calls today pass through any check at all, or are dispatched directly.

## Problem
Report.md's claim of an "MCP tools view" is a UI description, not an architecture description. If the LLM currently has direct or lightly-gated tool access, that's the highest-severity gap in this phase — unrestricted tool access is explicitly the failure mode this whole subsystem exists to prevent.

## Architecture Change

```
User → Intent/Query Classifier (Phase 05 routing) → Policy Engine → Tool Permission Layer
→ MCP Gateway → Approved MCP Servers → Tool Results → Tool Result Sanitization (Phase 07's shared sanitizer)
→ Evidence/Provenance Layer → Retriever/Research Planner → LLM → Output Verification (Phase 07)
```

**Tool categories** (from `mcp_permissions.yaml`, Phase 01):
```
LEGAL_SEARCH        — read-only, offline-capable if local corpus covers it
CURRENT_LAW         — requires ONLINE mode, allowlisted government sources only
CASE_LAW_SEARCH     — requires ONLINE mode, allowlisted sources only
GOVERNMENT_SOURCE    — requires ONLINE mode, strictest allowlist
DOCUMENT_SEARCH      — local only, user's own uploaded documents
LOCAL_RETRIEVAL      — always available, offline-safe (Phase 06's retrieval)
DEEP_RESEARCH        — composite category, bounded by Phase 09's execution limits
```

Each category has: allowed tools, required mode (offline/online), max calls per request, timeout, rate limit — no LLM-initiated tool call bypasses this table.

## Files to Add
- `backend/app/mcp/policy_engine.py` — evaluates whether a requested tool call is permitted given category, mode, and current request's budget.
- `backend/app/mcp/permission_layer.py` — enforces allowlist, schema validation on tool inputs/outputs.
- `backend/app/mcp/gateway.py` — actual dispatch to approved MCP servers, with timeout/rate-limit/cancellation.
- `backend/app/mcp/tool_registry.py` — typed tool definitions (schema in, schema out) per category.

## Files to Modify
Existing MCP UI/view code (per manifest) — wire it to actually call through the gateway instead of whatever it currently does.

## Dependencies
Depends on: Phase 07
Blocks: 09, 10
Modifies: existing MCP UI wiring
Introduces: policy engine, permission layer, gateway, tool registry
Validates: Phase 12's MCP eval category

## Implementation Steps
1. From Phase 00 manifest, determine exactly what the current MCP tools view actually does when a tool is "used" — this determines whether this phase is "add a gateway" or "replace direct dispatch with a gateway."
2. Define tool categories and permissions in `mcp_permissions.yaml` (Phase 01 registry).
3. Implement `tool_registry.py`: every tool has a typed input/output schema — no tool accepts arbitrary unstructured input from the LLM.
4. Implement `policy_engine.py`: given a requested tool + category + current mode (offline/online) + current request's call budget, return allow/deny with a reason (logged to L6 audit).
5. Implement `permission_layer.py`: validates the LLM's tool-call request against the registry schema before it reaches the gateway — malformed or out-of-schema requests rejected here, never reach a real MCP server.
6. Implement `gateway.py`: actual dispatch, with per-call timeout, rate limit, and cancellation support; tool results pass through Phase 07's `context_sanitizer.py` before being handed back to the LLM as evidence — never as instructions.
7. Wire the existing frontend MCP view to reflect real gateway state (which tools are available, current mode, why a call was denied if it was) rather than static/decorative UI.

## Configuration
`mcp_permissions.yaml` (categories, allowlists, mode requirements, call/timeout/rate limits per category) — Phase 01 registry.

## API Changes
- `GET /mcp/status` — current mode, available tool categories, active servers.
- `POST /mcp/tool-call` (internal, LLM-initiated via orchestrator, not directly user-facing) — schema-validated request/response.

## Database Changes
`mcp_tool_calls` table (or extend `audit_events`) — every call logged with category, tool, requester, timestamp, result status, latency.

## Security Requirements
This phase is a security boundary by definition: no LLM-initiated tool call reaches an actual MCP server without passing policy engine + permission layer checks. Tool results are untrusted data (Phase 07's sanitizer applies here specifically, not optionally). No arbitrary URL/tool selection by the LLM — only registry-defined tools, only within permitted categories.

## Performance Requirements
Policy engine check adds latency per tool call — must be lightweight (rule/lookup-based, not itself an LLM call) to avoid compounding agentic workflow latency (Phase 09).

## Testing
- Security: unauthorized tool call attempt is rejected (test with a crafted request outside the allowlist).
- Security: malicious tool result (containing embedded instructions) is sanitized before reaching the LLM, verified by test.
- Integration: offline mode blocks all online-required categories with a clear, correct rejection reason.

## Acceptance Criteria
- Every tool call traces through policy engine → permission layer → gateway — no direct-dispatch path remains.
- Malicious/malformed tool results cannot influence model behavior as instructions (tested, not assumed).
- MCP UI accurately reflects real backend state, not decorative.

## Rollback
Feature-flag to fully disable MCP (falls back to local-only retrieval, Phase 06) if the gateway introduces instability — this should be the easiest phase to roll back given it's additive on top of existing retrieval.

## Validation Commands
```
pytest backend/tests/mcp/ -v
pytest backend/tests/mcp/test_policy_engine.py -v
pytest backend/tests/mcp/test_result_sanitization.py -v
```
