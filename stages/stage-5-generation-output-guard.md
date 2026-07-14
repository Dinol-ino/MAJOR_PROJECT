# Stage 5: Generation and Output Guard

## Objective

Move generation and answer validation to the new target stack while keeping the runtime abstraction clean and reversible.

## Target state

- Primary generator target: `google/gemma-3-4b-it`
- Output guard includes:
  - citation verification
  - PII detection with `Presidio`
  - entailment / contradiction check with a `DeBERTa-v3` NLI checkpoint
  - policy and leak checks

## Runtime decision

Do not hard-wire generation to one transport too early.

Approved architecture:

- keep a runtime adapter layer
- allow temporary continuity through `Ollama`
- switch the default generator only after retrieval and trust scoring are stable

This avoids breaking the current demo path while the rest of the stack changes underneath it.

## Output guard flow

1. generator produces draft answer
2. citation verifier checks answer against retrieved chunk ids
3. Presidio scans for sensitive entities
4. NLI verifier labels claims as:
   - supported
   - contradicted
   - unknown
5. policy layer decides allow, redact, or quarantine

## Required installs

- access to `google/gemma-3-4b-it`
- `transformers>=4.50.0` if Hugging Face runtime is chosen
- `Presidio`
- chosen `DeBERTa-v3` NLI checkpoint

## Required `.env` values

- `MODEL_RUNTIME`
- `GENERATOR_MODEL`
- `GENERATOR_CONTEXT_TOKENS`
- `HF_TOKEN`
- `PRESIDIO_ENABLED`
- `NLI_MODEL`
- `OUTPUT_QUARANTINE_MODE`

## In scope

- runtime abstraction for generation
- answer verification chain
- output quarantine policy
- citation-grounding enforcement

## Out of scope

- Langfuse full instrumentation
- admin model registry UI
- frontend redesign

## Risks

1. Gemma cutover before retrieval quality stabilizes will blur whether failures come from retrieval or generation.
2. Presidio and NLI add latency; they need policy thresholds, not unconditional use in every path from day one.
3. If citation verification is loose, the answer guard will look stronger than it really is.

## Exit criteria

- The generator is replaceable behind one interface.
- Output validation is stronger than token overlap alone.
- The system can quarantine unsupported or privacy-unsafe answers before they reach the user.
