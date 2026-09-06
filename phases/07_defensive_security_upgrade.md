# Phase 07 — Defensive Security Upgrade

Depends on: Phase 01 (config for thresholds), Phase 03 (L6 audit memory for logging), Phase 05 (deterministic-first classification routing)
Blocks: Phase 08 (MCP gateway relies on this layer's tool-result sanitization), Phase 09 (agentic security check step)
Modifies: existing three-layer defense (Input Guard / Trusted Context / Output Guard)
Introduces: hard-gate injection scoring, cryptographic audit ledger, Guardrails (conditional/scoped), context sanitization for MCP/web content
Validates: injection/jailbreak/PII/cross-session test suite (feeds Phase 12)

## Objective
Strengthen the existing three-layer defense rather than replace it — close the confirmed gaps (additive scoring, no PDF sanitization, PII scan bypass, layer dedup) and extend coverage to MCP/web content, which didn't exist as an attack surface before this phase.

## Current State
Per Phase 00 manifest, confirm current status of: injection scoring (additive vs gate), PDF sanitization, PII scan conditionality, layer 1/1.5 dedup, and whether a cryptographic audit ledger actually exists or is just a timestamped log (report.md's claim needs verification here specifically).

## Problem
An additive trust score means a sufficiently crafted input can offset injection risk with other signals — this is the single highest-severity gap carried over from prior audit, and it's a hard gate requirement, not a tuning parameter.

## Architecture Change

**Layer 1 — Input Guard** (extended):
- Injection/jailbreak classifier — deterministic pattern rules first (fast, catches obvious cases), local classifier model (Phase 05 routing: 86–200M class) only for ambiguous cases.
- **Hard gate**: above threshold → reject before retrieval/generation, full stop, no blending into a broader score.
- Rate limiting, schema validation on all inputs (SQLi/command-injection/path-traversal patterns rejected at this layer, not relied upon at the DB layer alone — defense in depth).

**Layer 2 — Trusted Context** (extended):
- Context sanitization now explicitly covers **three sources of untrusted content**, not just retrieved documents: retrieved corpus chunks, uploaded documents, and MCP/web tool results (new — didn't exist before MCP work). All three are stripped of embedded-instruction patterns before reaching the prompt, using the same sanitization logic (don't build three separate implementations).
- PDF sanitization on ingest (confirmed gap, fix here per `stages_2/01`).
- PII scanning unconditional on ingest (confirmed gap, fix here — Presidio or equivalent, per `stages_2/09` prerequisites).

**Layer 3 — Output Guard** (extended):
- Deterministic entity/token overlap scoring replaces any LLM self-grounding check (per `stages_2/02` and `03`).
- Guardrails AI: **scoped narrowly** — structured schema enforcement (answer/citations/confidence) and the overlap validator, both local/deterministic. No remote-calling validators enabled (audit each one used, per `stages_2/00`'s warning). Guardrails does not replace the deterministic checks, it implements them in a structured, testable form.
- Citation-existence check against corpus metadata (fabricated citations, not just missing ones).
- PII-in-output check as defense-in-depth (does not replace the ingest-time fix above).

**Cryptographic audit ledger** (verify claim, build if absent): append-only table (Phase 02/03's L6), each entry hash-chained to the previous entry's hash — makes tampering detectable, not just logically prevented by access control. If Phase 00 manifest finds an existing "audit ledger" that isn't actually hash-chained, that's a **PARTIAL** verdict — this phase completes it, doesn't rebuild from scratch.

## Files to Modify
Existing Layer 1/2/3 modules (exact paths from manifest).

## Files to Add
- `backend/app/security/injection_gate.py` — hard-gate implementation, replaces additive scoring.
- `backend/app/security/context_sanitizer.py` — shared sanitization for corpus/upload/MCP-result content.
- `backend/app/security/pdf_sanitizer.py`
- `backend/app/security/pii_scanner.py` (unconditional invocation point)
- `backend/app/security/output_validator.py` — Guardrails-based schema + overlap scoring.
- `backend/app/security/audit_ledger.py` — hash-chaining logic, verification function (walk the chain, detect tampering).

## Dependencies
Depends on: Phase 01, 03, 05
Blocks: 08, 09
Modifies: Layer 1/2/3 defense modules
Introduces: hard gate, unified sanitizer, hash-chained ledger, scoped Guardrails
Validates: Phase 12's security eval category

## Implementation Steps
1. Replace additive injection scoring with hard-gate logic first — highest-severity fix, do it before anything else in this phase.
2. Fix Layer 1/1.5 dedup (query-hash caching of the classification result within a request, per `stages_2/01` item 5).
3. Build unified `context_sanitizer.py`, wire it at all three ingestion points (corpus, upload, MCP result) — MCP point activates once Phase 08 exists, stub it now.
4. Implement PDF sanitization and unconditional PII scanning at ingest.
5. Implement `output_validator.py`: schema enforcement + deterministic overlap scoring + citation-existence check, using Guardrails only for the parts it genuinely simplifies (schema validation), hand-rolled deterministic code for overlap scoring if that's simpler than forcing it through a Guardrails validator.
6. Implement or complete `audit_ledger.py`: each write computes `hash(prev_hash + entry_content)`, stores both; add a verification function that walks the full chain and flags any break — run this in Phase 15's regression suite.

## Configuration
Injection threshold, PII sensitivity level, overlap-score threshold, ledger hash algorithm — all in `settings.py`.

## API Changes
`GET /audit/verify` — runs the hash-chain verification, returns pass/fail + first broken entry if any (admin/diagnostic use).

## Database Changes
`audit_events` table gets `prev_hash`, `entry_hash` columns if not already present (Phase 02/03 schema, completed here if Phase 00 finds it partial).

## Security Requirements
This entire phase *is* the security requirement — explicit coverage: prompt injection, indirect injection (via retrieved/MCP content), jailbreaks, exfiltration, PII leakage, malicious PDFs, malicious web content (once Phase 10 exists), tool poisoning (once Phase 08 exists — sanitizer is shared, ready), path traversal, SSRF (relevant once Phase 10's online mode exists), SQLi, command injection, excessive-context DoS, cross-session/cross-user leakage (ties to Phase 03), unauthorized tool execution (ties to Phase 08).

## Performance Requirements
Hard gate must not meaningfully increase latency over the current (broken) additive scoring — deterministic rules run first specifically to keep the common case fast, only escalating to a model classifier when needed.

## Testing
- Security: full injection/jailbreak/PII/malicious-PDF test suite (adversarial cases from `stages_2/07`, extended).
- Unit: hash-chain verification correctly detects a tampered entry in a test fixture.
- Integration: hard gate blocks 100% of known injection patterns in the test set with zero pass-through regardless of other signal values.

## Acceptance Criteria
- Injection risk is a hard gate — verified by a test that a high-injection-score query never reaches generation, regardless of crafted signals meant to offset it.
- PDF sanitization and PII scanning run unconditionally, verified by test.
- Audit ledger hash-chain verification passes on clean data and correctly flags tampering in a test fixture.
- Guardrails validators in use are confirmed local-only (documented per validator, per `stages_2/02`).

## Rollback
Each sub-component (gate, sanitizer, ledger) is independently feature-flagged for staged rollout; hard gate rollback should be avoided given severity, but is technically possible via config flag if a false-positive rate emergency requires it — log this event loudly if ever used.

## Validation Commands
```
pytest backend/tests/security/ -v
pytest backend/tests/security/test_hard_gate.py -v
pytest backend/tests/security/test_audit_ledger.py -v
```
