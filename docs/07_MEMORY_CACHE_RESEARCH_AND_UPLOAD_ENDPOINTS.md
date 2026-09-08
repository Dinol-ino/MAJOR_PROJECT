# Module 7 — Memory, Cache, Research & Upload Endpoints: Purpose & Growth Model

**Scope**: `app/routes/memory.py`, `app/routes/cache.py`, `app/routes/research.py`, `app/routes/upload.py`. These are largely invisible to the end user directly but are what make everything else (Module 4's chat, Module 5's graph, Module 2's Vault) actually durable and fast rather than illustrative.

---

## 7.1 `app/routes/upload.py` — purpose: turn a PDF into something the FSM can retrieve from, visibly

Per your explicit complaint: *"user doesn't understand if the pdf is loaded or not."* This endpoint group's product purpose is not just "accept a file" — it's "accept a file and prove, at every step, that it became usable evidence."

**Task 7.1.1**: `POST /upload` / `POST /upload/batch` must emit the same kind of staged status events as Module 4's chat stream: `received` → `magic_byte_validated` (or rejected — a non-PDF or corrupted file must fail here, loudly, not proceed silently) → `text_extracted` (with a page/character count, so a suspiciously-low count signals the "Broken PDF text extraction" defect from your audit before the user finds out three questions later that their document was never actually readable) → `chunked` (chunk count) → `embedded` → `indexed`. The UI attaches this to the file's pill/chip component (already scoped in the prior Vault spec) so the user watches their specific file, by name, move through these states — not a generic "Ingesting PDFs…" ghost-text (Img 3).

**Task 7.1.2**: `GET /upload/documents/{session_id}` (or the vault-scoped equivalent post-Module 2) is the read side of this — it must reflect the exact same status enum as the upload stream, queried fresh from the DB, so refreshing the page or reopening a vault shows accurate current state, not just the last thing the client happened to see mid-stream.

## 7.2 `app/routes/memory.py` — purpose: expose the 6-layer memory model as something inspectable, not just internal plumbing

**Task 7.2.1**: `GET /memory/conversations`, `GET /memory/documents/{session_id}`, `GET /memory/semantic/{user_id}` should back a real "what does the system remember about me/this case" view — a legitimate legal-tech feature (transparency into what's retained matters for privileged/confidential work), not just internal debug endpoints. Consider surfacing this as a simple panel inside Project Vault settings (Module 2) — "This vault contains: 14 conversations, 6 documents, 3 semantic facts" — each linking to the underlying `DELETE` endpoints already specified, so users have real control, not just visibility.

**Task 7.2.2**: `DELETE /memory/documents/{session_id}/{doc_id}` cascading delete (ChromaDB + BM25 + Postgres) is already correctly scoped per report.md — verify it in practice, not just in the schema: upload a document, delete it, then directly query ChromaDB/BM25 to confirm zero residual chunks. A cascading-delete claim that isn't verified against the actual vector store is exactly the kind of "claimed" item this whole program exists to stop taking on faith.

## 7.3 `app/routes/cache.py` — purpose: prove the caching layer is doing something, and let it be safely reset

**Task 7.3.1**: `GET /cache/metrics` should be wired into a small, honest diagnostics widget (not a dedicated top-level nav item — this is an operator/debug concern, not a lawyer-facing feature) showing real hit/miss ratios for L1/L2/L3. Zero hits on a freshly-started system is correct and should display as such, not be hidden.

**Task 7.3.2**: `POST /cache/clear` must actually invalidate all three bounded LRU caches and be callable safely from Module 6's hardware/model view whenever the corpus version changes (re-ingestion, new Act added) — tie this into Module 5's ingestion pipeline so cache staleness after a corpus update is structurally impossible, not dependent on someone remembering to click clear.

## 7.4 `app/routes/research.py` — purpose: the visible engine behind Deep Thinking mode (Module 2 §2.4)

**Task 7.4.1**: `POST /research/pipeline` is the real backend for Deep Thinking — Module 2 already specifies that Deep Thinking must route through the full FSM rather than a single chat call; this endpoint is where that routing lands. `GET /research/circuit-breaker/status` should be surfaced in the UI whenever a Deep Thinking session is active (a small "system health" indicator during long-running research — e.g. "3/5 tool calls used, 45s/60s budget") so the hard execution ceilings already designed (report.md §9) are visible user-facing information, not just internal safety limits the user discovers only when they're abruptly hit.

**Task 7.4.2**: `POST /research/mode` (OFFLINE/ONLINE toggle) must be the single source of truth consumed by Module 6's MCP gateway mode-flip logic (§6.4.3) — don't let research mode and MCP mode drift into two separately-tracked booleans that can disagree.

## Acceptance criteria for Module 7
- [ ] File upload shows real, per-stage status by filename, including honest failure states for extraction problems.
- [ ] Cascading document delete verified directly against ChromaDB/BM25, not just assumed from the code path.
- [ ] Cache metrics visible and cache is provably cleared on corpus version bump.
- [ ] Deep Thinking sessions show live execution-ceiling telemetry (steps/tools/time used vs. budget).
