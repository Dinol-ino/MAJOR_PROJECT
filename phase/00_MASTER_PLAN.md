# DFrag — Master Plan (stages_2)

Local-first, defense-hardened legal RAG system for Indian law. Read this file first; it is the source of truth for stage order, architecture, and model tiering. Each numbered file in this folder is one stage — execute in order unless marked parallel. Do not skip a stage's acceptance criteria to start the next.

## Non-negotiable system properties (apply to every stage)

1. **Retrieval-grounded only.** No answer is generated without citing retrieved context. If retrieval returns nothing relevant, the system refuses rather than answers from parametric knowledge.
2. **Legal facts never enter model weights.** Fine-tuning (Stage 5) is behavior-only — citation discipline, structured output, refusal. All legal facts live in pgvector/BM25, permanently, versioned.
3. **Injection risk is a hard gate**, not an additive trust score. A query that fails the injection check is blocked before it reaches retrieval or generation — it does not proceed with a lowered score.
4. **Local-first, no silent network calls.** No component (validators, eval judges, embedding services) sends document or query content off-device by default. Every dependency that could call out must be explicitly audited before use.
5. **No hardcoded values where dynamic detection is possible** — model selection, hardware tier, corpus freshness are all runtime-determined, not fixed constants.
6. **Every finding/task must trace to actual code or an explicit spec in this folder** — no inferred requirements.

## Architecture (text diagram)

```
┌─────────────────────────────────────────────────────────────────────┐
│                            USER (Tauri / Web)                        │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ session-authenticated request
┌───────────────────────────────▼───────────────────────────────────────┐
│  INPUT LAYER                                                          │
│  - Auth (identity-based session isolation, not client session_id)    │
│  - Rate limiting                                                     │
│  - Layer 1: injection classifier (fast, e.g. Prompt Guard / Hlyn)    │
│  - Layer 1.5: secondary injection check (only if Layer 1 ambiguous — │
│    run ONCE per query, cached on query hash, never duplicated)        │
│  - HARD GATE: fail closed, no downstream processing on fail          │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────────┐
│  RETRIEVAL LAYER                                                      │
│  - BM25 (cached index, invalidated on corpus write, not per-query)   │
│  - pgvector dense search (InLegalBERT embeddings)                    │
│  - Hybrid rank fusion                                                │
│  - Metadata filter: jurisdiction, effective_date, NOT superseded     │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ context chunks + provenance
┌───────────────────────────────▼───────────────────────────────────────┐
│  CONTEXT CONTROL                                                      │
│  - Context sanitization (strip embedded instructions from retrieved  │
│    text before it reaches the prompt — retrieved content is          │
│    untrusted input, same as user input)                              │
│  - Context assembly against frozen prompt template (Stage 4 file)    │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────────┐
│  GENERATION LAYER                                                     │
│  - Local model via Ollama, tier selected by hardware detection       │
│  - System prompt enforces citation format, refusal-when-ungrounded   │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────────┐
│  OUTPUT VALIDATION LAYER                                              │
│  - Guardrails: structured schema (answer/citations/confidence)       │
│  - Deterministic entity/token overlap scorer (replaces LLM self-     │
│    grounding) — fail closed, retry once, then refuse                 │
│  - Citation-existence check against pgvector metadata                │
│  - PII-in-output check (defense-in-depth, does not replace ingest    │
│    PII scanner)                                                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────────┐
│  MEMORY (parallel to the request path, not blocking it)              │
│  - Redis: short-term session context (TTL)                           │
│  - Postgres: durable transcript memory + corpus provenance tables    │
│  - pgvector: knowledge corpus (Indian law, versioned)                │
└─────────────────────────────────────────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────────┐
│  MONITORING / AUDIT LOG                                              │
│  - Every request: injection score, retrieval hits, citations used,   │
│    validation pass/fail, model tier used, latency breakdown per layer │
└─────────────────────────────────────────────────────────────────────┘
```

## Stage index (execute in this order)

| Stage | File | Parallel-safe? | Depends on |
|---|---|---|---|
| 1 | `01_STAGE1_SECURITY_AND_VALIDATION.md` | No | — |
| 2 | `02_STAGE2_RETRIEVAL_AND_CORPUS.md` | No | Stage 1 |
| 3 | `03_STAGE3_MEMORY_ARCHITECTURE.md` | Yes, can overlap Stage 2 tail | Stage 1 |
| 4 | `04_STAGE4_HARDWARE_MODEL_MANAGEMENT.md` | No | Stage 2 |
| 5 | `05_STAGE5_FINETUNING.md` | No | Stages 1–4 stable |
| 6 | `06_STAGE6_DEPLOYMENT.md` | No | Stages 1–5 |
| — | `07_EVAL_HARNESS.md` | **Yes — start at Stage 1, run continuously** | — |
| — | `08_SYSTEM_PROMPT.md` | Reference doc, used from Stage 1 onward | — |

## Model tiering (3B–15B target, hardware-selected)

| Tier | Params | Example models | Trigger condition | Notes |
|---|---|---|---|---|
| **Tier 0 (floor)** | 3B | Llama-3.2-3B-Instruct, Phi-3-mini | Detected <8GB usable RAM/VRAM, or default fallback | Must remain fully functional — this is the guaranteed baseline (matches current dev laptop). Never assume a higher tier is available. |
| **Tier 1** | 7–8B | Mistral-7B-Instruct, Llama-3.1-8B, **SaulLM-7B** (legal-tuned, preferred if fits) | 8–16GB usable RAM/VRAM | SaulLM-7B preferred over generic 7B when hardware allows — it's legal-domain-tuned, reduces reliance on prompt-only legal framing. |
| **Tier 2** | 13–15B | Mistral-Small variants, Llama-2-13B class, quantized 15B-class models | >16GB usable RAM/VRAM or discrete GPU with sufficient VRAM | Optional ceiling tier for contributors/users with stronger hardware. Not required for the product to function. |

Tier selection is fully automatic (Stage 4) — never a hardcoded default, never left to a user-typed form value alone.

## Encoder models (retrieval, not generation)

- **InLegalBERT** — primary retrieval embedding model, replaces the current hash-based placeholder (audit finding, fixed in Stage 2).
- **Legal-BERT** — optional secondary use for classification/NER tasks if a concrete need is identified (document type classification, redaction NER) — not added speculatively.

## Security/injection models

- **Layer 1**: Meta Prompt Guard 86M (or ProtectAI DeBERTa-v3-v2) — fast, local, CPU-viable.
- **Layer 1.5**: same or a second independent classifier, run only once per unique query (deduped by query hash) — the audit found this currently runs twice on unchanged input; that must not recur under the new architecture.

## What is explicitly excluded from this architecture

- AirLLM (no runtime path — latency-incompatible with local-first, low-latency constraints).
- Fine-tuning on legal PDF content (facts stay in retrieval, permanently — see Stage 5 for the correct, narrow fine-tuning scope).
- Any Guardrails/eval/embedding component that calls a remote API by default.
