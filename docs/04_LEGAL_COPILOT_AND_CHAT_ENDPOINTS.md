# Module 4 — Legal Copilot & Chat Endpoints: Purpose, Cold-Start State, Dynamic Growth

**Scope**: `app/routes/chat.py` (`/chat`, `/chat/stream`, `/chat/history/{session_id}`, `/chat/memory/semantic`), the `LEGAL_COPILOT` view (`ChatWindow.jsx`, `CommandInput.jsx`), and everything downstream it should trigger. This is the root of the whole system — every other view (Citation Graph, Statute Library "recently referenced," Audit Ledger, Diagnostics) should be a *read model* fed by what happens here, not an independently seeded screen.

**Rule for antigravity across this whole file**: nothing described below is allowed to have a static/seed/mock code path in production. If a screen would otherwise be empty, it is empty and says so — it does not fall back to demo data. This is the direct fix for the "Consensus reference but our AI isn't doing any better" complaint: Consensus's UI looks alive because every panel is a real reflection of a real search; ours currently looks alive because some panels contain fixture data dressed as live state.

---

## 4.1 `POST /chat` — single-turn grounded legal Q&A

**Purpose**: Answer one legal question, grounded in retrieved statutory text, with citations. This is the core product. Everything else exists to make this trustworthy and auditable.

**What it is not**: a general-purpose chatbot. Per your Legal-only scope requirement, the query classifier (FSM `CLASSIFY` state) should route anything outside law/criminal/procedural/regulatory domains to a scope-refusal, not attempt an answer — this is different from the `INSUFFICIENT_EVIDENCE` refusal in Module 1 (that's "in-scope but no evidence found"; this is "out of scope entirely").

**Cold-start state**: a brand-new install with only the seed corpus has a small, honestly-labeled statute library. The chat does *not* pretend to know more than that. If asked about an Act that was never ingested, it must say so explicitly ("This Act is not currently in the statutory corpus — you can upload the relevant document or request it be added") rather than let the LLM's parametric knowledge fill the gap silently. This is the practical meaning of your own founding principle: legal facts belong in retrieval, never in weights — enforce it at the refusal boundary, not just as an ingestion-time policy.

**Dynamic interconnection — what one `/chat` call must fan out to**:
1. **L2 Conversation Memory**: message pair written to Postgres (per Module 2), immediately — not batched.
2. **L6 Audit Ledger**: one new hash-chained record per request minimum (`chat_invoked`), plus one per defense-layer decision (Layer 1 pass/block, Layer 2 PII redaction count, Layer 3 grounding score). This is what makes the "Total Audit Records: 1" you saw in the Cryptographic Audit screenshot grow from real usage instead of sitting at 1 forever — see Module 8.
3. **Citation Graph**: every citation actually returned in the response (from the Layer 3 citation-existence check, not from the raw retrieval candidates) should upsert a node/edge into the graph store if not already present, and increment a `reference_count` if already present. See Module 5 §5.2 — this is the actual mechanism that should have produced Img 1/8's graph, and should keep growing it, instead of the graph being a fixed ~14-node seed.
4. **L5 Research Session Memory**: only written if this call is part of a Deep Thinking / multi-step research trace (Module 2 §2.4), not for simple single-turn chat — don't conflate the two.
5. **Statute Library "last referenced"**: each Act/Section actually cited gets a `last_referenced_at` timestamp bump, purely for UI sorting/highlighting in Module 5 — no separate write path duplicating citation-graph logic.

**Task 4.1.1**: Implement this fan-out as a single internal event (`ChatResponseFinalized`) emitted once per completed `/chat` call, consumed by four small, independently-testable handlers (audit, graph, research-memory, statute-reference). This keeps `chat.py` itself thin and makes it possible to unit-test "does a citation actually update the graph" without spinning up the whole chat pipeline.

## 4.2 `POST /chat/stream` — SSE token streaming

**Purpose**: same as 4.1 but with visible token-by-token generation, which is also the honest mechanism for the "Legal AI is generating response…" loading state you specifically asked to fix (Img 3's ambiguous "Ingesting PDFs…" ghost-text with no real progress).

**Task 4.2.1**: Stream must emit distinguishable event types, not just raw tokens: `retrieval_started`, `retrieval_completed` (with chunk count found), `generation_token`, `grounding_check_started`, `citation_verified` (per citation, as it's confirmed), `done`. The frontend loading state (Module 6) renders each of these as a distinct, honest status line — this is what separates a real progress indicator from a spinner that just means "something is happening, trust us."

## 4.3 `GET /chat/history/{session_id}` and `GET /memory/conversations`

**Purpose**: reload a past conversation. Per Module 2, this must read from Postgres (system of record), with Redis only as a hot-path cache in front of it — never the reverse.

**Cold-start state**: a new session has zero history rows. The UI's `SessionList.jsx` renders "No conversations yet — start by asking a question" (not the current "No task history." label from Img 1's sidebar, which is close but should be scoped per-vault once Module 2 lands).

## 4.4 `GET /chat/memory/semantic` and `POST /chat/memory/semantic` — L3

**Purpose**: durable user-level facts that aren't case-specific — e.g. "user practices primarily in Karnataka jurisdiction," "user prefers BNS section numbers alongside legacy IPC cross-references." This is what should let the assistant get *contextually* better over repeated use without ever encoding *legal facts* into it — L3 stores user preferences, never statutory content. Enforce this at the validation gate already designed (report.md §7): reject any L3 write that looks like a legal claim rather than a user preference (e.g. block "Section 420 IPC means X" from ever landing in L3 — that belongs in the corpus, not user memory, and letting it in via a chat side-channel would recreate the exact "facts baked outside retrieval" problem the project was founded to avoid).

**Cold-start state**: empty. The assistant behaves identically for every new user until it has real accumulated preference signal — no default persona injected to simulate personalization.

## Acceptance criteria for Module 4
- [ ] A fresh conversation with a query about an unseeded Act returns an honest "not in corpus" response, never a fabricated answer.
- [ ] A single `/chat` call demonstrably produces new rows in the audit ledger, and (when it cites something new) new nodes/edges in the citation graph — verified by making one real call and diffing both stores before/after.
- [ ] SSE stream distinguishes retrieval/generation/grounding phases in the UI, not one generic spinner.
- [ ] L3 semantic memory rejects legal-fact-shaped writes at the validation gate (test with an adversarial "remember that Section X means Y" chat message).
