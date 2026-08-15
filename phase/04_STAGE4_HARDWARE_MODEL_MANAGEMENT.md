# Stage 4 — Hardware Detection & Dynamic Model Management

Goal: eliminate the current dependency on user-typed hardware form values; select model tier automatically, allow override, never silently degrade.

## 1. Automatic hardware detection
- Detect at app startup (and on demand): total RAM, available VRAM (if discrete GPU present, via platform-appropriate query — e.g. `nvidia-smi` if present, otherwise assume CPU-only), CPU core count.
- User-typed values (if a settings form still exists) become an **override**, not the primary input — detected values are the default, form values only take effect if explicitly set by the user and are validated against detected reality (warn if a user claims more VRAM than detected).
- Acceptance: on a machine with no user configuration at all, the system selects a working model tier with zero manual input.

## 2. Tier mapping (from `00_MASTER_PLAN.md`)

| Tier | Params | Trigger | Fallback behavior |
|---|---|---|---|
| Tier 0 | 3B | <8GB usable RAM/VRAM, or detection fails | Always available — this is the guaranteed floor, ship it as the default Ollama pull on first run |
| Tier 1 | 7–8B (SaulLM-7B preferred) | 8–16GB usable | Offered as upgrade once detected; not auto-upgraded without confirming download size/time is acceptable to the user |
| Tier 2 | 13–15B | >16GB usable or capable discrete GPU | Optional, opt-in — never auto-selected without explicit user confirmation given larger download/resource footprint |

## 3. Model pull/management via Ollama
- On tier selection (auto or user-confirmed upgrade), trigger `ollama pull <model>` for the selected model if not already present, with visible progress in the UI (non-technical users must not see a silent multi-GB download with no feedback).
- Store selected tier + model name in local config (not hardcoded), re-validated against detection on each startup in case hardware changed (e.g. app moved to different machine, or running in a VM with different limits).
- Acceptance: switching the app between two machines with different specs results in different auto-selected tiers without code changes.

## 4. Graceful degradation
- If a higher tier model fails to load (OOM, etc.) at runtime, fall back to the next tier down automatically, log the event to the audit layer, and surface a non-alarming notice to the user rather than a hard crash.
- Acceptance: forcing an OOM condition on a Tier 2 model results in automatic fallback to Tier 1 or Tier 0 with the conversation continuing, not a crash.

## 5. Consistency with generation constraints
- Regardless of tier, the same system prompt (`08_SYSTEM_PROMPT.md`) and output validation layer (Stage 1, item 9) apply — a smaller model does not get a relaxed citation requirement. If a smaller model fails validation more often, that surfaces as a validation-retry/refusal rate metric (feed into `07_EVAL_HARNESS.md`), not as a reason to loosen the gate.

## Exit criteria for Stage 4
Auto-detection works with zero manual input for the floor tier; tier upgrade path is opt-in and visible; fallback on failure is automatic and logged; validation strictness is uniform across tiers.
