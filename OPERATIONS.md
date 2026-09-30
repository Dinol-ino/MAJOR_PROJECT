# DFrag — Operations & Status

Security-hardened legal RAG workspace for Indian law. Single source of truth for
running it, configuring it, and knowing what is and is not finished.

Repo root: `C:\defensive rag\MAJOR_PROJECT`

---

# 1. Run it

## 1.1 Prerequisites on the host

| Thing | Where it runs | Check |
|---|---|---|
| Docker Desktop | host | `docker version` |
| PostgreSQL 17 | **native on host, port 5433** | `psql -h 127.0.0.1 -p 5433 -U postgres -l` |
| Ollama | **native on host, port 11434** | `curl http://127.0.0.1:11434/api/tags` |
| Model `qwen2.5:3b` | Ollama | `ollama list` |

PostgreSQL and Ollama are deliberately **not** managed by compose on this machine —
both already run natively, and compose depending on them caused port conflicts. They sit
behind opt-in profiles instead (§3.2). The backend reaches them over
`host.docker.internal`, which is wired through `extra_hosts: host-gateway`.

## 1.2 Start

```powershell
cd "C:\defensive rag\MAJOR_PROJECT"
docker compose up -d --build
```

Open **http://localhost:3000**. Backend API is on **http://localhost:8000**.

`--build` is needed after any **backend** Python change. The **frontend** is bind-mounted
(`./frontend:/app`) and served by Vite with HMR, so frontend edits appear on save with no
rebuild and no restart.

## 1.3 Everyday commands

```powershell
# state of the stack
docker compose ps

# backend logs (the one that matters)
docker compose logs -f backend

# restart just the backend after a config/.env change (no rebuild)
docker compose restart backend

# rebuild after backend code changes
docker compose up -d --build backend

# full test suite
docker compose exec backend python -m pytest -q

# one test file
docker compose exec backend python -m pytest tests/test_module1_grounding.py -q

# stop (keeps volumes/data)
docker compose down

# stop and DESTROY all indexes, audit log, provisioning db
docker compose down -v
```

## 1.4 Health checks after starting

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/statutes/corpus-status
```

`/health` reports DB, Ollama, model and hardware tier.
`/statutes/corpus-status` must report `"status": "healthy"` with `total_chunks > 0`. If it
reports `"unseeded"`, read the `corpus_source.reason` field:

| reason | meaning | fix |
|---|---|---|
| `corpus_files_missing` | the corpus bind mount is not in the container | recreate the container: `docker compose up -d --force-recreate backend` |
| `corpus_present_but_not_indexed` | files are there, indexing has not run | `curl -X POST http://localhost:8000/statutes/sync` or restart the backend |

The backend log will also name every path it searched for the corpus.

## 1.5 Self-contained fallback (no native Postgres/Ollama)

```powershell
# in .env: DFRAG_PG_HOST=postgres  DFRAG_PG_PORT=5432  DFRAG_OLLAMA_URL=http://ollama:11434
docker compose --profile local-db --profile local-ollama up -d --build
```

---

# 2. Services and ports

| Service | Container port | Host binding | Managed by |
|---|---|---|---|
| frontend (Vite) | 3000 | `127.0.0.1:3000` | compose |
| backend (uvicorn) | 8000 | `127.0.0.1:8000` | compose |
| redis | 6379 | `127.0.0.1:6379` | compose |
| postgres | 5432 | `127.0.0.1:5432` | compose, **profile `local-db`** |
| ollama | 11434 | `127.0.0.1:11434` | compose, **profile `local-ollama`** |
| PostgreSQL (native) | — | `127.0.0.1:5433` | host, outside compose |
| Ollama (native) | — | `127.0.0.1:11434` | host, outside compose |

Every published port is bound to **loopback only**. Nothing is reachable from the LAN.
Redis, Postgres and Ollama have no authentication of their own, so this matters.

Named volumes: `chroma-data` (dense index), `bm25-data` (lexical index), `sqlite-data`
(audit log + provisioning db). The statutory corpus is mounted **read-only** at
`/workspace/data/acts_raw`.

---

# 3. Configuration

## 3.1 Precedence

```
process env (docker compose `environment:`)  >  backend/.env  >  root .env  >  code default
```

`load_dotenv` is called without `override`, so a value already in the environment wins.
Compose passes `env_file: .env` (root) plus an explicit `environment:` block for
container-internal wiring only — hostnames, ports, index paths. Model choice, secrets and
policy come from `.env`.

**Watch out for empty values.** `os.getenv("X", "default")` returns `""` for a variable
that is set but empty, so the default never applies. Two production bugs came from
exactly this (§7.3, §8.4). If a knob should take its code default, **comment the line out**
rather than leaving it blank.

## 3.2 The knobs that matter

| Variable | Current | Effect |
|---|---|---|
| `DFRAG_PG_HOST` / `DFRAG_PG_PORT` | `host.docker.internal` / `5433` | which database |
| `DFRAG_PG_DB` | `dfrag` | database name |
| `DFRAG_OLLAMA_URL` | `http://host.docker.internal:11434` | model endpoint |
| `DEFAULT_MODEL` | `qwen2.5:3b` | generation model |
| `OLLAMA_FALLBACK_MODEL` | *(empty)* | secondary local model; empty = none, correct here since `qwen2.5:3b` is already the smallest tier |
| `GENERATOR_CONTEXT_TOKENS` | `4096` | context window budget |
| `GENERATOR_MAX_OUTPUT_TOKENS` | `2048` | ceiling; per-request value comes from reasoning effort |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `5` | fail fast when Ollama is down |
| `OLLAMA_GENERATION_TIMEOUT_SECONDS` | `180` | generation ceiling |
| `NETWORK_MODE` | `OFFLINE` | no external calls at all |
| `MAX_FILE_SIZE_MB` | `10` | upload size cap |
| `MAX_FILE_PAGES` | `400` | pages read per PDF |
| `PDF_PAGE_OVERFLOW_MODE` | `truncate` | `truncate` or `reject` (§8.2) |
| `VAULT_MAX_FILES` | `10` | PDFs per project vault |
| `ACTS_RAW_DIR` | set by compose | statutory corpus directory |
| `MODELS_DISK_PATH` | *(empty)* | disk measured for download space; empty now resolves safely (§7.3) |
| `DB_ALLOW_SQLITE_FALLBACK` | `false` | never silently switch data stores |

Nothing environment-specific is hardcoded in application logic. If a value differs between
Windows, Docker and Linux, it lives in `.env` or `docker-compose.yml`.

---

# 4. Security pipeline

Every `/chat` request passes three layers. None of them can be skipped, including on the
low-effort fast path — that bypass existed and was closed.

**Layer 1 — input guard** (`app/defense/layer1_*`, `security/injection_gate.py`)
Prompt injection, jailbreak patterns, SQL/command injection. Target **<10 ms**. A block
returns `blocked_by: "layer1"`, `failure_kind: "security_block"` and a correlation ID.

**Layer 2 — trusted context** (`app/defense/layer2_trusted_context.py`,
`security/context_sanitizer.py`)
The only prompt that reaches the model is `prompts/legal_system_prompt_v4.md`. Retrieved
text is untrusted: `<script>` stripped, embedded instructions neutralised, then each chunk
sealed in a defensive container:

```
<data slug="it_act_2000" act="Information Technology Act, 2000" section="66">
 ...text...
</data>
```

The `slug` attribute is what the model copies into a citation token, so it cannot invent
an identifier. Injected imperatives inside retrieved text are stripped while the
substantive content survives — `"Ignore all previous instructions. The fee is Rs 100."`
keeps the fee and loses the command.

**Layer 3 — output guard** (`security/output_validator.py`, `services/response_parser.py`)
Citations resolved against the actual evidence, grounding score computed, contract
violations flagged. Target **<20 ms**.

Also enforced: bcrypt auth with session TTL, per-route rate limiting via slowapi
(`SlowAPIMiddleware` is registered, so `RATE_LIMIT_DEFAULT` actually applies — without the
middleware only the decorated routes were limited), vault/tenant isolation on every query,
SSRF and domain allowlist on outbound requests, PDF active-content scanning, PII scanning,
append-only audit ledger with correlation IDs.

**Never logged:** passwords, API keys, bearer tokens, raw PII, document contents, prompts.
Exception types are logged rather than messages where a message could carry user content.
`/statutes/corpus-status` returns booleans and counts, never filesystem paths.

## 4.1 Tenant isolation

A user cannot reach another user's conversations, vaults, documents, vectors, memories or
audit records. Vault documents live in a per-vault Chroma collection
(`get_vault_collection_name(vault_id)`), and deleting a vault purges its vectors. Graph
queries are filtered to the caller's own conversation IDs unless the caller is admin.

---

# 5. Citations and the no-hallucination guarantee

## 5.1 The contract

The model must end every factual sentence with a token copied from a `<data>` block:

```
[^S:it_act_2000|66]          act slug | section
[^S:it_act_2000|66|12]       ...with a page
```

Page is optional. `p.??` is banned. There is no separate Sources list — the single
mechanism is the token, because a competing "also write a sources list" instruction made
the model do one or the other, not both. A reminder is injected immediately before
`Answer:`, which is what took citation emission from 1-of-2 responses to 3-of-3.

## 5.2 How a citation is resolved

`services/response_parser.py`, two passes:

1. **Section match.** Normalised on both sides — `"Section 43A"`, `"43A"` and `"s43A"` all
   compare equal. Before this, chunks storing `"Section 66"` never matched a model
   emitting `"66"`, so nothing ever resolved.
2. **Act/slug fallback**, only for chunks that carry **no genuine statutory section
   label**. Vault chunks are labelled by position (`Chunk 3`, `Page 12`), which carries no
   statutory meaning, so an act match there is real evidence. A chunk with a real section
   label is **skipped** — its section was already compared in pass 1 and differed.

That second restriction is the anti-hallucination boundary:

| evidence section | model cites | resolved | why |
|---|---|---|---|
| `166` | `s166` | yes | grounded |
| `166` | `s999` | **no** | section 999 is not in the evidence |
| `Chunk 2` | `clause 4` | yes | positional label, act match is real |
| `166` | *(none)* | yes | no section claimed, act match stands |

Without the restriction a fabricated section resolved against the right act and came back
with a real chunk ID and a real quote attached. That defect was introduced during the
citation fix and caught by `test_module1_grounding_score_formula_traceable`.

## 5.3 Grounding score

```
score = (resolved / total) * 100, minus 15 if any citation is unresolved
0 citations on a substantive answer → 40
refusal / out-of-scope / insufficient evidence → 100 (nothing was claimed)
```

`citation_contract_violated` is set when evidence existed and the score fell below
`min_grounding_score`. Refusals are not penalised — an honest "I don't have this" is fully
grounded.

## 5.4 What stops fabricated answers

- Retrieval returning nothing → `INSUFFICIENT_EVIDENCE`, an explicit refusal, `sources: []`.
- Weak dense hits with no lexical support are dropped (`retrieval/hybrid_rank.py` requires
  score ≥ 0.10), so a greeting cannot pull in unrelated statutes.
- The UI shows only **cited** sources, not everything retrieved. Confidence is computed
  from the real grounding score, not a constant.
- Provenance panel shows only recorded values. The fabricated `v2024.1`,
  `Active Settled Law`, `IN (Central / Union Statutes)` and the fake hash built from
  `charCodeAt` were removed.
- Citation graph is laid out by a seeded force simulation over real edges
  (`MAX_GRAPH_NODES 120`, 220 iterations), not an index-ordered circle. An empty graph
  renders empty instead of a decorative ring.
- An act with no manifest entry is named from its own short-title clause, never invented.
  `provenance_verified` is true only when the manifest records both a source URL and a
  verification date.

---

# 6. Vault scoping

A question asked inside a project vault is answered against the user's own documents:

- Vault chunks are sorted ahead of statutory chunks before the context budget is applied,
  so the user's document is not crowded out by statute text.
- The domain gate no longer refuses a vault-scoped question for lacking a statutory
  keyword. "What is the notice period in this agreement?" used to come back as
  out-of-scope. Explicit non-legal patterns (recipes, sport, code) still refuse in every
  scope, and Layer 1 runs before this point, so the boundary is unchanged.

---

# 7. Model calling and performance

## 7.1 Path

```
/chat → bounded orchestrator state machine
  CLASSIFY → SECURITY_CHECK → PLAN → RETRIEVE → TOOL_CALL
  → EVIDENCE_VALIDATION → SYNTHESIS → LEGAL_VERIFICATION → COMPLETED
```

Bounded by construction: max steps, max tool calls, max execution time, cancellation,
circuit breaker per model, full audit trail. Generation runs in Ollama on the host, so the
container needs no GPU stack.

Reasoning effort drives real budgets, not a label:

| effort | top_k | evidence chunks | tool calls | max output tokens |
|---|---|---|---|---|
| low | 3 | 4 | 0 | 512 |
| medium | 5 | 8 | 2 | 1024 |
| high | 8 | 12 | 4 | 2048 |

## 7.2 Targets

| Stage | Target |
|---|---|
| hardware detection | <50 ms |
| Layer 1 gate | <10 ms |
| lexical retrieval (BM25) | <25 ms |
| dense retrieval (Chroma) | <50 ms |
| hybrid RRF rank + dedup | <15 ms |
| PII processing | <40 ms |
| output validation | <20 ms |
| audit write | <5 ms |

End-to-end on this machine, warm, low effort, vault question: **~2.5 s**. Almost all of it
is token generation in Ollama. Retrieval and the defence layers are not the bottleneck.

## 7.3 Build and runtime costs already removed

- **CPU-only torch.** `pip install torch --index-url .../whl/cpu` before
  `requirements.txt`, so the later pass sees torch satisfied. The default wheel pulled the
  whole CUDA runtime — torch 555 MB, cuDNN 553 MB, cuBLAS/cuFFT/cuSOLVER/cuSPARSE/nvrtc,
  around 4 GB the image cannot use. Build time went from 45+ minutes to **491 s**. To move
  to a GPU host, delete that line.
- **`psycopg[binary]`.** Plain `psycopg` ships no libpq, so the async engine
  (`postgresql+psycopg://`) failed while the sync path worked.
- **Disk probe fixed.** `MODELS_DISK_PATH` is empty in both `.env` files, and
  `os.getenv("MODELS_DISK_PATH", os.getcwd())` returns `""`, so `disk_usage("")` raised at
  three call sites. Telemetry reported `free_gb: null`; the hardware detector reported
  `0.0 GB` free, which made `fits_storage` false for **every** model, so model
  recommendation and the auto-pull pre-flight could not work at all. Resolution is now
  centralised in `telemetry.models_disk_path()` — configured value, then nearest existing
  parent, then cwd, then filesystem root, logging each fallback.

## 7.4 What to tune next, in order

1. `GENERATOR_CONTEXT_TOKENS` 4096 → 8192. The context meter reads ~1.9k used against a
   1.8k budget, so evidence is being trimmed. **This costs RAM** and the machine has
   ~2.86 GB usable, so change it, restart the backend, and watch for an Ollama OOM before
   trusting it.
2. Keep the corpus indexes warm. They persist in named volumes; `down -v` destroys them
   and the first question after that pays the full re-index.
3. Do not cache final answers. Stale legal text is worse than slow legal text. Only safe
   intermediate data may be cached, with explicit invalidation.

---

# 8. PDF ingestion

## 8.1 Two paths

| Path | Endpoint | Used for |
|---|---|---|
| session upload | `POST /upload` | ad-hoc PDF in a chat |
| vault ingest | `POST /vaults/{id}/documents` | permanent, indexed into the vault's own collection |

Vault ingestion is **asynchronous**: the request returns `202` with
`status: "pending"`, and a background task walks
`parsing → chunking → embedding → indexing → ready`, updating progress. Poll
`GET /vaults/{id}/documents/{doc_id}/status`. Failures are recorded as
`status: "failed"` with an error, never left hanging. Re-uploading the same file returns
the existing document with `duplicate: true` — dedup is by content hash, per vault.

## 8.2 Strictness, and how it was loosened

Active content is **flagged, not rejected**. `/JavaScript`, `/JS`, `/Launch`,
`/EmbeddedFiles`, `/AcroForm` are logged and the document is then text-extracted through
PyMuPDF, which ignores scripts and forms. Real judgments and government PDFs carry form
objects routinely, so refusing them would be wrong.

**Page overflow used to reject the whole document.** Now:

- `PDF_PAGE_OVERFLOW_MODE=truncate` (default) — read the first `MAX_FILE_PAGES` pages,
  record `truncated: true`, `pages_ingested`, `total_pages`, and log it.
- `PDF_PAGE_OVERFLOW_MODE=reject` — the old behaviour.

The page budget stays bounded either way, so memory and extraction cost are unchanged.
The vault ingester also had **no page cap at all** — it looped over every page while the
session uploader rejected anything over the limit. Both now honour the same budget.

Hard failures that remain, all deliberate:

| Rejection | Why |
|---|---|
| not `.pdf` | only PDF is parsed |
| empty file | nothing to ingest |
| missing `%PDF` header | not a PDF whatever the extension says |
| over `MAX_FILE_SIZE_MB` | bounded request size |
| vault at `VAULT_MAX_FILES` | bounded per-vault storage |

## 8.3 To loosen further

Edit `.env`, then `docker compose restart backend`:

```
MAX_FILE_SIZE_MB=25
MAX_FILE_PAGES=800
VAULT_MAX_FILES=50
PDF_PAGE_OVERFLOW_MODE=truncate
```

Each of these is a resource bound. Raising them raises peak memory during ingestion on a
machine with ~2.86 GB usable, so raise one at a time and watch `docker stats`.

## 8.4 Scanned PDFs

A scanned PDF with no text layer extracts to nothing and produces no chunks. There is no
OCR in the pipeline. This is a real limitation, not a bug — adding OCR means a new
dependency and a much larger per-document cost.

---

# 9. Project vaults

## 9.1 What was wrong

The backend was complete — create, list, patch, delete, upload, document list, per-document
status, `GET /vaults/{id}/conversations`. The API client had all of it. Uploading to a
selected vault worked. **The UI just never showed any of it.** Selecting a vault set
`activeVaultId` and nothing else: the Conversations list was a flat global list, and the
vault row had no children. So a vault looked like an empty folder with no way to put
anything in it.

Root cause of the invisible nesting: `GET /chat/sessions` did not return
`project_vault_id`, so the sidebar could not tell which chats belonged to which vault.

## 9.2 What now happens

- `GET /chat/sessions` includes `project_vault_id` (additive; no consumer breaks).
- Selecting a vault expands it in place, showing **+ New chat in this vault**, that vault's
  chats, and its documents with live ingestion status.
- The main Conversations list shows unfiled chats only, so a vault's chats are not listed
  twice.
- Chats started while a vault is selected are bound to it — `apiClient.chat` already
  passed `activeVaultId`, and the binding survives restarts.

## 9.3 How to use it

1. Sidebar → **Project Vaults** → **+** → name it.
2. Click the vault. It expands.
3. **+ New chat in this vault**.
4. In the chat box the upload button reads **Upload to Vault** — that PDF is indexed
   permanently into this vault's own collection, not just this session.
5. Ask. Vault documents rank ahead of statutes, and citations point at your document.

No rebuild needed for any of the frontend part — Vite HMR picks it up. The
`project_vault_id` field needs `docker compose up -d --build backend`.

---

# 10. MCP legal sources — **not built**

## 10.1 What exists

| File | Role |
|---|---|
| `app/mcp/gateway.py` | request gateway |
| `app/mcp/policy_engine.py` | what a server may be asked |
| `app/mcp/permission_layer.py` | approval boundary |
| `app/mcp/tool_registry.py` | discovered tools |
| `app/mcp/server_manager.py` | lifecycle, config-driven only |
| `app/config/mcp_servers.yaml` | server declarations — **`servers: {}`** |
| `app/config/legal_sources.yaml` | outbound domain allowlist |
| `app/network/mode_enforcer.py` | OFFLINE/ONLINE gate, SSRF, private-IP block |

The allowlist already names the sources: `indiacode.nic.in` (central and state
enactments), `indiankanoon.org` (judgments), `sci.gov.in`, `mca.gov.in`,
`egazette.gov.in`, with per-domain rate limits. Blogspot, WordPress, Reddit, X, Facebook
and Quora are explicitly denied.

`server_manager` reports a server as `configured` (executable present) or `unavailable`,
and **never** `connected` without a real handshake. The registry is empty on purpose:
nothing claims a connection it does not have.

## 10.2 What is missing

The four or five servers themselves. Each needs an MCP server that queries its source,
plus verification over the network — which could not be done from the environment this
work ran in, and writing four unexercised network clients would be worse than leaving the
registry honest.

## 10.3 To add one

```yaml
# app/config/mcp_servers.yaml
servers:
  indiacode:
    transport: stdio
    command: ["node", "/opt/mcp/indiacode/index.js"]
    description: "Central and State enactments from indiacode.nic.in"
    domain: "statutory"
    capabilities: ["get_section", "verify_citation"]
    enabled: false      # flip to true only after a real handshake
```

Then set `NETWORK_MODE=ONLINE`. Even then every request passes the allowlist, SSRF check,
private-IP block, timeout, request cap, provenance tracking and audit log. Offline remains
the default and must make **no** external calls.

A note on sequencing: MCP verification is only testable once the statutory corpus is
indexed, because there has to be a local citation to verify against.

---

# 11. Local law agents — **not built**

Intended as narrow, bounded roles rather than a general agent: query classification,
section extraction, citation verification. Any of them must inherit the existing
orchestration limits — max steps, max tool calls, max execution time, cancellation,
circuit breaker, audit. The existing research orchestration limits must not be raised to
accommodate them.

---

# 12. Tests

```powershell
docker compose exec backend python -m pytest -q
```

Last run: **305 passed, 17 failed**, all seventeen accounted for.

| Group | Count | Status |
|---|---|---|
| Hallucinated citation resolving as valid | 1 | **fixed** — the act/slug fallback restriction in §5.2 |
| Assertions on the old `<data>` tag | 2 | **updated** to the `slug=` contract |
| Statutory corpus absent from the container | 8 | recreate the container; three new diagnostics added |
| Disk probe returning `None` | 1 | **fixed** — §7.3 |
| Config-dependent, not defects | 4 | no second local model configured; compose file not in the image; `409` from the working idempotency guard; act index needs the corpus |
| Vault/domain-gate and Layer 3 fast path | — | fixed earlier in the work |

Security tests cover prompt injection, jailbreak attempts, malicious retrieved
instructions, SQL injection, SSRF, directory traversal, malicious PDFs, PII leakage,
authentication bypass, authorization bypass, cross-vault data leakage, rate-limit bypass
and secret exposure. Run them before trusting any change to the defence layers.

---

# 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Every legal answer says insufficient evidence | corpus not indexed | `/statutes/corpus-status`, then §1.4 |
| `failed to connect to the docker API` | Docker Desktop not running | start Docker Desktop, wait for the whale icon |
| Backend unhealthy on first start | cold imports of torch/transformers/spacy | `start_period` is 180 s; wait, then check logs |
| Ollama port conflict | native Ollama already on 11434 | leave the `local-ollama` profile off |
| `503` "workspace database is not reachable" | native Postgres down or wrong port | check port **5433**, `DFRAG_PG_HOST/PORT` |
| Answers have no citations | model ignoring the contract | check the reminder line is still in `layer2_trusted_context.py` |
| Citation graph looks fake | old build | frontend is HMR; hard-reload the browser |
| Model download never starts | disk probe was returning 0 GB free | fixed in §7.3; rebuild the backend |
| Frontend change not showing | editing outside the bind mount | files must be under `./frontend` |
| Vault looks empty | old backend without `project_vault_id` | `docker compose up -d --build backend` |

---

# 14. Open items

1. **MCP legal servers** (§10.2) — the largest remaining piece.
2. **Local law agents** (§11).
3. **`GENERATOR_CONTEXT_TOKENS` 4096 → 8192** (§7.4) — a RAM decision, needs watching.
4. **OCR for scanned PDFs** (§8.4) — new dependency, weigh the cost.
5. **`HF_TOKEN` in `backend/.env` is a live value.** Run
   `git log -p -- backend/.env`. If it was ever committed, rotate it — the git history
   keeps it even after the file changes.
6. **Empty-string env vars.** `OLLAMA_FALLBACK_MODEL` and `MODELS_DISK_PATH` are both
   blank. The disk one is now handled; audit the rest of `.env` for the same pattern and
   comment out anything meant to take a code default.

# 11. Statutes, external sources, agentic retrieval (added in the stabilization pass)

- **Importing Acts:** `git clone --depth 1 https://github.com/nyaayaIN/laws-of-india <dir>` then
  `python backend/scripts/import_laws_of_india.py <dir> --acts "<name substring>" ...`, then
  `python backend/scripts/seed_tier1.py`. Everything imports as `unverified` with the upstream commit
  recorded; upstream is CC BY-NC-SA 4.0 and lags amendments. It has no BNS/BNSS/BSA.
  Only a human diff against India Code may set `verified_at`.
- **eCourtsIndia** (`ecourts_case_search`): set `ECOURTSINDIA_API_KEY` in `.env`, switch the network
  mode to ONLINE. Results are case metadata labelled EXTERNAL SOURCE; queries are PII-scrubbed. It is
  the only online connector that works; `kanoon_case_search`, `live_statute_checker` and
  `indiacode_fetcher` report "not configured". Vaquill's API covers US law only and is unused.
- **Agentic retrieval:** `AGENTIC_RETRIEVAL_ENABLED=true` turns on a bounded LangGraph planner
  (`app/agents/retrieval_agent.py`) that splits multi-part questions, retrieves per part and retries
  uncovered parts once. It only chooses queries; sanitizer, validator, ownership and egress guard are unchanged.
- **Migrations:** `alembic upgrade head` (adds document storage columns; verified up/down/up).
- **Session ownership:** a session id belongs to whoever first uses it; MCP calls, session uploads and
  `/memory/documents/*` return 404 for anyone else.
