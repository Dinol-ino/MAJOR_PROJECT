# Stage 6 — Deployment Packaging

**Depends on Stages 1–4 being stable.** This is the stage where "runs on my dev machine" becomes
"a stranger can install this."

## Two deployment targets — build both, don't collapse them into one

### Path A — Server/team deployment (Docker, existing stack)

Keep the current `docker-compose.yml` (Postgres+pgvector, Redis, backend, frontend) as-is — this
target is already close to correct. This stage's task here is narrow:
1. Add a single top-level installer script (`install.sh` / `install.ps1`) that checks for
   Docker, installs it if missing (or clearly instructs if it can't be automated on the platform),
   pulls/builds the compose stack, runs Alembic migrations, and pulls the default Ollama model —
   collapsing the current multi-step README instructions into one command.
2. Add health-check endpoints (`GET /health/db`, `GET /health/redis`, `GET /health/ollama`) so the
   installer (and future monitoring) can confirm each dependency is actually reachable, not just
   that the container started.
3. Document this path in `README.md` as "Team / Server Install."

### Path B — Single-user desktop distribution (new, lightweight)

This is the path for "a user imports this to their own PC" without Docker/Postgres knowledge.

1. **Storage swap for this build target only**: add a `STORAGE_BACKEND` setting
   (`postgres` | `sqlite`). When `sqlite`, use SQLite with the `sqlite-vec` extension in place of
   Postgres+pgvector for the relational + vector store, and drop the Redis dependency in favor of
   an in-process cache (e.g. `diskcache` or a simple in-memory dict with TTL) for session memory.
   **This is an additive backend, not a replacement** — `postgres` stays the default for Path A;
   `sqlite` is a new code path behind the same repository/interface abstractions already used for
   `IngestionRepository`/`PostgresHybridRetriever`, so both storage backends implement the same
   interface.
2. **Desktop shell**: wrap the existing React frontend in Tauri (smaller binary, native, doesn't
   require bundling a full Chromium runtime the way Electron does) rather than rebuilding the UI.
   The FastAPI backend runs as a local sidecar process the Tauri shell starts on launch.
3. **Bundled Ollama management**: reuse Stage 4.3's auto-pull flow for first-run model setup, this
   time triggered by the desktop installer's first-launch wizard instead of a web form.
4. **Single installer output**: produce a `.exe`/`.dmg`/`.AppImage` via Tauri's bundler for
   Windows/macOS/Linux respectively.
5. Document this path in `README.md` as "Desktop / Solo Install," clearly separate from Path A so
   users pick the right one for their situation.

## 6.1 CI/CD

**Task:** add a GitHub Actions workflow that on every PR: runs `pytest` (backend), runs the
frontend lint/build, runs `attack_suite/run_comparison.py` in offline/simulated mode (per its
existing `ollama_online` fallback branch — don't require a live Ollama instance in CI), and blocks
merge on failure. On merge to `main`, build and push the Path A Docker images.

## 6.2 Backup / restore

**Task:** add `scripts/backup_platform.py` — dumps Postgres (or SQLite file, for Path B) and the
`uploads-data`/`chroma-data` volumes to a single timestamped archive; `scripts/restore_platform.py`
reverses it. Document the retention policy for the audit SQLite log separately, since it's
hash-chained and must never be partially restored (partial restore breaks the chain's
verifiability) — restore it as a whole file or not at all.

## 6.3 Monitoring / observability

**Task:** the codebase already tracks per-stage latency (`latency_ms` dict in `chat.py`) and has a
`LangfuseTracer` with a local-logging fallback when Langfuse isn't configured. This stage's task is
to make that data visible, not to build new instrumentation:
1. Add a lightweight `GET /metrics` endpoint (Prometheus-format) exposing request counts, block
   rates by layer, and p50/p95 latency per stage, sourced from the existing timing data already
   being computed.
2. This is optional to wire into a full Grafana dashboard for v1 — the endpoint existing and being
   scrapeable is the acceptance bar for this stage; the dashboard itself can come later without
   blocking anything else.

## Testing for this stage

- Run the Path A installer script against a clean VM/container and confirm it reaches a working
  `/health/*` green state with zero manual steps beyond running the script.
- Run the Path B installer on a machine with no Docker/Postgres installed at all, confirm first-run
  wizard completes model pull and produces a working chat response.
- Confirm backup → wipe → restore round-trips correctly for both storage backends.
