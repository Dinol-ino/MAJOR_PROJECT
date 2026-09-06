# Phase 16 — Final Local Release Gate

Depends on: Phase 15 (integration/regression passed)
Blocks: nothing — this is the terminal phase
Modifies: nothing
Introduces: the release gate checklist itself, as a repeatable artifact for future releases
Validates: release readiness, binary — either every item below passes or the release does not ship

## Objective
A hard, objective gate. DFrag is not "done" because a phase file says so — it's done when every item below is independently verified true.

## Gate Checklist

### Functional
- [ ] Core chat works (verified: Phase 13 E2E)
- [ ] Uploads work, including malicious-PDF sanitization path (Phase 07, 13)
- [ ] Retrieval works — hybrid + PageIndex fusion (Phase 06)
- [ ] Memory works — all 6 layers, isolation verified (Phase 03)
- [ ] PostgreSQL works — pooling, migrations, restart recovery (Phase 02)
- [ ] Model routing works — correct tier per task, OOM fallback (Phase 05)
- [ ] MCP works — policy-gated, no direct-dispatch path remains (Phase 08)
- [ ] Offline mode works — OS-level network block test passed (Phase 10, 15)
- [ ] Online mode works when enabled — allowlist enforced (Phase 10)
- [ ] Citations work — full provenance, no fabrication (Phase 07, 10)
- [ ] Audit works — hash-chain verified, tamper-detection tested (Phase 07)

### Security
- [ ] Prompt injection tests pass — hard gate confirmed, not additive (Phase 07, 12)
- [ ] Indirect injection tests pass — retrieved/MCP content sanitization confirmed (Phase 07)
- [ ] PII tests pass — unconditional ingest scan + output check (Phase 07)
- [ ] Cross-session/cross-user isolation passes (Phase 03, 15)
- [ ] Tool authorization tests pass — unauthorized calls rejected (Phase 08)
- [ ] Offline network isolation passes — OS-level, not just app-config (Phase 15)
- [ ] Malicious MCP result tests pass — sanitizer effectiveness confirmed (Phase 08)

### AI Quality
- [ ] Retrieval benchmarks pass — Recall@K/Precision@K/MRR/nDCG meet Phase 11-derived targets (Phase 06, 12)
- [ ] Grounding benchmarks pass — faithfulness score meets target, trend non-declining (Phase 12)
- [ ] Citation verification passes — existence + overlap checks (Phase 07)
- [ ] Hallucination tests pass — adversarial + curated set (Phase 12)

### Performance
- [ ] Latency benchmarks pass — against Phase 11's real, benchmarked targets (not invented numbers)
- [ ] Memory benchmarks pass — Tier 0 floor hardware specifically tested
- [ ] Cache benchmarks pass — hit rate meets expectation, no cross-user leakage (Phase 04)
- [ ] Concurrency tests pass — pool behavior under simultaneous requests (Phase 02, 11)
- [ ] OOM recovery passes — graceful fallback confirmed (Phase 05)

### Persistence
- [ ] PostgreSQL migrations pass — clean `alembic upgrade head` (Phase 02)
- [ ] Transaction tests pass — no partial-write corruption (Phase 02)
- [ ] Restart recovery passes — zero data loss for committed transactions (Phase 02)
- [ ] Memory persistence passes — all 6 layers survive restart appropriately per their policy (Phase 03)
- [ ] Deletion/retention tests pass — L3/L4 deletion cascades correctly (Phase 03)

### Frontend
- [ ] Production build passes
- [ ] Playwright critical flows pass (Phase 13)
- [ ] Streaming works — TTFT and incremental rendering confirmed (Phase 11, 14)
- [ ] Errors handled correctly — no raw stack traces surfaced to user (Phase 13)

### Engineering
- [ ] No hardcoded architecture constants (Phase 01's grep check, re-run)
- [ ] No duplicate services (Phase 15's audit)
- [ ] No dead routes (Phase 15's audit)
- [ ] No fake/decorative UI elements (Phase 15's audit — specifically re-verify the original "MCP tools view" is now real)
- [ ] No untested critical paths (Phase 12/13 coverage cross-referenced against Phase 09's state machine)
- [ ] No uncontrolled agent loops (Phase 09, re-verified in Phase 15)
- [ ] No unrestricted tool access (Phase 08, re-verified in Phase 15)
- [ ] No hidden network calls (Phase 15's network-blocked test run)
- [ ] No cloud dependency for core operation (Phase 15's OS-level offline test)

## Sign-off Requirement
Every checked item must reference the specific test/command that verified it — a checklist item checked without a corresponding passing test run is not a valid sign-off. This gate exists specifically to prevent the failure mode report.md itself warned about: claiming "fully functional, audited, hardened, and verified" without evidence.

## Rollback
If the gate fails on any item, the release does not ship — return to the owning phase, fix, re-run Phase 15's regression, re-attempt this gate. There is no partial release.

## Validation Commands
```
# Full gate run — every command from every phase's Validation Commands section, in dependency order
bash scripts/run_full_gate.sh   # to be created in this phase: sequentially invokes every phase's validation commands, halts on first failure, reports which gate item failed
```
