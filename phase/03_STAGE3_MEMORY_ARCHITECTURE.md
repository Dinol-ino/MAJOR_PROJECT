# Stage 3 — Memory Architecture (Redis + Postgres + pgvector)

Four distinct systems, kept explicitly separate in schema and code — do not let application logic blur them (e.g. a "get user memory" call must never accidentally pull corpus metadata).

## 1. Redis — short-term conversational context (already present)
- TTL-bound. Holds active session's recent turns for coherent multi-turn generation.
- No change to lifecycle; this stage does not touch Redis except to define the handoff into Postgres below.

## 2. Postgres — durable transcript memory (new, this stage's primary deliverable)
- Fixes: history currently lost when Redis TTL expires.
- Schema (minimum):
```sql
CREATE TABLE conversations (
  conversation_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  title TEXT
);

CREATE TABLE messages (
  message_id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
  role TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content TEXT NOT NULL,
  citations JSONB,              -- structured citations from Guardrails output
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
- On Redis TTL expiry, the conversation must already be durably persisted in Postgres — write-through on every turn, not a batch job that risks losing data between TTL expiry and persistence.
- Acceptance: a conversation survives Redis TTL expiry and a full app restart with no data loss.

## 3. pgvector — knowledge corpus (already present, schema extended in Stage 2)
- No change in this stage beyond what Stage 2 already specifies. Referenced here only to confirm it is not the same store as transcript memory.

## 4. Postgres — corpus provenance tables (from Stage 2's metadata schema)
- Lives in the same Postgres instance as transcript memory, but as distinct tables (`legal_documents`, `document_versions`) — never joined against `conversations`/`messages` in application logic except for citation-existence checks (Stage 1, item 9).

## 5. Session-list endpoint (gap identified, not yet tracked elsewhere)
- `GET /sessions` — returns the authenticated user's conversation list (id, title, created_at, last_message_at) from the `conversations` table.
- Frontend: `SessionList.jsx` — renders this list, allows selecting a past conversation to reload into active view (pulling full message history from `messages`).
- Acceptance: a user can see and reopen a past conversation after restarting the app.

## 6. Identity binding
- Every row in `conversations`, `messages`, and any per-user preference table is bound to the identity-based user_id established in Stage 1 (item 1) — never a client-generated session_id.
- Acceptance: two different authenticated identities cannot see each other's conversation lists even if they share a client-generated session_id (this is a direct regression test against the Stage 1 isolation fix).

## Exit criteria for Stage 3
Durable transcript storage, session-list endpoint + frontend, and corpus provenance tables all exist, are identity-bound, and pass acceptance criteria above. This stage can run in parallel with the tail end of Stage 2 (no hard dependency between corpus ingestion and transcript memory), but both must be complete before Stage 4.
