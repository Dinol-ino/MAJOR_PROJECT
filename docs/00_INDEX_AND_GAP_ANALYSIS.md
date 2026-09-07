# DFrag v4 Refinement Program — Index & Evidence-Tagged Gap Analysis

**Status of this document**: Architect handoff to antigravity. Refines the existing v3.0 codebase — no rewrite from scratch. Every task below references the actual file paths named in `report.md`.

**Evidence key**: DESIGNED (in docs only) / OBSERVED (seen in screenshots or prior audit) / CLAIMED (report.md asserts, unverified) / NOT ESTABLISHED (no evidence either way).

---

## 0.1 Why this program exists

`report.md` claims "Enterprise Production Grade — Audited, Hardened, Verified & Formally Signed-Off" and "190 automated pytest backend regression tests (100% pass)." Your own prior evidence audit (`EVIDENCE_FINDINGS_AND_SCOPE_CORRECTION.md`) put real completion at **15–25%**, with 9 confirmed defects including canned template responses, fake statutory retrieval, a 10-node citation graph instead of a real corpus, and an audit ledger showing zero records despite "100% Verified" badges.

The new screenshots you've shared are consistent with that audit, not with the report:

| Screenshot | What it shows | Evidence tag |
|---|---|---|
| Img 1 | Hardware Engine: CPU "Detecting…" frozen, RAM/GPU already populated | OBSERVED — telemetry read is partial/inconsistent |
| Img 5 | Same view, still "Detecting…", model list area blank ("Scanning hardware…") | OBSERVED — no fallback state, no timeout handling |
| Img 6 | Same view seconds later: full CPU/RAM/GPU numbers **and** a 7-model list with "Auto-Pull" buttons, one marked "ACTIVE" | OBSERVED — inconsistent with Img 1/5; suggests race condition or two data sources (one real psutil read, one static list) |
| Img 3 | Chat: "Error: Failed to fetch response from backend inference engine" / "Blocked by SYSTEM Guard: Failed to fetch," model shown as `GEMMA2:2B` | OBSERVED — confirms defect #6 from your audit (only Gemma2:2B active) and defect #9 (no graceful degradation) |
| Img 7 | Chat: professional grounded response, model shown as `DFRAG-LEGAL:7B`, "Grounded (75%)" badge, 5 cited provisions with "Show Provenance Details" | OBSERVED — this is the *target* quality bar, but note it only appears once the model switched to `dfrag-legal:7b`, which Img 6 shows is not yet pulled/active by default |
| Img 8 | Citation Graph: ~14 visible nodes (IT Act 2000, BNS 2023, Companies Act, Contract Act, a handful of sections, one precedent "Shreya Singh...") | OBSERVED — matches your audit's "~10-node seed citation graph rather than a real corpus" almost exactly |
| Img 4 | Statute Library: infinite "Loading Indian Statutory Knowledge Base…" | OBSERVED — no error state, no timeout, no empty state |
| Img 2/6 (MCP panel) | `local-statute-server` and `indian-legal-gateway` shown as "Allowlisted" with specific tool names (`indiacode_fetcher`, `kanoon_case_search`, `live_statute_checker`) | CLAIMED in UI — no confirmation these servers are live processes vs. static config rows (matches audit defect #7: MCP servers wired to unrelated generic tools with a cloud dependency next to an "OFFLINE" badge) |

**Conclusion carried into every module below**: nothing in this plan assumes the report's claims are true. Each module states what to *verify* before it states what to *build*, because building new features (Project Vault, Deep Thinking, fallback API) on top of unverified grounding will just add more surface area that looks finished and isn't.

---

## 0.2 Your stated priorities, restated as engineering scope

You asked for, in your own words: (1) better legal answer quality — the fine-tuning/system-prompt side isn't "doing any better," (2) unprofessional response formatting, (3) cloud API key fallback, (4) permanent context/memory/conversations, (5) Project Vault, (6) Deep Thinking mode, (7) Claude-like context window controls, (8) renaming chats, (9) per-vault file caps with permanent case-file memory, (10) visible upload/processing states in the UI, (11) natural (non-"AI-generated-looking") UI, (12) broad Indian law coverage instead of the fixed set visible in screenshots, (13) real MCP/API integration for current law instead of fabricated citation graphs and hardcoded hardware/model lists.

These map to five modules:

| Module | File | Covers your asks |
|---|---|---|
| 1 | `01_GROUNDING_AND_RESPONSE_QUALITY.md` | 1, 2, 12 |
| 2 | `02_PROJECT_VAULT_AND_MEMORY.md` | 3 (partial), 4, 5, 6, 7, 8, 9 |
| 3 | `03_DYNAMIC_HARDWARE_AND_MODEL_REGISTRY.md` | fixes Img 1/5/6 inconsistency, "Auto-Pull" |
| 4 | `04_DYNAMIC_MCP_GATEWAY_AND_CITATION_GRAPH.md` | 12, 13 |
| 5 | `05_UI_UX_REFINEMENT.md` | 10, 11 |
| 6 | `06_CLOUD_FALLBACK_AND_CONTEXT_CONTROLS.md` | 3, 7 |

## 0.3 Mandatory sequencing — do not reorder

1. **Module 1 before everything else.** A Project Vault or Deep Thinking mode wrapped around a model that still produces the Img 3 failure mode (hard error, no fallback, no grounding) just gives users a nicer container for a broken core. This is the same mistake the v3.0 → "signed-off" jump already made once.
2. **Module 3 before Module 4.** The citation graph and MCP tool claims can't be verified as real until the hardware/model layer underneath them is verified as real — if the model list in Img 6 is static JSON, the "Auto-Pull" button is decorative, and any MCP tool output riding on top of it is unverifiable.
3. **Module 2 (Vault/Memory) can proceed in parallel with Module 5 (UI)** once Module 1 is signed off, since they touch mostly disjoint files (`app/db/models.py`, `app/memory/*` vs. React components).
4. **Module 6 last.** Cloud fallback is a safety net for local failure, not a substitute for fixing local failure — wiring it in early gives antigravity an easy way to make broken local inference "look" fixed by silently routing to Claude/GPT-4o instead.

## 0.4 Definition of done for this program

Not "all features present in UI." Per-module acceptance criteria are in each file, but the program-level bar is: **every claim rendered in the UI must be traceable to a live backend call that antigravity can show you the request/response for, on demand, with no synthetic or seed data in the code path.** If a demo requires `--seed` scripts or mock arrays to look complete, it isn't done.
