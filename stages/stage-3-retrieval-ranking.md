# Stage 3: Retrieval and Ranking

## Objective

Consolidate the search stack around one dense embedding model, one vector store, one sparse path, and one reranking step.

## Target state

- Dense embeddings: `jina-embeddings-v3`
- Vector storage: `pgvector`
- Sparse retrieval: `BM25` or PostgreSQL full-text search, with one approved implementation only
- Fusion: `RRF`
- Reranking: `BAAI/bge-reranker-large`

## Architecture decisions

1. Remove the multi-embedding temptation.
   - no `bge-small-en`
   - no parallel embedding families
   - one embedding dimension standard for all chunks
2. Keep hybrid retrieval because legal queries need both:
   - exact section/act matching
   - semantic matching
3. Apply reranking after fusion, not before.
4. Use one chunk schema across both law corpus and user corpus.

## Retrieval scoring model

Base retrieval can stay:

- dense similarity
- sparse lexical score
- fused RRF score

Then reranker score becomes the final ordering input before context assembly.

## Required installs

- access to `jinaai/jina-embeddings-v3`
- access to `BAAI/bge-reranker-large`
- tokenizer/runtime support for both models

## Required `.env` values

- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `RERANKER_MODEL`
- `RETRIEVAL_TOP_K`
- `RERANK_TOP_N`
- `SPARSE_SEARCH_MODE`

## In scope

- retrieval schema mapping in PostgreSQL
- vector dimension freeze
- fusion strategy
- reranking insertion point
- law corpus and user corpus unification

## Out of scope

- query firewall classification
- answer generation
- PII scanning
- observability

## Risks

1. `jina-embeddings-v3` is stronger but heavier than the current embedding path, so hardware validation matters before cutover.
2. Reranking adds latency and must be measured before becoming the default in all paths.
3. Sparse search should not be duplicated in both app code and database code unless one is clearly primary.

## Exit criteria

- One approved dense model exists.
- One approved sparse path exists.
- One approved reranker exists.
- Retrieval can return ranked chunks with page-level metadata ready for trust scoring.
