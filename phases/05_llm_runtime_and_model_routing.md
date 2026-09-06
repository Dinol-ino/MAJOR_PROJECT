# Phase 05 — LLM Runtime & Model Routing

Depends on: Phase 01 (config registry), Phase 04 (caching)
Blocks: Phase 06 (retrieval reranking may use routed models), Phase 09 (agentic orchestrator calls routed models per step)
Modifies: existing Ollama client/hardware-detection code (`stages_2/04` baseline)
Introduces: async runtime manager, config-driven model routing table
Validates: no hardcoded model names, graceful OOM fallback, streaming works end-to-end

## Objective
Replace ad hoc model invocation with an async, streaming, config-driven runtime manager that routes tasks to the cheapest model capable of doing them correctly.

## Current State
Per Phase 00 manifest. `stages_2/04` already specified hardware-aware tiering (3B/7-8B/13-15B) — verify whether that's implemented, partially implemented, or still relies on user-typed hardware values as the prior audit found.

## Problem
Using one model size for every task (classification, routing, summarization, complex legal reasoning) wastes latency and resources on tasks that don't need it, and a synchronous/non-streaming client makes perceived latency worse than actual latency.

## Architecture Change

Current → Transitional → Target:
`Single model, synchronous calls, possibly hardcoded name` → `Async client + routing table, hardware detection still manual` → `Full async runtime manager, automatic hardware detection, config-driven routing, graceful degradation`

**Routing table (config-driven, `model_registry.yaml`):**

| Task | Model class | Reasoning |
|---|---|---|
| Security classification (injection/jailbreak) | Deterministic rules first → small local classifier (86–200M, Phase 07) only if rules are ambiguous | Never use a generation LLM for this — slower and less reliable than a purpose-built classifier |
| Intent/tool-selection routing | Tier 0 (3B) | Simple classification task, doesn't need reasoning capacity |
| Retrieval query reformulation | Tier 0 (3B) | Mechanical task |
| Summarization | Tier 0–1 depending on document complexity | Config-driven threshold on input length/complexity |
| Complex legal reasoning / synthesis | Tier 1 or Tier 2 (hardware-dependent) | Only task tier is escalated for by default |
| Citation verification | Deterministic overlap check (Phase 07) + lightweight model only if deterministic check is ambiguous | Never trust a generation LLM alone to verify its own citations |

## Files to Add
- `backend/app/runtime/manager.py` — model lifecycle: load, warm-up, unload, switch, OOM recovery.
- `backend/app/runtime/router.py` — reads `model_registry.yaml`, maps task type → model tier → actual model name.
- `backend/app/runtime/streaming.py` — token streaming handler with cancellation support.
- `backend/app/runtime/hardware_detect.py` — automatic detection (RAM/VRAM/CPU), per `stages_2/04` spec — verify/complete if partially implemented.

## Files to Modify
Existing Ollama client module (exact path from Phase 00 manifest).

## Dependencies
Depends on: Phase 01, 04
Blocks: 06, 09
Modifies: Ollama client, hardware detection
Introduces: routing table, runtime manager
Validates: Phase 11's model load/unload/latency metrics

## Implementation Steps
1. Confirm via Phase 00 manifest whether hardware detection is automatic or still form-based; complete the automatic path if not (per `stages_2/04`, items 1–2).
2. Implement `router.py`: task type → tier lookup, tier → concrete model name lookup, both from YAML, zero hardcoded names in calling code.
3. Implement async streaming end-to-end: FastAPI endpoint uses `StreamingResponse`, Ollama client streams tokens, frontend consumes via SSE/WebSocket (confirm which the frontend already uses per manifest, extend rather than replace).
4. Implement model warm-up on startup for the Tier 0 floor model (avoid cold-start latency on first request) — do not warm up higher tiers unless already in active use, to avoid wasting resources.
5. Implement OOM recovery: catch load/inference failure, fall back one tier, log to audit (L6 memory), retry once, surface a non-alarming notice to the user if fallback occurred.
6. Implement idle unload: if a higher-tier model hasn't been used within a configurable window, unload it to free resources — reload on next request that needs it (accept the warm-up cost as a tradeoff, document it).

## Configuration
`model_registry.yaml` (tiers/names/resource requirements), `MODEL_IDLE_UNLOAD_SECONDS`, `MODEL_WARMUP_ON_STARTUP` (bool) — Phase 01 registry.

## API Changes
`GET /runtime/status` — currently loaded model(s), tier, hardware detected, reason for current selection (transparency requirement from the original spec: "expose the reason for model selection").

## Database Changes
None directly; model-selection events logged to L6 audit memory (Phase 03).

## Security Requirements
Model routing decisions must not be influenceable by untrusted input (e.g. a crafted query cannot force selection of a specific model as a side-channel or resource-exhaustion attack) — task-type classification determines routing, not raw user text matched against a routing rule directly.

## Performance Requirements
Time-to-first-token and total generation time tracked per tier (Phase 11) — targets set only after real benchmarking on actual hardware, not invented here.

## Testing
- Unit: router returns correct model for each task type given a config.
- Integration: OOM simulation triggers fallback without crash or data loss.
- Streaming: cancellation mid-stream releases resources correctly.

## Acceptance Criteria
- Zero hardcoded model names in calling code (verified by Phase 01's grep check).
- Automatic hardware detection with zero manual input for Tier 0 floor.
- OOM triggers graceful fallback, not crash.
- `/runtime/status` correctly explains current model selection.

## Rollback
Router can be bypassed via a single config flag forcing all tasks to a fixed fallback model — useful for isolating whether an issue is routing logic or the underlying model itself.

## Validation Commands
```
pytest backend/tests/runtime/ -v
pytest backend/tests/runtime/test_oom_fallback.py -v
```
