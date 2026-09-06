# Agent Skill 04 — Verification & Reporting Protocol

Applies to: how progress gets reported, for every phase, every task, every session.

## 1. "Done" requires evidence, not a description

When reporting that a task or acceptance criterion is complete, include:
- The actual command run (from the phase file's Validation Commands section, or the specific test invoked).
- Its actual output — real pass/fail counts, real error messages if any, not a summary that rounds failures up to success.

"Should be working now" is not a completion report. "Ran `pytest backend/tests/security/test_hard_gate.py -v`, 12 passed, 0 failed" is.

## 2. Every file/line reference must come from actually viewing the file in this session

Not from the phase file's example paths (those are proposed, not verified — `phase/00`'s own framing), not from memory of a similar codebase, not from inference about where something "probably" is. View it, then reference it.

## 3. Manifest is a living document, not a one-time artifact

If work in a later phase reveals that `phase/00_VERIFICATION_MANIFEST.md`'s earlier verdict on something was wrong (marked PARTIAL but actually absent, or vice versa), update the manifest and note why the earlier verdict was incorrect. Don't proceed on a manifest entry you now know to be stale.

## 4. Report partial completion accurately

For each phase, report:
- Which acceptance criteria passed (with evidence per §1).
- Which didn't, and specifically why (blocked by a human approval gate, a discovered dependency issue, ambiguity that needs resolving, or genuine remaining work).
- What would need to happen to close the gap.

Partial-but-accurate status is always fine. Rounding partial up to complete is the exact failure mode this whole project restructuring exists to fix — treat it as seriously as a security violation, because in a legal-accuracy system, false confidence in completeness has similar downstream consequences to false confidence in a legal answer.

## 5. Flag internal inconsistencies rather than silently resolving them

If two phase files appear to claim authority over the same resource (e.g. both describe adding a column with the same name for different purposes to the same table), or a later phase's instructions seem to contradict an earlier phase's already-implemented decision, stop and flag it. Don't pick one interpretation silently and proceed — these inconsistencies are exactly what `phase/00`'s "no phase may contradict another" rule was meant to prevent, and if one slipped through, it needs a human decision on which is authoritative.

## 6. Keep a build-time decision trail

Beyond the runtime system's own audit logging (Phase 07's L6 ledger, which records what the *product* does), the agent's own significant build-time decisions should be visible — in commit messages or a running changelog — not only inside the agent's own reasoning. Examples worth recording: "deferred L4/L5 caching per Phase 04's rejection reasoning," "chose ProtectAI DeBERTa-v3-v2 over Prompt Guard to avoid HF gating friction," "Phase 00 manifest updated: MCP tools view found to call gateway directly with no policy check, verdict changed from PARTIAL to VERIFIED-ABSENT for policy engine specifically."

## 7. When a phase's own tests fail, the phase failed — not the test

If a test written per a phase's Testing section fails, the default assumption is the implementation is incomplete or wrong, not that the test itself is miscalibrated. Only conclude the test is wrong after genuinely confirming the implementation is correct against the phase's stated intent — and if that happens, fix the test transparently (noting why), don't quietly delete or loosen it.
