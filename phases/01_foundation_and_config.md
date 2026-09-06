# Phase 01 — Foundation & Configuration Centralization

Depends on: Phase 00 (verification manifest complete)
Blocks: 02–16 (all later phases consume config from this layer)
Modifies: any module currently reading hardcoded constants
Introduces: `backend/app/config/` registry, versioned system prompt architecture
Validates: no hardcoded model names, thresholds, or timeouts remain outside this layer

## Objective
Remove scattered constants (model names, timeouts, thresholds, retention periods, MCP permissions, network mode) and centralize them into typed, validated configuration.

## Current State
Per Phase 00 manifest — likely mixed: some config may already be centralized (e.g. if hardware detection was fixed), but prior audit confirmed hardcoded model names and thresholds existed in at least the injection-scoring and hardware-detection paths.

## Problem
Scattered constants make every later phase's "no hardcoded X" requirement unenforceable — this has to be fixed first or every subsequent phase inherits the same problem.

## Architecture Change
Current → Transitional → Target:
`Constants scattered in modules` → `Partial migration, deprecation warnings on direct constant use` → `Single typed settings registry, all modules import from it`

- `backend/app/config/settings.py` — Pydantic Settings, one class per concern (`ModelConfig`, `SecurityConfig`, `RetrievalConfig`, `MemoryConfig`, `MCPConfig`, `PerformanceConfig`, `NetworkModeConfig`).
- `backend/app/config/model_registry.yaml` — model tiers, names, resource requirements (ties into Phase 05).
- `backend/app/config/mcp_permissions.yaml` — tool allowlist and permission scopes (ties into Phase 08).
- `backend/app/config/legal_sources.yaml` — allowlisted domains for online research (ties into Phase 10).

## Files to Modify
Every module identified in the Phase 00 manifest as containing hardcoded model names, thresholds, or timeouts — exact list populated from manifest output, not guessed here.

## Files to Add
- `backend/app/config/settings.py`
- `backend/app/config/model_registry.yaml`
- `backend/app/config/mcp_permissions.yaml`
- `backend/app/config/legal_sources.yaml`
- `backend/app/prompts/` — versioned system prompt directory: `security_core.md` (immutable), `legal_behavior.md`, `retrieval_instructions.md`, `tool_policy.md`, `citation_requirements.md`, `task_template.md` — assembled at runtime, never concatenated ad hoc.

## Files to Remove
None yet — deprecate in place (log a warning if old constant path is hit) until Phase 15 confirms nothing still references it.

## Dependencies
Depends on: Phase 00
Blocks: all phases 02–16
Modifies: config-reading code throughout backend
Introduces: settings registry, versioned prompt architecture
Validates: `grep`-based check for hardcoded model name strings returns zero hits outside `model_registry.yaml`

## Implementation Steps
1. Enumerate every hardcoded constant found in Phase 00 manifest evidence.
2. Create typed settings classes; migrate one concern at a time (security thresholds first, since Phase 07 depends on them).
3. Build the versioned prompt assembler: a function that composes the six prompt sections in fixed order, rejecting any attempt to inject additional unstructured text into `security_core.md`'s position.
4. Add a lint/CI check (simple grep or AST check) that fails the build if a new hardcoded model name or magic timeout number is introduced outside the registry.

## Configuration
Environment variables for deployment-level values only (DB connection strings, network mode ON/OFF); everything else lives in the YAML registries, loaded once at startup, validated against Pydantic schemas — startup fails loudly on invalid config, not silently falls back.

## API Changes
None user-facing. Internal: any module previously importing constants directly now imports `from app.config import settings`.

## Database Changes
None.

## Security Requirements
`security_core.md` prompt section is immutable at runtime — no code path may modify it per-request. Config registry itself must not be writable by any request-handling code path (read-only after startup load).

## Performance Requirements
Config load adds negligible startup time (<100ms target — verify empirically, don't assume).

## Testing
- Unit: settings validation rejects malformed YAML/env values.
- Integration: prompt assembler produces identical output for identical inputs (determinism check).
- CI: hardcoded-constant grep check.

## Acceptance Criteria
- Zero hardcoded model names/thresholds/timeouts remain outside the registry (verified by grep/AST check, not by review alone).
- System prompt is assembled from versioned sections, `security_core.md` cannot be altered by request-time input.
- App fails fast on invalid config at startup rather than at first use.

## Rollback
Revert to direct constant imports per-module; settings registry files can remain unused without breaking anything (additive change, not destructive) until modules are migrated.

## Validation Commands
```
grep -rn "gpt\|llama\|mistral\|saul" backend/app --include=*.py | grep -v config/
pytest backend/tests/config/
```
