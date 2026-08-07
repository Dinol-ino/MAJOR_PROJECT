# Stage 3 — Persistent Memory Architecture

**Depends on Stage 1** (sessions must be bound to authenticated users before you make their
history permanent — otherwise you're permanently storing unowned data).

## The three memory tiers this stage implements

1. **Short-term conversation memory** — already correct, keep as-is: Redis, `SessionMemoryStore`,
   TTL-based, last-5-turns injected into the prompt (`chat.py` lines ~180-190).
2. **Long-term conversation memory** — **missing today**. Confirmed: no code path persists chat
   `history` to Postgres; it only exists in Redis and is lost when `SESSION_TTL_SECONDS` (7200s)
   expires. This stage adds it.
3. **Knowledge memory** (documents/corpus) — already in Postgres/pgvector, out of scope for this
   stage, covered by Stage 2.

## 3.1 Add a durable transcript table

**Task:**
1. New Alembic migration adding `chat_messages` table: `id`, `session_id`, `owner_user_id`
   (from Stage 1's `SessionRecord`), `role` (`user`/`assistant`), `content`, `sources_json`,
   `blocked_by`, `latency_ms_json`, `created_at`.
2. In `chat.py`, after a successful (or blocked) response is built, write both the user message
   and assistant response as rows in `chat_messages`, in addition to the existing
   `memory_store.put_context()` Redis write — **don't replace the Redis write, add alongside it.**
   Redis stays the fast path for prompt-building; Postgres becomes the permanent record.
3. Do this as a background/async write where possible (don't add it to the request's critical
   path in a way that increases perceived latency — fire-and-forget via a background task, with
   a retry-on-failure log, not a blocking call before the response returns).

## 3.2 Expose transcript history via API

**Task:** add `GET /sessions/{session_id}/history` (or extend the existing `/audit/{session_id}`
route if that's a better fit for the existing contract) returning paginated `chat_messages` rows
for the session, scoped to `owner_user_id == current_user.id` (reuse Stage 1's ownership check).
This is also the gap your own plan already flagged: a `GET /sessions` endpoint and
`SessionList.jsx` component were noted as needed for the left-panel session history UI but not
yet tracked — this stage is where that gets built for real, backed by durable data instead of
Redis-only state that would make a "session history" panel misleading (sessions older than the
TTL would silently vanish from the list otherwise).

## 3.3 Conversation summarization for long sessions

**Problem:** the prompt only ever includes the last 5 turns (`history[-5:]` in `chat.py`). For a
long legal consultation session, earlier context is silently dropped, not summarized.

**Task:**
1. When a session's Redis-stored `history` list exceeds a configurable threshold (e.g. 10 turns),
   generate a short summary of the older turns using the existing local generator (no new model,
   no fine-tuning needed — a plain summarization prompt against the same Ollama model already in
   use) and store it as a `summary` field alongside `history` in the Redis payload.
2. When building the prompt, prepend `summary` (if present) before the last-5-turns window,
   instead of just silently truncating older context.
3. This is a **prompting change, not a fine-tuning change** — consistent with the plan's
   principle of keeping the base model's job simple and deterministic.

## 3.4 Document version memory — confirm, don't rebuild

**Confirmed already working:** deterministic UUIDs via `uuid.uuid5` hashing (namespace + document
+ chunk index + content hash) already prevent duplicate rows on re-upload, and `document_versions`
already exists in the schema. This stage's only task here is to **surface version history** to
the user — add a field to `UploadResponse` or a small `GET /documents/{document_id}/versions`
endpoint, since the data already exists but currently has no user-facing access path.

## Testing for this stage

- Extend `tests/test_observability_memory.py` with a test that a completed chat turn produces both
  a Redis `put_context` write and a `chat_messages` row.
- Test that history persists and is retrievable after Redis TTL expiry (simulate by clearing Redis
  directly in the test and confirming the Postgres-backed history endpoint still returns data).
- Test ownership scoping on the new history endpoint using Stage 1's isolation test pattern.
