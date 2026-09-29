# DFrag — Completion Plan

Written 2026-09-29. This file is the plan of record: it lives in the repository so it
survives between working sessions. Update the checkboxes as work lands.

---

## Where the project stands

Verified on 2026-09-29, not asserted:

| Signal | State |
|---|---|
| Backend suite | **322 passed**, hermetic (temp stores, no Ollama, no network), on the pinned dependency set |
| E2E suite | **15 passed** against a live backend |
| Frontend build | `npm ci && npm run build` clean |
| Source tree | No stubs, no `TODO`/`FIXME`, no `NotImplementedError` |
| CI | `backend`, `frontend`, `e2e`, `containers` — YAML valid; not yet observed on a real runner |
| Corpus | 8 Acts indexed, 232 sections; **all `legal_status: unverified`** (Phase 3, outstanding) |
| Generation path | **Never exercised.** Every run so far returned `failure_kind: model_unavailable` |

The architecture described in `report.md` exists in code. What remains is verification,
a set of known security defects, and provenance work.

### What is NOT done, in one line each

1. No run has ever produced a real model answer.
2. ~~13 security findings~~ — 11 fixed, 2 withdrawn as non-defects (#1, #14). Done.
3. Every Act is `unverified` — nobody has diffed the excerpts against India Code.
4. Six commits are local; nothing is pushed.
5. `docker compose build` has never been run.

---

## Phase 0 — Protect the work  ·  ~10 min

- [ ] Push `main`. Six commits (`f8e3860` .. `538ccdb`) exist only on this machine.
- [ ] Confirm CI actually runs green on the runner. It has never executed; the
      `e2e` job in particular boots a backend and is unproven outside this machine.
- [ ] If the `e2e` job fails on the runner, fix it there before anything else —
      a red CI badge costs more than it saves.

**Done when:** GitHub shows all four jobs green on `main`.

---

## Phase 1 — High-severity security fixes  ·  ✅ DONE 2026-09-29

Each contradicts a guarantee the README makes, each is small and self-contained,
and each gets a regression test in `backend/tests/security/`.

- [x] **#1 — `app/runtime/model_state.py`: honour `available`.**
      `resolve_for_request()` returns `active["model"]` without checking
      `active["available"]`, so a dead runtime or a deleted model is returned anyway
      and fails opaquely downstream. Gate on it; raise
      `ModelNotAvailable(code="runtime_offline")`.
      *Test:* runtime offline → `ModelNotAvailable`, not a model tag.

- [x] **#2 — `app/routes/auth.py`: stop the token cache outliving revocation.**
      `_TOKEN_CACHE.put(candidate, user_dict, float(payload["exp"]))` caches the user
      record for the full token life (`AUTH_SESSION_TTL_SECONDS` defaults to 7 days),
      and `get_current_user` returns the cache hit before consulting `_REVOKED`.
      A deleted or demoted user keeps access for up to a week.
      Cache for `min(exp, now + 60)` and check `_REVOKED` on the hit path.
      *Test:* revoke, then assert the next request with the same token is 401.

- [x] **#3 — `app/main.py`: apply the rate limiter.**
      `default_limits` only takes effect with `SlowAPIMiddleware` registered, and it
      is not. Only the three decorated auth routes are limited; `/chat`, `/upload`
      and `/research` are unlimited and `RATE_LIMIT_DEFAULT` is dead config.
      Add `app.add_middleware(SlowAPIMiddleware)`.
      *Test:* exceed the default limit on a non-auth route → 429.
      *Watch out:* this will throttle the E2E suite. `DynamicTestLimiter` already
      disables limiting under pytest, but Playwright drives a real server — if E2E
      starts returning 429, raise `RATE_LIMIT_DEFAULT` for the CI backend.

**Done when:** 305+ backend tests pass, three new regressions pass, E2E still 15/15.

---

## Phase 2 — Prove the generation path  ·  ~1–2 h

The highest-risk unknown. Everything tested so far is the *refusal* path.

- [ ] Start Ollama; pull a model that fits the machine.
- [ ] Activate it through **Hardware & Models → Download & activate** (exercises
      `ModelStateService.activate`: verify → fit → warm-up → persist).
- [ ] Ask a question answerable from the indexed corpus, e.g.
      *"What does Section 66 of the Information Technology Act provide?"*
- [ ] Confirm, and screenshot for the report:
      - a real answer with a `Grounded: N%` badge
      - `sources` citing indexed sections
      - `model_used` populated, `failure_kind` null
- [ ] Restart the backend and confirm the active model persisted.
- [ ] Ask something the corpus cannot answer and confirm it declines rather than
      guessing — this is the project's headline claim and needs evidence.
- [ ] Submit a prompt-injection attempt and capture the refusal.

**Done when:** you have screenshots of a grounded answer, an honest refusal, and a
blocked injection. These are the demo.

---

## Phase 3 — Corpus provenance  ·  ~2–4 h, no coding

The single change that most improves how the project reads. Currently the UI reports
*"Provenance verified for 0% of acts"*.

For each entry in `data/acts_raw/manifest.yaml`:

- [ ] Open its `source_url` (already filled, pointing at India Code).
- [ ] Diff the local excerpt against the official text.
- [ ] Set `legal_status` (`in_force` / `amended` / `repealed`) and `verified_at`
      to the date you checked. Leave anything you did not check alone.
- [ ] Re-index from the Statute Library and confirm the percentage rises.

Acts: BNS 2023 · BNSS 2023 · BSA 2023 · IT Act 2000 · Companies Act 2013 ·
Consumer Protection Act 2019 · Indian Contract Act 1872 · DPDPA 2023.

> Verify only what you actually check. A manifest that claims verification it did not
> do is worse than one that admits `unverified` — the honesty is the product.

**Done when:** at least the IT Act and BNS are genuinely verified, and the Statute
Library reports a non-zero percentage.

---

## Phase 4 — Remaining findings  ·  ✅ DONE 2026-09-29

Medium:
- [x] #4 Login timing oracle — `valid = bool(user) and _verify_password(...)`
      short-circuits, so unknown usernames answer measurably faster. Always hash
      against a dummy.
- [x] #5 PBKDF2 at 100,000 iterations; OWASP's floor is 600,000. Store the count in
      the hash (`salt$iters$key`) so existing hashes still verify.
- [x] #6 `AUTH_REGISTRATION_OPEN` defaults true — the workspace accepts accounts
      forever. Default it false.
- [x] #7 `ownership.owns()` grants admins write access, not just read. Split
      `can_read()` from `owns()`.
- [x] #8 `_REVOKED`, `_FAILED_LOGINS` and `_active_cache` are per-process and break
      under multiple workers. Document `--workers 1`, or move to a shared store.
- [x] #9 Ephemeral JWT secret should fail hard outside dev.

Low:
- [x] #11 `/health` exposes `installed_models` pre-auth.
- [x] #12 Dead CORS branch in `main.py`.
- [x] #13 `_probe_nvml` never calls `nvmlShutdown()`.
- [x] #14 Confirm `evaluate_model_fit` treats WMI's `vram_total_mb: 0` with
      `vram_reliable: false` as *unknown*, not as zero VRAM.

**Done when:** fixed, or listed in the report as known and triaged. Triaged-and-named
reads better to an examiner than silence.

---

## Phase 5 — Release validation  ·  ~1 h

- [ ] `docker compose build` and `docker compose up -d` from a clean checkout.
- [ ] Register the first account and confirm it becomes admin.
- [ ] `npx playwright install chromium && npx playwright test` on this machine
      (verified in a container against a pinned Chromium; confirm on real hardware).
- [ ] Clone to a fresh directory and re-run the corpus index — this checks the
      `.gitignore` fix that made `data/acts_raw/` ship. Before it, a clone had one Act.

**Done when:** a fresh clone reaches a working workspace with no manual file copying.

---

## Phase 6 — Submission  ·  mostly done, screenshots outstanding

- [x] Reconcile `report.md` against the code — component tree, corpus listing,
      test counts (190+ → 322 + 15 E2E), and a telemetry claim that contradicted
      `gpu_probe.py` (it said "no WMI subprocesses"; there is a WMI fallback).
- [x] Remove references to deleted components; add `LoginView`.
- [x] Add §15 Known Limitations & Scope Boundaries, and reconcile the conclusion
      (it claimed "Absolute Hallucination Defense", which §15.3 contradicts).
- [ ] Drop in the Phase 2 screenshots.

---

## Suggested order

Phase 0 → 1 → 2 → 3, then 4/5/6 as time allows.

Rationale: Phase 0 protects the work. Phase 1 is cheap and closes the gap between
what the README promises and what the code does. Phase 2 is scheduled early because
it is the likeliest source of unknown bugs and you want slack for them. Phase 3 needs
no code and can run in parallel with anything.

## Honest framing for the viva

Two things are worth saying before being asked:

- **The corpus is excerpts, marked unverified.** The provenance pipeline is real; the
  data is a sample. That is a defensible engineering position — do not let the demo
  imply the system is a citable legal authority.
- **Known findings are documented, not hidden.** A project that enumerates its own
  security defects is stronger than one that claims none.


---

## Progress log

**2026-09-29** — Phases 1, 4 and 6 completed in one session.

- Phase 1: #2 (token cache outliving revocation) and #3 (rate limiter never applied)
  fixed with 9 regression tests. **#1 withdrawn**: raising on an unavailable model
  broke graceful degradation — the chat route 409s before retrieval, discarding the
  evidence. Caught by 10 pre-existing test failures. The original behaviour is correct
  and is now pinned by a test that explains why.
- Phase 4: #4, #5, #6, #7, #8, #9, #11, #12, #13 fixed with 8 regression tests.
  **#14 withdrawn**: `hardware_detector` already gates on `vram_reliable`.
- Phase 6: report.md reconciled; §15 Known Limitations added.
- Suites after: **322 backend, 15 E2E, both green.**

**Still outstanding — all need your machine or your judgement:**

- **Phase 0** — push. The remote is `Dinol-ino/MAJOR_PROJECT`, a shared repo, now
  11 commits ahead. Not pushed unilaterally: the line-ending normalisation rewrites
  every file and will conflict with any in-flight work a collaborator has. Coordinate,
  or push to a branch and open a PR.
- **Phase 2** — the generation path is still unproven. Ollama is not reachable from a
  cloud session; this needs running locally.
- **Phase 3** — corpus verification. Requires a human to diff each excerpt against its
  India Code source and sign it off. Do not delegate this to a model.
- **Phase 5** — Docker build and a fresh-clone check; no Docker in the cloud session.
- **Phase 6** — Phase 2 screenshots, once Phase 2 is done.

**Unverified claims left in report.md** that you should confirm or soften before
submission, since I could not reproduce them: the §12.1 "Measured Production
Performance" latency column, and the §12.2 "100% block rate against 110 adversarial
vectors". If those were measured on your machine, say so and give the conditions; if
they were estimates, mark them as targets rather than measurements.
