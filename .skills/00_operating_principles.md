# Agent Skill 00 — Operating Principles

Applies to: every phase in `phase/` and `stages_2/`, for the entire duration of execution.

This file governs how the agent works, not what it builds. Read this before starting Phase 00 and re-apply it continuously — it doesn't expire after the first read.

## 1. No fake completeness — the rule this whole project is named after

`report.md` claimed a fully functional, audited system that turned out to be mixed. Do not reproduce that failure mode from the other direction. A phase, task, or acceptance criterion is only "done" when:
- The actual validation command was run.
- Its actual output is shown or summarized accurately (not paraphrased optimistically).
- Every acceptance criterion in the phase file is checked individually — "mostly working" is not "done."

If something is partially done, say so exactly: which criteria passed, which didn't, what's blocking the rest. Partial honest status is always acceptable. False "complete" status is never acceptable.

## 2. Ground truth beats documentation

Phase files are a plan, written without repository access. When actual code contradicts a phase file's assumption:
- Actual code wins.
- Update `phase/00_VERIFICATION_MANIFEST.md` to reflect the real state.
- Do not silently rewrite the phase file to match broken code, and do not silently proceed as if the phase file's assumption was correct — flag the discrepancy if it changes what the phase should do.

## 3. Verify before you claim, inspect before you edit

- Never state a file path, line number, or function name from memory or inference — view the actual file first.
- Never assume a dependency, table, or endpoint exists because an earlier phase file said it would be added — confirm it landed.
- If Phase 00's manifest doesn't cover something you need to know, inspect it yourself and add the finding to the manifest rather than guessing.

## 4. Sequential, dependency-respecting execution

- Execute phases in the dependency order stated in `phase/00_architecture_audit.md` §10. Don't skip ahead because a later phase looks easier or more interesting.
- Don't start phase N+1 until phase N's acceptance criteria are verifiably met.
- If you believe a different order is genuinely better, document the reasoning and flag it — don't silently reorder.

## 5. Minimal footprint

- Change only what the current phase's "Files to Modify" / "Files to Add" sections call for.
- Opportunistic refactors ("while I'm in here...") are a separate, explicitly-scoped task — not something bundled silently into an unrelated phase's commit.
- If you find a genuine bug or improvement opportunity outside current scope, note it (e.g. in the phase's implementation notes or a tracked issue) rather than fixing it inline.

## 6. Preserve rollback

Every phase file has a Rollback section for a reason. Implement changes so that section remains true — if your implementation approach would make rollback harder than the phase file describes, that's a signal to reconsider the approach, not to quietly accept the risk.

## 7. Ask rather than assume, on the things that matter

Most ambiguity should be resolved with a sensible default and a documented assumption — don't stall on small things. But see `03_HUMAN_APPROVAL_GATES.md` for the specific list of things that are never resolved by assumption, regardless of how confident you are.
