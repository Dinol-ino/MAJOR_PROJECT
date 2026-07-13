# Phase 2: Integration (H7 - H9, All)

- **Owners**: Person A (Frontend), Sweedan (RAG Core), Dinol (Defense & Security)
- **Status**: Complete
- **Blocked-by**: Phase 1

## Task Checklist
- `[x]` [Sweedan & Dinol] Connect FastAPI routes to the RAG core search interface and model runtime inference.
- `[x]` [All] Wire React frontend calls to `/upload`, `/chat`, and `/recommend` FastAPI endpoints.
- `[x]` [Sweedan] Ingest 3-5 raw acts into Tier-1 database (`data/acts_raw/` txt files).
- `[x]` [Dinol] Connect SQLite logger to save audit entries for every chat query and PDF ingestion.

## Resumability Notes for Agents
- Dinol has wired up `/chat`, `/audit`, and `/upload` endpoints to the `AuditLogger` and `Layer1/2/3` validation checks inside `backend/app/routes/`.
- The pipeline utilizes `Tier1LawRetrieval` and `Tier2UserRetrieval` stub controllers, which will be updated by Sweedan.
