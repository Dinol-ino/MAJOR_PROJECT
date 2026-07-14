# Stage 6: Memory, Observability, and Admin Controls

## Objective

Add the operational layers that make the system maintainable and measurable without distracting from the core pipeline too early.

## Target state

- `Redis` stores short-lived chat/session memory
- `Langfuse` captures traces, retrieval quality, latency, and evaluation results
- a light model catalog exists for approved models
- the audit chain remains intact as the legal traceability layer

## Memory model

### Persistent memory

- PostgreSQL + pgvector
- chunks
- embeddings
- metadata
- law corpus
- user corpus

### Session memory

- Redis
- recent turns
- retrieval references
- active context window state

### Raw file memory

- uploaded originals
- OCR output
- extracted intermediate artifacts

## Observability scope

Langfuse should capture:

- request trace ids
- retrieval candidate sets
- reranker decisions
- block or quarantine reasons
- latency by stage
- user feedback if added later

## Model registry scope

Keep it intentionally small at first:

- approved model name
- task type
- runtime backend
- context window
- embedding dimension if applicable
- hardware note
- license note

Do not build a full admin dashboard yet unless the core path is already stable.

## Required installs

- Langfuse deployment
- Langfuse SDK
- Redis client

## Required `.env` values

- `LANGFUSE_HOST`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_ENABLED`
- `SESSION_TTL_SECONDS`

## In scope

- memory-tier separation
- tracing contract
- evaluation instrumentation
- minimal approved-model catalog design

## Out of scope

- arbitrary model download UI
- advanced RBAC
- multi-tenant admin console

## Exit criteria

- Session memory is separated cleanly from document memory.
- Core pipeline steps are traceable end to end.
- Approved models are cataloged without opening unsafe arbitrary model swapping.
