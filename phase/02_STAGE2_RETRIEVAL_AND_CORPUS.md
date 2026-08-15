# Stage 2 — Retrieval Quality, Latency, and Corpus Acquisition/Currency

Retrieval quality work is meaningless over an incomplete or stale corpus, so corpus acquisition is part of this stage, not deferred to later. Complete corpus work before declaring retrieval-quality work "done."

## Part A — Retrieval Engine Fixes

### A1. BM25 caching
- Audit finding: BM25 sparse index rebuilt from scratch on every query.
- Fix: build/maintain the BM25 index incrementally, persisted, invalidated and rebuilt only on corpus write (new/changed document), never on query.
- Acceptance: query-time BM25 search does not trigger a full index rebuild; rebuild only fires on ingestion events.

### A2. Embedding model correction
- Audit finding: active embedding model is a hash-based placeholder, not the semantic model named in architecture docs.
- Fix: replace with **InLegalBERT** (`law-ai/InLegalBERT`) as the production embedding model for both corpus documents and queries.
- Re-embed the full existing corpus after swapping the model — a mixed corpus of placeholder-hash and InLegalBERT embeddings is not usable for similarity search.
- Acceptance: embedding vectors are produced by InLegalBERT for 100% of stored corpus entries; no hash-placeholder vectors remain in pgvector.

### A3. Hybrid retrieval
- Combine BM25 (sparse, good for exact statute/section number matches) with pgvector dense search (InLegalBERT, good for semantic/conceptual queries) via rank fusion (e.g. reciprocal rank fusion).
- Acceptance: a query using an exact section number and a query using natural-language paraphrase of the same provision both retrieve the correct document in top-3.

### A4. Metadata-filtered retrieval
- Every retrieval query filters on: `jurisdiction` (unless explicitly cross-jurisdiction), `superseded_by IS NULL` (exclude repealed/overturned provisions unless historical context is explicitly requested), `effective_date <= query context date` (default: now).
- Acceptance: a provision marked `superseded_by` a newer document is not returned as current law in a standard query.

## Part B — Corpus Acquisition & Currency (new subsystem)

### B1. Source clearance (human decision, blocking)
- Before any bulk ingestion: document which sources are cleared for scraping. Preferred: India Code (indiacode.nic.in / legislative.gov.in) for statute text — official, government-published. Court sources per-court (check individual availability/terms). Do not default to IndianKanoon for bulk scraping without confirming current terms allow it.
- This is a documented decision in the repo, not an inferred default.

### B2. Ingestion pipeline
```
[Scheduled trigger] -> [Fetch: direct HTTP where possible; Playwright only for JS-rendered pages]
  -> [Stage 1 PDF sanitization — mandatory, not bypassed for bulk ingest]
  -> [Stage 1 PII scanner — mandatory, unconditional]
  -> [Diff against stored version -> flag changes for review, no silent overwrite]
  -> [Chunking]
  -> [Embed via InLegalBERT]
  -> [Write to pgvector with full metadata schema below]
  -> [Invalidate/update BM25 index]
```

### B3. Metadata schema (per document, enforced at write time)
```
document_id, source_url, source_authority, jurisdiction,
document_type (act|amendment|judgment|rule),
enactment_date, effective_date, amendment_history[],
superseded_by (nullable), last_verified_at, ingestion_hash
```

### B4. Re-crawl cadence
- Statutes: scheduled re-check (e.g. monthly) via cron/Celery-beat.
- Case law sources: more frequent if source supports it.
- On re-crawl: compute `ingestion_hash` of fetched content, compare to stored hash. If changed, flag for review — do not auto-replace embeddings for a changed legal provision without a review step.

### B5. Conflict resolution rule
- Official government source wins for statute text. Court's own publication wins for judgment text. Any other conflict → flagged for manual resolution, never resolved by "most recent scrape timestamp" alone.

### B6. Acceptance for Part B
- A sample statute ingested via this pipeline has complete metadata, passes sanitization/PII checks, and is retrievable via both BM25 and dense search.
- Re-running the crawl against an unchanged source produces zero flagged diffs; against a deliberately modified source produces exactly one flagged diff, no silent overwrite.

## Exit criteria for Stage 2
Parts A and B both pass acceptance. Feed retrieval-quality test cases (exact-match, paraphrase, superseded-provision-exclusion) into `07_EVAL_HARNESS.md` as part of the RAGAS context precision/recall suite.
