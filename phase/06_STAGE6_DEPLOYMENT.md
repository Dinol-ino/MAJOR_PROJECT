# Stage 6 — Deployment Packaging

Two distinct deployment paths, different constraints for each. Do not let one path's convenience compromise the other's constraints.

## Path A — Docker (server/team)

- Full stack containerized: API service, Redis, Postgres, Ollama (or connection to a managed Ollama instance), pgvector.
- Guardrails + full validator dependency set (spaCy models etc.) included in image — bundle size is a lesser concern here than on desktop.
- CORS, rate limiting, and auth (Stage 1) configured for multi-user team access, not single-local-user assumptions.
- Acceptance: `docker compose up` produces a working stack with no manual post-start configuration beyond initial admin account creation.

## Path B — Tauri + SQLite (desktop, non-technical solo users)

- SQLite replaces Postgres for this path's durable memory (Stage 3 schema, SQLite-compatible subset) — single-user, no multi-tenant concerns, so this is a legitimate simplification, not a compromise of Stage 1's isolation work (isolation matters for multi-user paths; single local user doesn't need cross-user isolation, but auth/token storage security still applies).
- Bundle size decision from `02_STAGE2...`/earlier Guardrails discussion: evaluate whether the full Guardrails framework is worth bundling versus implementing the specific validators (structured schema check, overlap scoring, citation-existence check) as lightweight custom code without the framework dependency. Decide based on actual measured bundle size impact, not assumption.
- Ollama bundled or auto-installed on first run, with the Tier 0 (3B) model pre-pulled so the app is usable immediately without a large first-run wait beyond the base model download.
- Hardware detection (Stage 4) runs on first launch, before any other setup step, to determine what tier upgrade to offer.
- Installer/first-run flow must not require any command-line interaction — this path is explicitly for non-technical users.
- Acceptance: a non-technical user can install, launch, and get a working (Tier 0) legal Q&A response with zero manual configuration and zero command-line steps.

## 1. Corpus distribution

- The Indian legal corpus (Stage 2) must ship pre-ingested with the desktop installer (or be downloaded as a versioned bundle on first run) — do not require end users to run the scraping/ingestion pipeline themselves.
- Corpus updates (from Stage 2's re-crawl cadence) are distributed as periodic update bundles the desktop app can pull and apply, not a live re-scrape running on the user's machine.

## 2. Session/session-list

- `GET /sessions` and `SessionList.jsx` (Stage 3) function identically across both paths — same API contract, different backing store (Postgres vs SQLite).

## 3. Audit log access

- Docker path: audit log accessible to admins via a dashboard or log aggregation, per team needs.
- Desktop path: audit log stored locally, viewable by the user (transparency for a single-user tool) but not transmitted anywhere.

## Exit criteria for Stage 6
Both paths independently pass their acceptance criteria. Desktop path specifically must be validated on hardware at the Tier 0 floor (the actual dev laptop spec) as the baseline "must work" case before considering the stage complete.
