# Stage 1 — Security, Isolation, Input/Output Validation

Goal: close every gap confirmed in the architectural audit before any retrieval/quality work begins. Nothing downstream is trustworthy if this stage is incomplete.

## 1. Session isolation → identity-based, not client-generated

- Replace client-generated `session_id` as the workspace isolation key with authenticated user identity.
- Every workspace-scoped query (retrieval, memory read/write) must resolve identity server-side from the auth token, never trust a client-supplied session identifier for isolation boundaries.
- Acceptance: a request with a forged/reused `session_id` but no valid matching auth cannot read another user's workspace data.

## 2. CORS

- Remove wildcard origin configuration. Explicit allow-list of known frontend origins (desktop app's local origin, any web deployment origin).
- Do not combine wildcard origins with `credentials: true` under any circumstance — this combination is the specific misconfiguration to eliminate.
- Acceptance: preflight requests from non-allow-listed origins are rejected.

## 3. JWT storage

- Move JWT out of localStorage. Use httpOnly, Secure, SameSite cookies for the web path; for the Tauri desktop path use the OS-level secure storage mechanism available to the app (not plain localStorage/sessionStorage equivalents).
- Acceptance: token is not accessible via client-side JS (`document.cookie` for httpOnly, or OS keychain API for desktop).

## 4. Rate limiting

- Add rate limiting at the API layer — per-identity, not per-IP alone (IP-based alone is insufficient for a desktop app on shared/NAT'd networks).
- Apply to all endpoints, with tighter limits on generation endpoints (expensive) than read endpoints.
- Acceptance: burst requests beyond threshold return 429, logged to audit layer.

## 5. Defense layer deduplication (Layer 1 / Layer 1.5)

- Audit finding: Layer 1 and Layer 1.5 both re-run the injection check on the same unchanged query string.
- Fix: compute a hash of the normalized query once; cache the Layer 1 result keyed on that hash for the lifetime of the request. Layer 1.5 either reuses that cached result or runs a genuinely independent second check — it must not re-execute Layer 1's identical check.
- Acceptance: profiling shows exactly one classifier inference per unique query string per request, not two.

## 6. Injection risk as a hard gate

- Replace additive trust-scoring for injection risk with a hard gate: above threshold → reject before retrieval/generation, full stop.
- No blending of injection score into an overall trust score that other signals can offset.
- Acceptance: a query scoring above the injection threshold never reaches the retrieval or generation layer, regardless of other signal values.

## 7. PDF sanitization on ingest

- Audit finding: no PDF sanitization currently on ingest.
- Add sanitization step before any PDF content (user-uploaded or bulk-ingested per Stage 2's corpus pipeline) is parsed into text — strip embedded scripts/actions, normalize encoding, reject malformed structure rather than best-effort parsing through it.
- Acceptance: a PDF crafted with embedded JS/actions is sanitized or rejected, never passed through unmodified into the ingestion pipeline.

## 8. PII scanning — always on

- Audit finding: PII scanning is skipped when shield mode is off.
- Fix: PII scanning on ingest must run unconditionally. Shield mode toggle affects query-time behavior (e.g. how aggressively to warn/redact at generation time), it must never disable the ingest-time scan itself.
- Acceptance: PII scan runs and logs findings regardless of shield-mode state.

## 9. Output validation layer (Guardrails)

Implement as part of this stage, not deferred:

- Structured output schema: `{answer, citations: [{source_document_id, section, page}], confidence}`.
- Deterministic entity/token overlap validator between answer and retrieved context actually used — replaces any existing LLM-based self-grounding check. Fail closed: below-threshold overlap → retry once with stricter instruction, then refuse if still failing.
- Citation-existence check: every `source_document_id` cited must resolve to a real corpus entry (query pgvector metadata) — catches fabricated citations, not just missing ones.
- Every Guardrails validator used must be confirmed local-only (no remote API calls) before being enabled — document this confirmation per validator in code comments or a checklist file.
- Acceptance: an answer with zero citations, or a citation to a nonexistent document, never reaches the user unmodified.

## 10. Audit log

- Every request logs: injection score, gate pass/fail, retrieval hit count, citations returned, validation pass/fail + retry count, model tier used, per-layer latency.
- Acceptance: a single request is fully reconstructable from logs — what was checked, what passed, what was returned, and why.

## Exit criteria for Stage 1

All nine items above pass their acceptance criteria against actual running code (not just design review) before Stage 2 work begins. Wire this stage's test cases into `07_EVAL_HARNESS.md`'s adversarial suite as it's built, not after.
