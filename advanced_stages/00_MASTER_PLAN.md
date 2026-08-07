# DFrag Rebuild — Master Plan

This is a **modification plan, not a rewrite**. Every stage below patches or extends existing
files confirmed present in the repository (see `inspection_report.md`). No stage deletes the
existing directory structure. No stage should require redoing a previous stage's work.

## Ground rules for whoever executes these stages

1. **Read the target files before editing them.** Every task below names exact files and, where
   known, exact functions. Confirm current content matches what's described before changing it —
   if it doesn't match, stop and report the discrepancy instead of guessing.
2. **No silent schema changes.** If a stage requires a new DB column, table, or API field, it must
   go through an Alembic migration, not a manual edit assumed at runtime.
3. **No hardcoded values where a config value already exists.** Use `settings.*` from
   `backend/app/config.py`; add new settings there rather than inlining constants.
4. **Preserve existing fallback behavior.** The codebase already has a good instinct (dense→sparse→
   Chroma fallback, Ollama→Transformers→Mock fallback). Extend this pattern to new components —
   never replace a fallback with a hard failure.
5. **Every stage ends with tests passing.** Run `pytest` in `backend/` and the existing
   `attack_suite/run_comparison.py` before considering a stage done. Add new tests for new
   behavior in the matching `tests/test_*.py` file — don't create a parallel test structure.
6. **Update `architecture.md` and `README.md` at the end of each stage** so the docs reflect
   what is actually running, not an aspirational diagram.

---

## Stage Order and Dependency Chain

| Stage | Name | Focus | Depends on | Must not break |
|-------|------|-------|------------|----------------|
| 1 | Security & Platform Foundation | Auth, session isolation, workspace scoping | none | existing auth/session tests |
| 2 | Ingestion & PageIndex | Real embeddings, BM25, Postgres retrieval, eval harness | Stage 1 | Stage 1 isolation fix |
| 3 | Retrieval & Ranking | Hybrid retrieval, trust scoring, persistent memory | Stage 1 | Redis session behavior |
| 4 | Defense & Trust | Input guards, output guards, classifier, trust scorer | Stages 1–3 | recommend.py contract shape |
| 5 | Intelligent Runtime & Knowledge Orchestration | Hardware detection, model registry, runtime abstraction (Ollama / llama.cpp / Transformers), context builder, token budget, streaming, citation, hallucination detection, confidence scoring, permanent user memory | Stages 1–4 | All frozen API contracts |
| 6 | Enterprise Deployment & Operations | Docker, CI/CD, RBAC, admin API, health monitoring, Prometheus metrics, structured logging, backup/restore, environment profiles, Kubernetes-ready design | Stages 1–5 | docker-compose.yml existing services |
| 7 | Enterprise Knowledge Ecosystem | Connector architecture, 10-stage ingestion pipeline, live sync service with change detection and versioning, knowledge store, user knowledge permanence | Stages 1–6 | Stage 2/3 retrieval interface |

**Stages 1–4** make the product correct, secure, and fast.
**Stage 5** makes it runtime-intelligent and model-agnostic.
**Stage 6** makes it deployable and operable by a team.
**Stage 7** makes the knowledge base live, authoritative, and self-updating.

---

## The Architecture Principle That Cannot Move

**Knowledge must never live inside the LLM.**

All legal facts, statutes, judgments, and user documents are stored in the retrieval layer
(pgvector + ChromaDB fallback). When law changes, the knowledge store is updated. The model
is never retrained. The model may be swapped for a better one without any knowledge loss
because the knowledge is not in the model — it is in the retrieval layer.

Fine-tuning, LoRA adapters, and adapter training are explicitly outside this architecture.
They are excluded by design because they couple the knowledge lifecycle to the model lifecycle.
This coupling is the failure mode of research prototypes. Enterprise platforms do not have it.

---

## What NOT to do in Any Stage

- Do not write knowledge into model weights. Facts stay in retrieval permanently.
- Do not remove the ChromaDB legacy fallback path until Stage 2's Postgres retrieval has been
  running clean in production for a defined burn-in period — it is the safety net during cutover.
- Do not change the frozen API contract (`/chat`, `/upload`, `/recommend`, `/audit/{session_id}`)
  without adding a new versioned field rather than repurposing an existing one.
- Do not allow any connector to write directly to the vector database — everything must pass
  through the Stage 7 ingestion pipeline.
- Do not make the LLM a dependency for knowledge updates — the sync service must be able to
  ingest new knowledge without invoking any LLM.
