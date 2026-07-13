# Phase 1: Parallel Build (H1 - H7)

- **Owners**:
  - Person A: Chat UI, Shield Toggle (visually wired, backend mocked), Mic Button, Upload Button, Hardware Form.
  - Person B: `seed_tier1.py` DB builder, Tier-2 ingestion pathway, hybrid BM25 + dense fusion, model recommend logic.
  - Person C: Layer 1, 2, and 3 security validators, hash-chained SQLite audit logs, drafting the 10 attack prompts suite.
- **Deliverables**:
  - Independent frontend mockup screens connecting to local dev API.
  - Seeding scripts and hybrid search routines.
  - Independent defense modules verified with unit tests.
- **Acceptance Criteria**:
  - Each developer's module builds and compiles cleanly.
  - Unit tests run successfully in isolation.
- **Blocked-by**: Phase 0.
