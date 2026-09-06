# Agent Skill 01 — Engineering Standards

Applies to: all code written or modified across `phase/` and `stages_2/`.

## 1. No hardcoding, no exceptions by convenience

Any value that could plausibly need to change — model names, thresholds, timeouts, retention periods, allowlists, pool sizes — belongs in the config registry (`phase/01_foundation_and_config.md`). If you're about to write a literal constant into application logic, stop and check whether it belongs in `settings.py` or a YAML registry instead. This is enforced by a grep/AST check in CI (Phase 01) — don't write code that would fail it.

## 2. No duplicate subsystems

Before adding new logic, search for an existing implementation of the same concern. If one exists:
- Broken → fix it.
- Working but insufficient → extend it.
- Never: add a second, parallel implementation "to be safe" or because the existing one was hard to find. Phase 15's final regression specifically audits for this — duplicate subsystems found there mean rework, not just cleanup.

## 3. Deterministic before LLM, every time this pattern appears

Multiple phases specify "deterministic rules first, model classifier only if ambiguous" (injection classification, freshness detection, citation verification, tool-selection routing). Implement it that way even when reaching for an LLM call would be faster to write. This isn't a style preference — it's a latency, reliability, and cost requirement that shows up directly in Phase 11's benchmarks and Phase 05's routing table.

## 4. Type and validate at every boundary

- API request/response bodies: typed schemas (Pydantic), not dicts passed through unchecked.
- Tool call inputs/outputs (Phase 08): schema-validated against the tool registry, not free-form.
- Config: validated at load time, app fails to start on invalid config rather than failing at first use.

## 5. Dependency discipline

New pip/npm packages require one of:
- Already listed in `stages_2/09_PREREQUISITES.md`, or
- Explicitly named in the current phase's "Files to Add" / implementation steps.

If a task seems to need something not on either list, flag it rather than installing it unilaterally — new dependencies are a design decision (see `03_HUMAN_APPROVAL_GATES.md`).

## 6. Tests are part of the phase, not a follow-up

A phase's Testing section isn't optional scope — the tests it describes must actually exist and pass before the phase is considered complete. No stubbed tests, no `@skip`, no `xfail` without a tracked reason referencing why and when it'll be fixed.

## 7. Commit hygiene

One phase (or one clearly-scoped sub-task within a phase) per commit or PR where practical, with the commit message referencing the phase file and section implemented (e.g. `phase/07: implement injection hard gate, item 6`). This is what makes Phase 15's audit and any future rollback actually tractable — a commit history that can't be mapped back to phase sections defeats the purpose of having them.

## 8. Match existing code style

Preserve the existing project's formatting, naming conventions, and idioms per file/module unless a phase explicitly calls for restructuring. Consistency with what's already there beats introducing a new personal style mid-codebase.
