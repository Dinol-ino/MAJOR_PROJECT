# Stage 2 — Real Retrieval Quality & Latency

**Depends on Stage 1** (retrieval must be workspace-isolated correctly before you optimize it).

## 2.1 Replace hash-based "embeddings" with real semantic embeddings

**Confirmed evidence:** `.env` currently sets `RETRIEVAL_EMBEDDINGS=local`, which routes to
`LocalHashEmbeddingModel` — a deterministic hash-based bag-of-tokens vector, not a semantic
embedding. `EMBEDDING_MODEL=jinaai/jina-embeddings-v3` is defined in code as the production
default but is not active. This means dense retrieval is currently not doing semantic search at
all — it's keyword-hashing wearing a vector-search interface.

**Task:**
1. Set `RETRIEVAL_EMBEDDINGS=model` in `.env` (keep `local` as the documented test-only override —
   `tests/test_retrieval.py` already forces `local` explicitly to avoid downloads in CI, leave
   that as-is).
2. Confirm `SentenceTransformerEmbeddingModel` in `backend/app/retrieval/embeddings.py` loads
   `jinaai/jina-embeddings-v3` correctly with `trust_remote_code=True` and
   `normalize_embeddings=True` as already coded.
3. **If CPU-only deployment is a real target** (per the offline-first, runs-on-a-laptop goal),
   add a lighter fallback embedding option (`BAAI/bge-small-en-v1.5`, ~130MB, much faster on CPU)
   selectable via `EMBEDDING_MODEL` in `.env` for low-tier hardware — wire this through Stage 4's
   hardware tiering rather than hardcoding one model for everyone.
4. Re-run `scripts/seed_tier1.py` against the new embedding model so Tier-1 law corpus vectors are
   consistent with query-time vectors (mismatched embedding models between ingest and query is a
   silent retrieval-quality killer — verify `model_name` tagging in `chunk_embeddings` prevents
   cross-model comparison, per the existing `index_missing_embeddings` metadata tagging).
5. Add a migration/backfill script: re-embed existing `chunks` rows that currently have
   `model_name="local-hash-1024"` embeddings, since old hash vectors are meaningless once you
   switch to real embeddings — don't leave stale hash vectors mixed into search results.

## 2.2 Stop rebuilding BM25 on every request

**Confirmed evidence:** `backend/app/retrieval/postgres_retrieval.py:136-168`, `_sparse_search`
constructs `BM25Okapi(tokenized_corpus)` fresh from all matching rows on every single call — O(corpus
size) tokenize + index build per chat message.

**Task:**
1. Build a module-level (or Redis/disk-backed, workspace-scoped) BM25 index cache keyed by
   `(corpus_type, workspace_id)`, built once and reused across requests.
2. Invalidate/rebuild the relevant cache entry only on ingest events (new document uploaded to
   that workspace) — hook this into `IngestionService.ingest_file` or `index_missing_embeddings`.
3. If corpus size grows large enough that even cached in-memory BM25 becomes a memory concern,
   note (don't necessarily implement yet) migrating sparse search to Postgres native full-text
   search (`tsvector`/`pg_trgm`) as a future option — flag this as a TODO comment rather than
   scope-creeping this stage.

## 2.3 Warm up all defense/retrieval models at startup, not on first request

**Confirmed evidence:** `backend/app/main.py:14-30`'s `lifespan()` only warms Ollama. The
reranker (`build_reranker()`, `@lru_cache`) and `Layer3OutputGuard` (`get_output_guard()`,
`@lru_cache`) are correctly cached as singletons, but they're lazily instantiated — meaning
whichever request arrives first after a restart pays the full model-load cost
(CrossEncoder + Presidio's spaCy pipeline + NLI model if configured).

**Task:** in `lifespan()`, after the existing Ollama warmup, explicitly call `build_reranker()`
and `get_output_guard()` (and trigger one dummy `.rerank()`/`.validate()` call each) so model
loading happens at container startup, not on the first real user request. Keep the existing
non-fatal try/except pattern — a warmup failure should log and continue, not crash startup.

## 2.4 Add streaming to `/chat`

**Confirmed evidence:** `chat_endpoint` returns a single blocking `ChatResponse`
(`response_model=ChatResponse`); no `StreamingResponse`/SSE path exists anywhere in
`routes/chat.py`.

**Task:**
1. Add a second endpoint, `POST /chat/stream`, using FastAPI's `StreamingResponse` with
   `text/event-stream`, that streams tokens from `OllamaClient` as they're generated (Ollama's
   `/api/generate` already supports `"stream": true` — currently the client always sends
   `"stream": false`).
2. **Important defense constraint:** Layer 3 output validation (grounding/citation/PII) currently
   runs on the complete answer after generation finishes. Streaming raw tokens to the user before
   validation completes would bypass that safety gate. Two acceptable approaches — pick one and
   document the choice:
   - (a) Stream to the client but buffer server-side; only forward tokens once Layer 3 has
     validated the complete answer (defeats some of the latency benefit but preserves the safety
     guarantee), or
   - (b) Stream immediately for `shield_on=false` requests only (already-unvalidated path today),
     and keep `shield_on=true` requests on the existing blocking `/chat` endpoint until a
     stream-compatible incremental grounding check is designed. **Recommended for this stage** —
     don't compromise Layer 3's guarantee to get streaming; ship streaming for the fast/unshielded
     path first.
3. Keep the existing `/chat` endpoint unchanged for backward compatibility with the current
   frontend — this is an additive change, not a replacement of the frozen contract.

## 2.5 Retrieval evaluation harness (needed before Stage 5, useful now)

**Confirmed gap:** no precision/recall/MRR evaluation exists; `attack_suite/run_comparison.py`
only measures block-rate pass/fail, not retrieval quality or latency percentiles.

**Task:** add `tests/eval/retrieval_eval.py`:
1. A small labeled set (20–50 query → expected-section pairs) built from `data/acts_raw/IT_Act.txt`
   content actually in the corpus.
2. Compute recall@5 and MRR before/after the embedding swap in 2.1, so the improvement is measured,
   not assumed.
3. Log p50/p95 latency per stage (retrieval/generation/output_guard — the timing instrumentation
   already exists in `chat.py`'s `latency_ms` dict, this task just needs to persist and aggregate
   it across a batch run rather than log it per-request only).

## Testing for this stage

- `tests/test_retrieval.py` and `tests/test_postgres_retrieval_stage3.py` must still pass with
  `RETRIEVAL_EMBEDDINGS=local` forced (CI stays download-free).
- New `tests/eval/retrieval_eval.py` run manually/CI-optional against real embeddings, not gating
  every PR (it downloads a real model).
- Confirm `attack_suite/run_comparison.py` latency (visible via the "total" timing already printed
  through `latency_ms`) drops after 2.2 and 2.3.
