# DFrag — Execution Plan

Defense-hardened Legal RAG · 3 devs · 15-hour build · local-first stack

## 0. Design fixes applied on top of the blueprint

| Blueprint claim | Problem | Fix locked for build |
| :--- | :--- | :--- |
| Layer 3 "grounding check" done by the LLM judging itself | Weak model self-judging its own hallucination has high false-negative rate | Deterministic **token/entity overlap** between answer and retrieved `<data>` chunks (threshold, e.g. $\ge 0.4$ Jaccard on content words). No second LLM call. |
| 3 devs all writing to shared Tier-1 ChromaDB | Local persistence isn't safe for concurrent writers across machines | Tier-1 build is a **one-time seed script** (`scripts/seed_tier1.py`), run locally by each dev, output dir gitignored. Never commit the Chroma binary dir. |
| "SQL injection structurally impossible" | True only if enforced | Added as a **PR checklist item**: no f-string/format SQL, parameterized only — checked before every merge to `main`. |
| Layer 1 regex/keyword injection detection | Bypassable via encoding/translation | Documented explicitly as a **known limitation** in report; attack suite must include one Layer-1-bypass case that L2/L3 still catch, to demonstrate defense-in-depth, not reliance on L1 alone. |

## 1. Repository structure

```
dfrag/
├── PLAN.md                     # this file — source of truth
├── skills/                     # agent/dev conventions
│   ├── AGENT_RULES.md
│   ├── api-contract.md
│   ├── coding-conventions.md
│   └── security-checklist.md
├── phase/                      # phase tracking
│   ├── phase-0-setup.md
│   ├── phase-1-parallel-build.md
│   ├── phase-2-integration.md
│   ├── phase-3-defense-wireup.md
│   ├── phase-4-polish.md
│   └── STATUS.md               # single-line status per phase
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint, routes only
│   │   ├── config.py           # env vars, model name, paths
│   │   ├── schemas.py          # pydantic request/response models
│   │   ├── retrieval/
│   │   │   ├── tier1_law.py    # Tier-1 law (Indian Law DB) retrieval
│   │   │   ├── tier2_user.py    # Tier-2 user PDF retrieval
│   │   │   ├── hybrid_rank.py  # BM25 + dense fusion
│   │   │   └── pageindex.py    # act/chapter/section tree builder
│   │   ├── defense/
│   │   │   ├── layer1_input_guard.py
│   │   │   ├── layer2_trusted_context.py
│   │   │   ├── layer3_output_guard.py
│   │   │   └── audit_log.py    # hash-chained SQLite
│   │   ├── model/
│   │   │   ├── ollama_client.py
│   │   │   └── recommend.py    # hardware -> model recommendations
│   │   ├── ingestion/
│   │   │   ├── pdf_extract.py  # pdfplumber wrapper
│   │   │   └── chunker.py      # section-aware chunker
│   │   └── routes/
│   │       ├── chat.py
│   │       ├── upload.py
│   │       ├── recommend.py
│   │       └── audit.py
│   ├── scripts/
│   │   └── seed_tier1.py       # law DB seeding script
│   ├── tests/
│   │   ├── test_defense_layers.py
│   │   ├── test_retrieval.py
│   │   └── attack_suite/
│   │       ├── attacks.json    # 10 attack prompts
│   │       ├── run_comparison.py
│   │       └── malicious.pdf   # hidden instruction PDF
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx
│   │   │   ├── ShieldToggle.jsx
│   │   │   ├── SourcesPanel.jsx
│   │   │   ├── MicButton.jsx
│   │   │   ├── UploadButton.jsx
│   │   │   └── HardwareForm.jsx
│   │   ├── api/
│   │   │   └── client.js       # API client wrapper
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── data/
│   └── acts_raw/               # raw acts folder
├── docker-compose.yml
└── README.md
```

## 2. Branching strategy

- `main`: always demoable, protected, no direct pushes.
- `dev`: integration branch, merges land here first.
  - `feat/frontend-a` (Person A)
  - `feat/rag-core-b` (Person B)
  - `feat/defense-c` (Person C)
- `main` is only merged from `dev` at the end of Phase 2 and Phase 3 (two demoable checkpoints).
- Each person branches `feat/*` off `dev`, rebases onto `dev` before opening a PR.

## 3. API contract

Refer to `skills/api-contract.md` for JSON details.

## 4. Skills / conventions

Refer to files in `skills/`.

## 5. Phase structure

Refer to files in `phase/`.
