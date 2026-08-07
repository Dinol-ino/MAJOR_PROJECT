# Stage 1 — Security & Isolation Fixes

**Priority: do this stage first, before any performance or feature work.** Item 1.1 is a
confirmed data-isolation gap, not a theoretical risk.

## 1.1 Fix workspace isolation — currently keyed on raw session_id, not authenticated user

**Confirmed evidence:**
- `backend/app/platform/session_scope.py:8-12` — `workspace_id_for_session()` derives the
  workspace UUID purely from `uuid.uuid5(uuid.NAMESPACE_URL, f"dfrag:session:{session_id}")`.
- `backend/app/routes/chat.py:159-162` and `backend/app/routes/upload.py:40-48` both call this
  function directly with the client-supplied `session_id` — no cross-check against the
  authenticated user.
- `frontend/src/App.jsx:57-60` generates `session_id` client-side as
  `Math.random().toString(36).substring(2, 8).toUpperCase()` — a 6-character random string,
  not cryptographically bound to anything.
- Confirmed by direct search: **no code path checks that the authenticated user owns the
  session_id being used** (`NOT FOUND` in inspection).

**Impact:** any authenticated user who supplies another user's `session_id` can query or upload
into that workspace. For a legal product handling client-confidential documents, this is a
confidentiality-breaking bug.

**Tasks:**
1. In `backend/app/platform/models.py`, confirm/extend the `SessionRecord` table (already exists
   per `test_platform_foundation.py`) to store `session_id`, `owner_user_id`, `created_at`.
2. On session creation (first `/chat` or `/upload` call with a new `session_id`, or a new explicit
   `POST /session` if you prefer an explicit creation step), write a `SessionRecord` row binding
   `session_id` to `current_user.id` from the JWT dependency.
3. Add a dependency/check at the top of `chat_endpoint` and `upload_endpoint`: look up the
   `SessionRecord` for the incoming `session_id`; if it exists and `owner_user_id != current_user.id`,
   reject with `403`. If it doesn't exist yet, create it bound to the current user.
4. Change `workspace_id_for_session` (or add a new function) to derive the workspace UUID from
   `owner_user_id` + `session_id` together, not `session_id` alone — so even a guessed session_id
   string can't collide with another user's actual workspace namespace.
5. Both `/chat` and `/upload` currently accept unauthenticated-looking requests based on the
   report — confirm both routes actually run behind `get_current_active_user` (from
   `auth/dependencies.py`). If either doesn't, add the dependency. Do not change the response
   shape of `ChatResponse`/`UploadResponse` — only add the auth/ownership gate.

**Acceptance criteria:**
- A test in `tests/test_auth.py` or a new `tests/test_session_isolation.py`: User A creates a
  session and uploads a document; User B, authenticated as themselves, attempts to `/chat` or
  `/upload` using User A's `session_id` string; response is `403`.
- Existing single-user flows (one user, one session) behave identically to before.

## 1.2 Lock down CORS

**Confirmed evidence:** `backend/app/main.py:39-46` —
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
This combination (`*` origins + credentials) is unsafe and rejected by spec-compliant browsers in
many configurations; where it's permitted through, it's a credential-exfiltration vector.

**Task:** replace `allow_origins=["*"]` with an explicit list sourced from a new
`settings.ALLOWED_ORIGINS` (comma-separated env var, default to
`["http://localhost:3000"]` for dev). Add `ALLOWED_ORIGINS` to `.env.example`.

## 1.3 Harden token storage

**Confirmed evidence:** `frontend/src/api/client.js:3-13` stores `dfrag_access_token` and
`dfrag_refresh_token` in `localStorage` — readable by any injected script if an XSS occurs.

**Task (minimum viable fix, no backend session-model rewrite required):**
1. Keep access token in memory (JS variable / React context), not localStorage.
2. Move refresh token to an `httpOnly`, `Secure`, `SameSite=Strict` cookie set by the backend on
   `/auth/login` and `/auth/refresh` responses, instead of returning it in the JSON body for the
   frontend to store itself.
3. Update `auth/router.py`'s login/refresh handlers to set the cookie via `Response.set_cookie`.
4. Update `frontend/src/api/client.js` to stop reading/writing `dfrag_refresh_token` from
   localStorage; rely on the cookie being sent automatically with `credentials: 'include'`.

## 1.4 Add rate limiting

**Confirmed:** no rate limiting middleware exists anywhere in the backend (`NOT FOUND`).

**Task:** add `slowapi` (FastAPI-native, small dependency) with a per-IP and per-user limit on
`/chat` (e.g. 20/minute) and `/upload` (e.g. 10/minute), configurable via
`settings.RATE_LIMIT_CHAT_PER_MINUTE` / `settings.RATE_LIMIT_UPLOAD_PER_MINUTE`. Return `429` with
a clear `Retry-After` header on breach. Add to `.env.example`.

## 1.5 Remove duplicate Layer 1 / Layer 1.5 execution

**Confirmed evidence:** `backend/app/routes/chat.py` calls `input_guard.validate(request.message)`
twice (lines ~110-112 for fast pre-retrieval rejection, then again at ~198) and
`classifier_15.predict(request.message)` twice (~132 and ~223) on the **same, unchanged query
string** within a single request.

**Task:** the fast pre-retrieval check at the top of `chat_endpoint` is the correct pattern (cheap
rejection before expensive retrieval work). Remove the second identical call later in the
function; thread the first call's `(is_clean, reason)` and `clf_res` results through instead of
recomputing. This is a pure latency fix — no behavior change, since the input hasn't changed
between the two call sites.

## 1.6 Gate trust score on injection risk instead of averaging it

**Confirmed evidence:** `backend/app/defense/trust_scorer.py:77-114` — injection risk is one
weighted term among four (`similarity 0.4, source 0.3, injection 0.2, freshness 0.1`), so a chunk
flagged `malicious` (`injection_risk_score = 1.0`) can still surface a high composite trust score
if similarity and source trust are high.

**Task:** change the scoring logic so that a `malicious` classification from the Layer 1.5
classifier **hard-caps** the chunk's final trust score at a low ceiling (e.g. 0.15) regardless of
the other three factors, rather than contributing 20% additively. `suspicious` can keep a
multiplicative penalty on the composite score rather than being purely additive. Add
`TRUST_INJECTION_HARD_CAP` to settings so this is tunable, not hardcoded.

## 1.7 Make PII/prompt-leak checks mandatory regardless of shield toggle

**Confirmed evidence:** the shield-off branch in `chat.py` skips `Layer3OutputGuard.validate()`
entirely, meaning PII redaction is also skipped when a user turns the shield off.

**Task:** split `Layer3OutputGuard.validate()` into two entry points:
- `validate_safety(answer)` — PII scan + prompt-leak detection only. **Always runs**, regardless
  of `shield_on`.
- `validate_grounding(answer, chunks, prompt)` — grounding/citation/NLI checks. Only runs when
  `shield_on=true` (this part staying optional is fine — it's a quality/grounding gate, not a
  data-leak gate).
Wire the shield-off branch in `chat.py` to call `validate_safety()` before returning, even though
it still skips `validate_grounding()`.

## 1.8 Baseline PDF sanitization on ingest

**Confirmed evidence:** `document_parser.py`'s PDF parsing path (PyMuPDF/pdfplumber) does no
sanitization step before extracted text is chunked and embedded — confirmed `NOT FOUND` for any
sanitization logic.

**Task (minimum viable, don't over-engineer this stage):**
1. Strip embedded JavaScript actions from PDFs before parsing (PyMuPDF exposes
   `doc.get_page_fonts`/embedded file and JS APIs — reject or strip files containing `/JavaScript`
   or `/JS` catalog entries).
2. Normalize extracted text with Unicode NFKC before chunking, to collapse zero-width characters
   and homoglyph tricks that could otherwise slip Layer 2's phrase-stripping.
3. After extraction, run the extracted text through the **existing** Layer 1.5 classifier before
   it's persisted as a chunk — if a chunk classifies as `malicious`, tag it with a low trust
   ceiling at ingest time (reuses 1.6's hard-cap logic) rather than only catching it at query
   time.

## Testing for this stage

- Extend `tests/test_defense_layers.py` with cases for 1.5 (hard-cap) and 1.7 (mandatory PII scan
  on shield-off).
- Add `tests/test_session_isolation.py` per 1.1.
- Run `tests/attack_suite/run_comparison.py` before/after — block rates should not regress, and
  latency in the "total" column should visibly drop due to 1.5's deduplication.
