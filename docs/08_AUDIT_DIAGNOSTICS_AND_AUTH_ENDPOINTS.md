# Module 8 — Audit Ledger, Diagnostics & Auth Endpoints: Purpose & Cold-Start Growth

**Scope**: `app/routes/audit.py`, `app/routes/diagnostics.py`, `app/routes/auth.py`, `GET /health`, `GET /health/db`. This is the trust layer — the whole product's pitch is *auditability*, so this module gets the strictest bar.

---

## 8.1 `GET /audit/{session_id}` and `GET /audit/verify` — purpose: tamper-evident proof, not a decorative badge

Img 3's screenshot shows exactly the right shape: "Total Audit Records: 1," "Legal Queries Executed: 1," "Shield Block Events: 0," a hash-chain row with `session_initialized`, current hash, previous hash, and a "100% Verified & Untampered" banner. The problem is scale and honesty at scale, not the mechanism — a ledger with 1 record after "Enterprise Production Grade... Formally Signed-Off" (report.md's own framing) is a symptom, and your prior audit already named it directly ("Audit ledger showing zero records despite real activity").

**Task 8.1.1**: Per Module 4 §4.1's `ChatResponseFinalized` fan-out, confirm every real chat call, upload, MCP tool call, and defense-layer decision produces a ledger row. Test by running a realistic 10-minute session (several chats, one upload, one MCP-backed query) and confirming the record count and category breakdown (`Chat Invocations` / `Shield Blocks` / `PDF Ingestion` — the tab structure already built in Img 3) actually reflects that session's real activity, not a static "1."

**Task 8.1.2**: `GET /audit/verify`'s hash-chain walk is good cryptographic design — keep it exactly as designed (report.md §5) — but the "100% Verified & Untampered" banner text should be conditional on the verify endpoint actually being called fresh for the current view, not a permanently-rendered string. If verification hasn't run yet or fails, the banner must say so, not default to the success message.

**Task 8.1.3**: `Export Audit Trail` button (Img 3) — verify this produces a real export of the actual queried records (JSON, per report.md's endpoint catalog), not a placeholder file. This is the kind of button that's trivial to leave non-functional during development and easy to forget — flag it explicitly for a manual click-test before any further sign-off language is used about this project.

## 8.2 `GET /diagnostics`, `/diagnostics/trace/{request_id}`, `/diagnostics/metrics/recent`, `/diagnostics/metrics/summary` — purpose: operator-facing proof the SLAs in report.md §14 are real, continuously

**Task 8.2.1**: report.md §14 presents specific empirical numbers (p50/p95/p99, TTFT, concurrency scaling) as a one-time benchmark result. `GET /diagnostics/metrics/summary` should compute these live from the actual ring buffer, and the numbers currently frozen in the report should be replaced, in any future report, with "as of {last regenerated date}, computed from `/diagnostics/metrics/summary`" — a benchmark table is only trustworthy if it's regenerable on demand, not hand-copied once and left in a document indefinitely (which is exactly what turned "190 passed in 44.22s" into a claim nobody could re-verify without rerunning pytest themselves).

**Task 8.2.2**: `GET /diagnostics/trace/{request_id}` (keyed on the correlation ID from Module 1 §1.1.2) is the direct debugging tool for the Img 3 "Failed to fetch" failure mode — every error surfaced in the UI should carry its correlation ID so a user (or you) can pull the exact trace instantly instead of reconstructing what happened from a screenshot, which is literally the situation this whole conversation started from.

## 8.3 `app/routes/auth.py` — purpose: real identity, which Module 2's Vault isolation now depends on

**Task 8.3.1**: Per Module 2 §2.1.2, `ProjectVault.user_id` must be server-derived from real authentication, not a client-supplied session ID. This makes `auth.py` load-bearing in a way it may not have been before — verify `POST /auth/login`'s bearer token is actually checked on every Vault/memory/document endpoint (a proper `Depends()` auth guard in FastAPI, applied consistently), not just present on `/auth/me`. This is the concrete fix for the audit's "workspace isolation keyed on client-generated session_id" finding.

**Task 8.3.2**: Given this is positioned for law firms handling confidential client data, the password hashing (PBKDF2-HMAC-SHA256, per report.md) is reasonable but should be paired with basic account hardening antigravity should confirm exists before this is used with real client data: rate-limited login attempts (SlowAPI is already a dependency, per report.md §3 — reuse it here specifically, don't add a second throttling library), and JWT/session storage should move out of localStorage (per your audit's confirmed finding) into an httpOnly cookie or equivalent, since localStorage is readable by any injected script and this product's entire value proposition is resistance to exactly that class of attack.

## 8.4 `GET /health`, `GET /health/db` — purpose: the honest "is this actually running" check that should have prevented Img 3's confusing error

**Task 8.4.1**: The frontend should poll `/health` on load and before allowing chat interaction — if Ollama is unreachable (report.md's own documented 2.0s fast-fail), the UI should show "Model engine offline" *before* the user submits a query, not let them submit and receive a message that misleadingly reads as a security block (Module 1 §1.1). This single change would have prevented the exact confusion visible in Img 3.

## Acceptance criteria for Module 8
- [ ] A realistic multi-action session produces a proportional, verifiable audit record count — no more static "1."
- [ ] "100% Verified" banner is conditional on a real, current verification pass.
- [ ] Export Audit Trail produces a real file with real data (manually verified).
- [ ] Every UI-surfaced error includes a correlation ID traceable via `/diagnostics/trace/{id}`.
- [ ] Vault/document/memory endpoints enforce real auth, not client-supplied session IDs.
- [ ] JWT no longer stored in localStorage.
- [ ] Health check gates the chat UI proactively instead of failing confusingly after submission.
