# Module 2 — Project Vault, Permanent Memory, Deep Thinking Mode

**Priority**: P1. Depends on Module 1 sign-off. **Dependency note**: this was already scoped once as "Project Vault" in the `DFrag v4: Enterprise Architecture Refinement Specification` document you have — that spec is largely reusable, but it was written before the Module 1 grounding gaps were confirmed by evidence audit, so this doc corrects a few of its assumptions rather than replacing it.

---

## 2.1 Correcting the existing Vault spec

The prior spec's §2 ("Project Vault & Deep Thinking Mode") is structurally sound: `ProjectVault` entity, FK relations from `DocumentMemory` (L4) and `ConversationMemory` (L2) to `project_vault_id`. Keep that schema. Two corrections:

**Correction 2.1.1** — The prior spec says "Transition PDF storage from session-scoped ephemeral vectors to vault-scoped persistent vectors in ChromaDB/PostgreSQL." Per your own audit, Postgres durable transcript storage is currently *missing entirely* — Redis short-term context exists but history is lost on TTL expiry. Do not build vault-scoped persistence on top of a persistence layer that doesn't exist yet. Sequencing:
1. First land plain durable L2/L4 storage in Postgres (this closes the audit's "Persistent memory gap" item on its own, independent of Vault).
2. Only then add `project_vault_id` as a nullable FK — conversations/documents not yet assigned to a vault (the common "just chatting" case) remain valid with `project_vault_id = NULL`.

**Correction 2.1.2** — The prior spec's workspace isolation note is silent on identity. Per your audit, isolation is currently keyed on client-generated `session_id`, not authenticated user identity — this is a data-isolation gap, not a cosmetic issue. `ProjectVault.user_id` must be the authenticated user's server-side identity (from your auth/session layer), never a value the client can set or replay. Fix this at the same time as adding the Vault FK, because retrofitting identity-keying after Vault data exists means a migration that has to reason about which orphaned rows belong to which real user — much harder later.

## 2.2 Permanent conversation memory

**Task 2.2.1** — `app/db/models.py`: add `Conversation(id, vault_id [nullable FK], user_id, title, created_at, updated_at)` and confirm `Message` has a FK to `Conversation`, not just to a Redis-backed session key. Migrate existing Redis-only conversation state to write-through: Redis remains the L1/short-term cache (fast reads for the active turn), Postgres is the system of record. This matches the existing 6-layer memory design in `report.md` §7 — L2 is documented as "PostgreSQL / SQLite" already, so this task is about making that documentation true, not inventing a new layer.

**Task 2.2.2** — `GET /sessions` endpoint and `SessionList.jsx` — you already flagged this as a known small gap not yet tracked in the main plan. Scope it here: `GET /vaults/{vault_id}/conversations` (list, for the left panel) and `GET /conversations` (unscoped, for the "general chat" case). Support pagination — don't return the full history table on every load.

**Task 2.2.3** — Rename: `PATCH /conversations/{id}` accepting `{title}`. Frontend: inline-editable title in `SessionList.jsx`, following the same interaction pattern as the file the prior spec already asked to model after Claude's UI (click title → edit → blur/enter to save). No new design system needed — reuse whatever text-input component Module 5 standardizes.

## 2.3 Project Vault as case-file workspace

**Task 2.3.1** — `POST /vaults` `{name}`, `GET /vaults`, `GET /vaults/{id}`, `DELETE /vaults/{id}` (soft delete — legal work should never hard-delete case files without confirmation; add a `deleted_at` column and a 30-day grace period before physical purge, matching typical legal-record-retention expectations — flag this as a policy question for the user's actual firm/compliance requirements, don't hardcode a retention period without confirming it).

**Task 2.3.2** — Per-vault file cap: you specified "uploading certain number of files" — make this a configurable `RetrievalConfig` value (reuse the typed sub-config pattern from `app/config/settings.py` per report.md §2), not a hardcoded constant. Suggested default: reuse the existing "Batch Limit: Up to 10 files" figure visible in Img 1/5's Hardware Tier card — but that number in the screenshot is describing hardware batch-processing capacity, not a vault cap; these are two different constraints and antigravity should not conflate them. Vault file cap is a product/UX decision; hardware batch limit is a resource constraint. Keep them as separate config keys.

**Task 2.3.3** — Vault-scoped documents must show up in the UI with real status, addressing your explicit complaint that "user doesn't understand if the pdf is loaded or not." Minimum states to render, each backed by a real DB column (`DocumentMemory.status`): `uploading` (with byte progress), `queued`, `extracting_text`, `chunking`, `embedding`, `indexed`, `failed` (with the actual error — recall the audit's confirmed defect: "Broken PDF text extraction" — a document that fails extraction must say so, not silently vanish from the UI).

## 2.4 Deep Thinking Mode

**Task 2.4.1** — The prior spec's plan (`reasoning_effort` param on `ChatMessageRequest`, streaming `<deep_thinking>` tokens to an expandable "Reasoning Trace" accordion) is sound and reuses the existing `<deep_thinking>` CoT tags already defined in the `DFrag V4 Master System Prompt` document — don't design a second reasoning format. Two additions:
- Deep Thinking mode should force routing through the full 10-state FSM orchestrator (report.md §9) rather than a single-shot chat completion — this is the actual mechanism that makes reasoning "deep" (multi-step retrieve → tool-call → validate → synthesize), not just a longer visible CoT block from one model call.
- Deep Thinking responses must still pass through the Module 1 relevance threshold at each `RETRIEVE` cycle, not just once at the end — a multi-step reasoning trace that confidently reasons its way to a citation-free conclusion is a worse failure mode than a single bad answer, because the visible reasoning makes it look more trustworthy.

## 2.5 Context window and Claude-like controls

**Task 2.5.1** — Expose actual context window size per active model tier (Tier 0/1/2 models have different native context limits — pull these from `model_registry.yaml`, don't hardcode a single number in the UI) as a visible, live indicator, plus a token-usage meter for the active conversation. This is read-only telemetry, not a new subsystem — surface what `ModelLifecycleManager` already knows.

**Task 2.5.2** — Auto-summarization/truncation strategy when a conversation approaches the active model's context limit: summarize older turns into L3 semantic memory (already designed, per report.md §7, with its "strict validation gate preventing prompt injection attacks from polluting long-term memory" — reuse that gate for summarized content too, since a compromised earlier turn could otherwise poison the summary).

## Acceptance criteria for Module 2
- [ ] Postgres is the system of record for conversations; Redis TTL expiry no longer loses history (verify by killing Redis mid-session and confirming conversation reloads correctly from Postgres).
- [ ] `ProjectVault.user_id` is server-derived, never client-supplied; isolation tested with two authenticated users sharing the same `session_id` pattern to confirm no cross-user leakage.
- [ ] Rename, list, and paginate all work against real endpoints, no mock arrays.
- [ ] Uploaded file status is visible and accurate at every pipeline stage, including failure.
- [ ] Deep Thinking mode routes through the full FSM and is subject to the same evidence threshold as normal chat.
