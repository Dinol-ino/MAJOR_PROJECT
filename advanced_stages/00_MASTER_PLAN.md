# DFrag Rebuild — Master Plan

This is a **modification plan, not a rewrite**. Every stage below patches or extends existing
files confirmed present in the repository (see `inspection_report.md`). No stage deletes the
existing directory structure. No stage should require redoing a previous stage's work.

## Ground rules for whoever executes these stages (Codex / Antigravity)

1. **Read the target files before editing them.** Every task below names exact files and, where
   known, exact functions. Confirm current content matches what's described before changing it —
   if it doesn't match, stop and report the discrepancy instead of guessing.
2. **No silent schema changes.** If a stage requires a new DB column, table, or API field, it must
   go through an Alembic migration, not a manual edit assumed at runtime.
3. **No hardcoded values where a config value already exists.** Use `settings.*` from
   `backend/app/config.py`; add new settings there rather than inlining constants.
4. **Preserve existing fallback behavior.** The codebase already has a good instinct (dense→sparse→
   Chroma fallback, Ollama→Transformers→Mock fallback). Extend this pattern to new components
   (hardware detection, model pulling) — never replace a fallback with a hard failure.
5. **Every stage ends with tests passing.** Run `pytest` in `backend/` and the existing
   `attack_suite/run_comparison.py` before considering a stage done. Add new tests for new
   behavior in the matching `tests/test_*.py` file — don't create a parallel test structure.
6. **Update `architecture.md` and `README.md` at the end of each stage** so the docs stop lying
   about what's actually running (this was the biggest issue found in the audit — the diagrams
   currently describe an aspirational system, not the real one).

## Stage order and dependency chain

| Stage | Focus | Depends on | Must not break |
|---|---|---|---|
| 1 | Security & isolation fixes | none | existing auth/session tests |
| 2 | Real retrieval quality (embeddings, BM25 cache, warmup, streaming) | Stage 1 (auth-scoped retrieval) | Stage 1's isolation fix |
| 3 | Persistent memory (Postgres transcript, ownership binding) | Stage 1 | Redis session behavior |
| 4 | Hardware detection & dynamic model management | none (independent) | recommend.py's existing contract shape |
| 5 | Fine-tuning / LoRA pipeline (optional, behavior-only) | Stage 2 (needs real embeddings/eval harness) | base model behavior when adapter absent |
| 6 | Deployment packaging (Docker installer path + lightweight desktop path) | Stages 1–4 | docker-compose.yml existing services |

Stages 1–4 are the ones that make the product **correct and fast**. Stage 5 is the one that makes
it **smarter**, and it's optional — ship without it first. Stage 6 is what makes it **installable
by someone who isn't you**.

## What NOT to do in any stage

- Do not fine-tune the base model on legal *facts*. Facts stay in retrieval, permanently. Only
  Stage 5's adapter touches *behavior* (format, citation discipline, refusal), never knowledge.
- Do not remove the ChromaDB legacy fallback path until Stage 2's Postgres retrieval has been
  running clean in production for a defined burn-in period — it's your safety net during cutover.
- Do not change the frozen API contract (`/chat`, `/upload`, `/recommend`, `/audit/{session_id}`)
  without adding a new versioned field rather than repurposing an existing one — clients (including
  the existing frontend) depend on the current shape.
