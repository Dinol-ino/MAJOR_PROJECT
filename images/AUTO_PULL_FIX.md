# DFrag Auto-Pull Fix — Docker Ollama Service (One-Click, Persistent, Storage-Safe)

> Audience: non-technical end user (e.g. lawyers) + developer appendix.
> Source of truth: Docker `ollama` service (`dfrag-ollama`, volume `ollama-models:/root/.ollama`).
> Scope: doc-only. No code changed by this file. Code fixes are listed as deferred.
> Location: `images/AUTO_PULL_FIX.md` alongside UI screenshots in `images/*.png`.

---

## 1. What "supposed to work" means

1. Open the web app → specs auto-detected, no terminal.
2. UI shows `Recommended for This Computer (~X GB)` + `Tier Matched` catalog.
3. Click `Download & Set Up Automatically` → progress % → `Ready & Active`.
4. Close browser / restart PC / `docker compose down` → model stays downloaded.
5. Never re-download unless volumes are explicitly deleted (`down -v`).
6. Never fill the disk — pull is blocked if unsafe.

Chain in code:

- Detect: `backend/app/system/hardware_detector.py:31-40 detect()` (300s cache) → `_perform_detection():43-222` (winreg CPU on Windows, `psutil` RAM, torch → `nvidia-smi` → WMI GPU, `shutil.disk_usage(os.getcwd())`, AVX2). Parallel fast path: `backend/app/services/telemetry.py:255-305 sample()` + `201-250 compute_hardware_tier()`.
- Recommend: `backend/app/routes/models.py:80-203 GET /models/recommended` (live `GET {OLLAMA_URL}/api/tags timeout=2.0` + `registry.evaluate_model_fit()`) → `status_state ACTIVE / PULLED_INACTIVE / NOT_PULLED`. Legacy alternate: `backend/app/routes/recommend.py:65-89 GET/POST /recommend`. Auto-provision alternate: `backend/app/services/provisioning_service.py:180-192`.
- Tier: `backend/app/system/hardware_detector.py:243-304 get_auto_selected_tier()` — `effective_vram=vram-1.0`, `effective_ram=avail-1.0`, `usable=max(...)` → Tier2 `vram>=12 or usable>=16`, Tier1 `vram>=6 or usable>=8`, Tier0 `usable>=3`.
- Download path A (per-model): `frontend/src/components/HardwareForm.jsx:144-186 handlePullModel` → `frontend/src/api/client.js:666-722 pullModelStream` → `POST /models/pull?stream=true` → `backend/app/routes/models.py:206-312` → `POST {OLLAMA_URL}/api/pull` + smoke `POST /api/generate`.
- Download path B (one-click): `HardwareForm.jsx:201-259 handleStartProvisioning` → `client.js:727-738 startProvisioning` → `POST /models/provision` → `provisioning_service.py:163-310 _run_provisioning (checking → compatibility_check → _check_installed → storage → downloading → verifying → health_check → ready)`.
- Startup: `backend/app/main.py:26-46 lifespan` → `backend/app/runtime/manager.py:321-357 warmup_floor_model()` when `AUTO_PULL_ON_STARTUP=true`.
- UI entry: `frontend/src/components/ManusHeader.jsx:186-204 Hardware Specs` / `Sidebar.jsx:141` → `App.jsx:215-223,241-250` → `HardwareForm` drawer / full view. One-click button: `HardwareForm.jsx:753-773`. Per-model button: `HardwareForm.jsx:933-952`.

Example for reference machine (Ryzen 5, ~10GB RAM, 512GB disk, modest VRAM):

- `ram_available ~8-9GB` → `effective_ram ~7-8GB` → Tier 0/1 boundary.
- Correct default: `qwen2.5:3b (~1.9GB, minimum)` floor. `qwen2.5:7b (~4.7GB)` only as opt-in if `safety_tier==SAFE`.
- Rule generalizes: always auto-select smallest `SAFE` model; never auto-pull 7B/14B without explicit user opt-in. This keeps any lawyer PC + CI runner safe.

---

## 2. One-click usage (non-technical user, Docker Ollama)

Prereqs:

- Docker Desktop + WSL2 (Windows), 10GB+ free disk, ports `3000/8000/11434` free.
- No terminal knowledge required beyond copy-paste of one command (launcher `.bat` is deferred to code phase).

Run:

```powershell
docker compose up -d --build
```

Then open `http://localhost:3000` → `Hardware Engine` → `Download & Set Up Automatically` → wait for `Ready & Active`.

Stop (keeps models):

```powershell
docker compose down
```

> Never run `docker compose down -v` unless you intend to delete all models, Postgres, Chroma, and SQLite data and re-download gigabytes.

What to expect on first run:

- `qwen2.5:3b` ≈ 1.9GB download. On slow disk/network this takes minutes. Progress bar should move; `0%` stuck >2 min = see §6.
- After `Ready & Active`, `Select` the model. Chat works offline afterward (Ollama container serves from persisted volume).

---

## 3. Storage-safety rule (do not crash the laptop)

Enforced gate (to be implemented in code phase; documented here as contract):

```text
required_gb = model.size_gb * 2.5 + 5.0  # download + extract + 5GB OS headroom
allow pull only if free_gb >= required_gb
warn if free_gb < 15 after pull
```

Examples:

| Model | size | required free to allow |
|---|---|---|
| `qwen2.5:3b` | 1.9GB | ~9.75GB |
| `qwen2.5:7b` | 4.7GB | ~16.75GB |
| `gemma2:9b` | 5.4GB | ~18.5GB |

- Check must measure the filesystem backing `ollama-models:/root/.ollama`, not container overlay `os.getcwd()`. Current code checks `os.getcwd()` (`hardware_detector.py:173`, `models.py:229`, `provisioning_service.py:325`) — known gap, fix deferred.
- Three gates currently disagree (`size*2.0` in `models.py:225` and `registry.py:121` vs `size*2.5` in `provisioning_service.py:326`) — unify to the formula above in code phase.
- On 512GB host with low free space: default to `qwen2.5:3b` only; refuse 7B with message `Free up X GB or stay on 3B`.

---

## 4. Persistence contract (Docker Ollama)

Compose today (`docker-compose.yml:20-33,54-56,104-108`):

```yaml
ollama:
  image: ollama/ollama:latest
  volumes: [ollama-models:/root/.ollama]
volumes: [pg-data, chroma-data, sqlite-data, ollama-models]
```

| Action | Ollama models (`ollama-models`) | Provisioning history (`provisioning.db`) | Chroma/SQLite/PG |
|---|---|---|---|
| Browser close / app close | Survives | Survives natively; survives in Docker while container exists | Survives |
| `docker compose down` | Survives (named volume kept) | Lost in Docker (no volume, overlay destroyed) | Survives |
| `docker compose down -v` | Destroyed — full re-pull required | Destroyed | Destroyed |

- `provisioning.db` path: `backend/app/services/provisioning_service.py:56 backend/provisioning.db` → `/workspace/provisioning.db` in container. No volume mounts it (`compose:54-56` only `chroma-data`, `sqlite-data`). Fix deferred: mount under `/workspace/db/` or dedicated volume.
- `OLLAMA_URL` dual-mode: `.env:3 http://127.0.0.1:11434` (host-native) vs `compose:59 http://ollama:11434` (Docker DNS, `environment:` overrides `env_file:`). Inside Docker backend must use `http://ollama:11434`. Do not change to host IP while using Docker Ollama.

Verify persistence (dev):

```powershell
docker volume ls
docker volume inspect MAJOR_PROJECT_ollama-models
docker exec dfrag-ollama ollama list
curl http://localhost:8000/health
curl http://localhost:8000/models/recommended
docker compose down
docker compose up -d
docker exec dfrag-ollama ollama list  # must still show model
```

---

## 5. GitHub Actions / any-user-PC envelope

- CI must not `ollama pull` multi-GB weights. Use:
  ```yaml
  MODEL_RUNTIME: mock
  AUTO_PULL_ON_STARTUP: "false"
  ```
  Assert `/models/recommended` contract + provisioning dry-run only.
- End-user default must run CPU-only without GPU. No `gpus:` in compose today → CPU inference. Document slowness for 7B on CPU; keep 3B floor as default so any PC works.
- Registry truth: `backend/app/config/model_registry.yaml` currently has 5 real tags (`qwen2.5:3b,7b`, `llama3.2:3b`, `gemma2:9b`, `mistral:7b`). Code also references phantom IDs (`dfrag-legal:7b` in `App.jsx:42`, `qwen2.5:14b` in `hardware_detector.py:276`, `gemma2:2b` in `settings.py:15` / `hardware_detector.py:291`) — fix deferred: add entries or retarget defaults to real tags.

---

## 6. Troubleshooting matrix (Docker Ollama)

| Symptom | Likely cause | Check |
|---|---|---|
| Frontend/backend never start on first `up` | Ollama healthcheck `curl` missing in `ollama/ollama` image (`compose:29`), `depends_on: service_healthy` blocks backend → frontend | `docker ps`, `docker inspect dfrag-ollama --format="{{.State.Health.Status}}"`, `docker logs dfrag-ollama`. Deferred fix: `["CMD-SHELL","ollama ps \|\| exit 1"]`, `start_period: 120s`, pin image version |
| `Ollama unreachable` banner (UI hardcodes `127.0.0.1:11434` text at `HardwareForm.jsx:826`) | Backend `OLLAMA_URL` wrong mode, or container not healthy | `docker logs dfrag-ollama`, `curl http://localhost:11434/api/version`, confirm backend env `OLLAMA_URL=http://ollama:11434` via `docker exec <backend> env` |
| Click download → immediate fail / `401` | All `/models/*`, `/telemetry/*` behind `Depends(get_current_user)` (`main.py:82-97`); `pullModelStream (client.js:669)` + `streamProvisioningProgress (:765)` use bare `fetch` without Bearer; `EventSource (HardwareForm.jsx:96-97)` cannot send headers | Open devtools network → `401` on `/api/models/pull` or `/api/api/models/provision/.../stream`. Deferred fix: `authFetch` + token query param for SSE |
| `404` on provision endpoints in production | Double `/api` prefix (`client.js:728,744,753,765,822,835` → `/api/api/...`) survives only via `vite.config.js:13 rewrite`; `BASE_URL` not exported (`client.js:1`) so `HardwareForm.jsx:96` falls back to relative path | Works in `vite dev`, breaks in `dist/` serve. Deferred fix: single prefix + exported base |
| Stuck at `0%` / timeout after minutes | `model_download_manager.py:46 Timeout(25.0)` kills multi-GB pull; provision uses `300s`, SSE uses `3600s` — inconsistent | Backend logs `Download failed / timeout`. Deferred fix: unify to `3600s` streaming |
| Downloads but UI shows not installed / re-pulls | `_check_installed` prefix match (`provisioning_service.py:312-321`, `manager.py:60-70`) false-positive/negative (`:latest`, case, `dfrag-legal` never in Ollama); `_pull_model:361 return True` even without `success` | `docker exec dfrag-ollama ollama list` vs UI `installed` flag |
| Wrong model recommended in Docker (always Tier 0) | Container sees cgroup CPU/RAM, no GPU (no `gpus:` in compose, no `nvidia-smi` in backend image) | Compare host Task Manager vs `GET /system/hardware` vs `GET /telemetry/sample` |
| History empty after `down/up` | `provisioning.db` ephemeral (see §4) | Expected until volume fix lands |
| `GET /health` fails | Missing `import httpx` in `main.py:109,115` | Backend logs `NameError` |

---

## 7. Verify checklist (before closing this issue)

- [ ] `docker compose up -d --build` → `dfrag-ollama (healthy)`, `backend (healthy)`, `frontend` all `Up`.
- [ ] `curl http://localhost:11434/api/version` → version JSON.
- [ ] `curl http://localhost:8000/health` → `ollama.status: ok`, `installed_models` list.
- [ ] UI → Hardware Engine shows live telemetry + `Tier Matched` + `Pull (~X GB)` / `Installed ✓`.
- [ ] Click recommended → progress → `Ready & Active` → `Select` → chat answers.
- [ ] `docker compose down` → `up -d` → `ollama list` still shows model, UI shows `Installed` without re-download.
- [ ] Low-disk machine → pull blocked with clear `Requires X GB free` message (after code fix).

---

## Appendix: files touched by future code fix (not changed here)

- `docker-compose.yml:22,29-33,59,54-56,88-90` — pin Ollama, fix healthcheck, add `provisioning.db` volume, prod frontend, `gpus:` docs.
- `backend/app/main.py:109,115` — add `import httpx`.
- `backend/app/system/model_download_manager.py:46` — timeout `25s` → streaming `3600s`.
- `backend/app/runtime/manager.py:331` — warm auto-tier model, not static `DEFAULT_MODEL`.
- `frontend/src/api/client.js:1,669,728,744,753,765,822,835` — export `BASE_URL`, single `/api` prefix, Bearer on streams.
- `frontend/src/components/HardwareForm.jsx:96-97` — fix telemetry SSE URL + auth.
- `backend/app/config/model_registry.yaml` + `App.jsx:42` + `hardware_detector.py:276,291` + `settings.py:15` — reconcile phantom IDs.
- `scripts/Start-DFrag.bat` (new, deferred) — `docker compose up -d --build` + poll `/health` + open browser; `Stop-DFrag` → `down` (not `-v`).
