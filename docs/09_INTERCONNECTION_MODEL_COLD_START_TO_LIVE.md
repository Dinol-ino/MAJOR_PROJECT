# Module 9 — Interconnection Model: From Blank Install to a Living System

**Purpose of this document**: every module (4 through 8) references a shared event, `ChatResponseFinalized`, and shared rules about provenance and cold-start honesty. This file is the single diagram and contract that ties them together, so antigravity implements *one* coherent event flow instead of six modules' worth of endpoint fixes that each independently decide how to talk to each other.

---

## 9.1 The core principle, stated once

**Every view in the product is a read-model over a small number of real, timestamped events. No view is allowed to have its own independent seed data.** A brand-new install, before any user interaction, shows every view in a correct, honest, empty (or corpus-only) state. The system becomes "alive" — citation graph growing, audit ledger filling, statute library showing "recently referenced" — strictly as a function of real chat, uploads, and MCP calls happening. This is the literal mechanism for what you asked for: *"initially to be complete blank but after chat, data it gets connected and shown so its dynamic."*

## 9.2 The five real events, and what each one is allowed to touch

| Event | Emitted by | Consumed by |
|---|---|---|
| `ChatResponseFinalized` | `/chat`, `/chat/stream` (Module 4) | L2 Conversation write, L6 Audit write, Citation Graph upsert (Module 5), Statute Library `last_referenced_at` bump, L5 Research Memory (only if part of a Deep Thinking trace) |
| `DocumentIngested` (with sub-states per Module 7 §7.1) | `/upload`, `/upload/batch` | L4 Document Memory, ChromaDB/BM25 index write, L6 Audit write, Citation Graph edges tagged `user_document_reference` (Module 5 §5.3.2) |
| `MCPToolInvoked` | `/mcp/tool-call` (Module 6 §6.4) | L6 Audit write, `GET /mcp/history`, Mode Enforcer visible-state flip if ONLINE, Citation Graph edges tagged `mcp_case_law_lookup` when the tool returns case law |
| `DefenseLayerDecision` | Layer 1/2/3 (report.md §5), fired for every request regardless of outcome | L6 Audit write only — this is the "Shield Block Events" counter in Img 3, and must fire on every request, not just blocked ones, so a 0-block session still shows a real audit trail |
| `ModelLifecycleChanged` | `/models/pull`, `/runtime/switch`, `/recommend/override` (Module 6) | Hardware Engine UI state, L6 Audit write (model switches are a security-relevant event worth logging — a user should be able to see, after the fact, which model actually answered a given historical query) |

**Task 9.2.1**: Implement these as an internal lightweight event bus (in-process pub/sub is sufficient at this scale — no need for Kafka/Redis Streams given report.md's own SLA numbers are sub-second single-process) so each consumer is independently unit-testable and none of them can silently stop firing without a test catching it.

## 9.3 Cold-start state, view by view

| View | Fresh-install state | First real trigger |
|---|---|---|
| Legal Copilot | Empty conversation, corpus-only knowledge, honest scope/coverage disclosure on first "what do you know" style question | N/A — this is the entry point |
| Citation Graph | Nodes/edges exactly matching ingested corpus structure (`Contains` edges only) — no interpretive or precedent edges until either curated relationship files are loaded or real chat/MCP activity produces them | `ChatResponseFinalized` with a new citation, or `MCPToolInvoked` returning case law |
| Statute Library | Full list of ingested Acts with **honest, verified** section counts (Module 5 §5.4.1) — no "recently referenced" highlighting yet | `ChatResponseFinalized` bumping `last_referenced_at` |
| Cryptographic Audit Ledger | Zero or near-zero records (only system-startup events) — never claims "100% Verified" until `/audit/verify` has actually run against a non-trivial chain | Every real request via `DefenseLayerDecision` |
| Hardware Engine | Real single-atomic hardware probe (Module 6 §6.1), model catalog showing `NOT_PULLED` for everything except whatever ships pre-pulled | `ModelLifecycleChanged` on first pull/switch |
| MCP Tools | Registered servers and their real, verified allowed-tools list (Module 6 §6.4.1) — no call history yet | `MCPToolInvoked` |
| Project Vault (Module 2) | Empty vault list; first vault created explicitly by the user | User action, not automatic |

## 9.4 What this buys you, concretely

This is the direct answer to the standing worry across this whole conversation — *"is this hardcoded or dynamic"* — for every future feature, not just the ones enumerated here: if a proposed feature can't name which of the five events (§9.2) feeds it, or can't describe its own honest cold-start state (§9.3), that's the signal it's about to become another static seed dressed as a live feature, and it should be rejected at design time rather than caught in a future evidence audit.

**Task 9.4.1**: Add a one-line "data source" requirement to your own internal feature-request template (in whatever `agent_skills/` file governs antigravity's engineering standards): every new UI element that displays data must declare, at proposal time, which event(s) populate it and what it looks like before any of those events have fired. This is a process fix, not a code fix, but it's the cheapest possible way to stop this exact category of defect from recurring a third time.

## 9.5 Sequencing against Modules 1–8

1. Module 9's event bus (§9.2) should be scaffolded early — it's small — but each event's producers/consumers are only wired in as their owning module (4 through 8) lands. Don't wire `Citation Graph upsert` before Module 5's `derivation_method` tagging exists, or you'll recreate an untagged, unprovenanced graph under a different name.
2. Module 1 (grounding) still gates everything — an event bus faithfully reflecting a chat pipeline that still hallucinates just makes the hallucinations better-audited, not gone.
3. Once Modules 4–8 are wired to the bus, re-run the Module 0 evidence audit process against the *new* system: fresh install, walk through Img 1–8's exact screens in order, and confirm each one now shows the honest cold-start state described in §9.3, then confirm it populates correctly after one real chat + one real upload + one real MCP call.

## Acceptance criteria for Module 9
- [ ] All five events implemented as testable, independently-failing-safe handlers.
- [ ] A fresh install walkthrough (repeat of the Module 0 screenshot session) shows every view in its correct cold-start state.
- [ ] After exactly one chat message, one document upload, and one MCP call, every view referenced in §9.3 shows a demonstrable, correct change with no manual seeding.
- [ ] The "data source" requirement is added to the antigravity engineering-standards skill file so this discipline persists past this specific refinement pass.
