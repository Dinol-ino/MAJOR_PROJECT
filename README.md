# DFrag — Defensive Legal RAG Workspace

A local-first legal research workspace for Indian law. Answers are drawn from **your indexed
statutes and uploaded documents**, pass through a three-layer security pipeline, and cite the
passages they rely on. When the evidence is insufficient, DFrag says so instead of guessing.

```
request → auth → input guard (L1) → legal-scope gate → retrieval (BM25 + dense, RRF; own vaults only)
        → citation-graph expansion → evidence packing (token budget) → context sanitiser (L2)
        → ACTIVE local model → output guard / grounding (L3) → persist + graph + audit → answer
```

## What is actually in this repository

| Area | Status |
|---|---|
| Statutory corpus | `data/acts_raw/*.txt` + `manifest.yaml` (provenance). Ships with an excerpted IT Act, 2000 marked **unverified**. Add acts and re-index from the Statute Library. |
| Retrieval | Persistent BM25 (authoritative) + Chroma dense vectors when an embedding model is loaded. Without one, dense search is disabled and reported — never faked. |
| Models | Ollama. Only installed models appear in the top selector; the active model is persisted. Downloads are explicit (Hardware & Models → Download & activate). |
| Research sources (MCP) | Built-in local tools. Online tools report "no connector configured" rather than returning results. External servers are declared in `backend/app/config/mcp_servers.yaml` (none by default). |
| Cloud fallback | Off by default; legacy direct pipeline only; never used for requests that include vault documents. |

## Run with Docker

```bash
cp .env.example .env
# Set JWT_SECRET_KEY and SECRET_KEY (python -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose up -d --build
```

Open http://localhost:3000. The first account you register administers the workspace.
All ports are bound to `127.0.0.1`. Data lives in named volumes (`pg-data`, `chroma-data`,
`bm25-data`, `sqlite-data`, `ollama-models`) and survives `docker compose down` (not `down -v`).

Then: **Hardware & Models → Download & activate** a recommended model.

## Run natively (development)

```bash
# backend
cd backend && python -m venv venv && . venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend
cd frontend && npm ci && npm run dev
```

With `DATABASE_URL` empty the backend uses local SQLite. If you set a PostgreSQL URL it is used
strictly: when unreachable the API returns 503 (set `DB_ALLOW_SQLITE_FALLBACK=true` only for local
experiments — `/health` will then report the fallback).

## Configuration

Everything environment-specific is in `.env` (see `.env.example`): secrets, model runtime URL and
timeouts, storage paths, reasoning budgets (`REASONING_<LEVEL>_<FIELD>`), network mode, upload limits.

## Tests

```bash
cd backend && python -m pytest -q
```

The suite is hermetic (`tests/conftest.py`): temporary stores, no Ollama, no network. It includes
tenant-isolation, auth, SSRF/offline, upload-limit, prompt-injection and "no fabricated evidence"
regression tests. CI (`.github/workflows/ci.yml`) runs the backend suite, the frontend build and the
container build.
