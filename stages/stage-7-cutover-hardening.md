# Stage 7: Cutover and Hardening

## Objective

Move from architecture design to a stable implementation plan that can replace the legacy stack incrementally and safely.

## Target state

- Chroma path retired
- new retrieval path defaulted
- new env contract active
- evaluation suite expanded
- docs and demo flow updated

## Cutover order

1. run new stack in parallel with the legacy stack
2. compare retrieval quality and latency
3. migrate seed corpus first
4. migrate Tier-2 uploads next
5. switch default path only after acceptance metrics are met
6. archive the legacy Chroma path, do not silently delete it

## Hardening checklist

- session isolation proven
- cross-session document reuse behaves as designed
- `/audit` scoping fixed
- attack suite expanded beyond the current 10 prompts
- hidden-in-document attacks re-tested
- citation verification measured
- reranker latency measured
- OCR fallback tested on scanned PDFs
- rollback instructions written

## Required deliverables before final cutover

- migration runbook
- updated `README.md`
- updated API notes if contracts change
- env setup instructions validated
- model download and installation notes validated

## Exit criteria

- New stack is operationally safer and simpler than the old stack.
- The system still preserves the core DFrag identity:
  - legal retrieval
  - security layering
  - private/local-first operation
  - traceable outputs

## Final rule

If a feature does not improve retrieval quality, defense quality, privacy, or operational clarity, cut it. This branch should favor coherence over feature count.
