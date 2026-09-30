# DFrag stabilization audit (2026-09-30)

Scope: targeted refactor of the existing system, no rebuild. Verified by 386 backend tests (hermetic).
NOT verified here: Docker builds beyond the user's own `docker compose up` (backend healthy),
Ollama generation quality/latency, live external APIs, and the production compose/nginx files.

## Fixed
| Area | Problem | Fix |
|---|---|---|
| Persistence | Originals were not kept; indexes were the only copy | Canonical store (`VAULT_FILES_DIR`, atomic writes); reindex/restart rebuild from the original; soft vault delete keeps files |
| Citations | Page provenance missing; "Page N" shown as a section | Page-aware chunks, `source_kind`/`doc_id`/`page_start` in citations, UI badges |
| Isolation | `/chat/stream` skipped auth/ownership; MCP tool-call, `/mcp/history`, `/memory/documents`, session uploads were cross-user readable | Ownership on every path; session claim; history scoped; regression tests |
| Egress | A cloud fallback could receive private vault text | ContextVar egress guard; cloud runtime refuses private context |
| Graph | Vault scope without an id showed global data | Empty state |
| Relevance | Off-topic questions matched "closest" statutes | idf-weighted term-coverage gate |
| Sanitizer | Invisible/confusable characters, tag breakout | NFKC + confusable folding; `<>` neutralised in chunks |
| Validator | Named Acts passed when no evidence was retrieved | Fail closed |
| Model | Cold model reloads | `keep_alive`; provisioning preflight |
| UI | Hardcoded "Verified current (2026)" | Honest verification badge |
| Schema | New columns only via runtime patch | Alembic `20260930_0002` |

## Added
Bounded LangGraph retrieval planner (flag, off by default); eCourtsIndia connector; laws-of-india importer;
prod frontend image + compose override (untested).

## Known limitations
- Statute text is unverified (community conversion); repealed IPC/CrPC/IEA are labelled as such.
- Lexical relevance gate and `vault_dense_min_score` (0.6) are heuristics, uncalibrated on real matter files.
- Planner is deterministic regex; there is no model-based router because it cannot be evaluated without Ollama.
- Performance numbers in `report.md` are unmeasured claims.
- L3 grounding is token-overlap, not entailment; section-level citation verification is open.
- Scraping court portals (captchas, ToS) and bulk case-law ingestion were deliberately not done.

## Found by driving the real app with Playwright (2026-09-30)
| Finding | Fix |
|---|---|
| Upload showed "Indexed" but the sidebar still said "0 doc / No PDFs yet" | Sidebar refreshes after every upload; covered by `e2e/vault_persistence.spec.ts` (real backend, reload, original download) |
| "Section 138 of the Negotiable Instruments Act" returned Section 20; "Section 420 IPC" returned nothing | Deterministic Act+section lookup ahead of ranking (`retrieval/structured_lookup.py`); same number in another Act is dropped; unknown Act returns nothing |
| Off-topic vault question ("capital of France") cited an old Act that mentions France | Vault questions with no legal subject no longer pull statutory text |
| Stale provenance e2e test asserted "Active Settled Law" | Test now expects the honest backend status |
| Developer wording ("Sync MCP", "In-Process DB") shown to lawyers | Renamed |
| Duplicate style key in CitationGraphView (build warning) | Removed |
Run locally: `cd frontend && npx playwright test` (backend on :8000, OFFLINE, temp stores; see .github/workflows/ci.yml).

## Measured performance (backend/scripts/measure_performance.py)
Sandbox CPU, lexical BM25 only (embedding model could not be downloaded there, so dense search was OFF). Re-run on your hardware; do not quote these as your numbers.

| Measure | Result |
|---|---|
| Index 12 Acts / 1,676 sections | 1.9 s |
| Statute query, cold (p50 / p95) | 9.2 ms / 12.7 ms |
| Statute query, cached | 0.02 ms |
| Ingest a 60-page PDF into a vault | 0.15 s |
| Vault query (p50 / p95) | 2.9 ms / 25 ms |

Generation latency is the real bottleneck and is unmeasured (needs Ollama). Nothing in retrieval is worth optimising before that is measured.

## Cache and store classification
| Store | Class | May be evicted / rebuilt? |
|---|---|---|
| Original PDFs (`VAULT_FILES_DIR`) | AUTHORITATIVE | Never automatically; only explicit delete |
| DB rows (vaults, documents, pages, chats, users) | AUTHORITATIVE | Never |
| Audit ledger | AUTHORITATIVE, tamper-evident | Never |
| Chroma vectors, BM25 index | DERIVED | Yes; rebuilt from originals (`/reindex`, restart recovery) |
| L1 process cache, L2 retrieval cache, L3 embedding cache | DISPOSABLE | Yes; TTL/clear at any time, keyed by corpus version |
| Loaded model / `keep_alive` | RUNTIME | Yes; reloads on next request |
Consequence: cache eviction, index rebuild, container restart, model switch, chat reset and app restart never delete a lawyer's originals.

## Section-name check
An answer that names "Section N" in prose which is not among the retrieved sources now gets a visible caution (`unsupported_section_mentions`). Advisory, not blocking; token citations are still verified against evidence.
