# Stage 4 — Real Hardware Detection & Dynamic Model Management

**Independent of Stages 1–3** — can be built in parallel by a different team member/session.

## The current gap

**Confirmed evidence:** `backend/app/routes/recommend.py:7-11` —
```python
@router.post("/recommend", response_model=RecommendResponse)
async def recommend_endpoint(request: RecommendRequest):
    recs = get_recommendation(request.ram_gb, request.vram_gb)
```
`RecommendRequest` takes `ram_gb`/`vram_gb` as **user-typed form fields**
(`frontend/src/components/HardwareForm.jsx`). There is no automatic hardware detection anywhere in
the backend, and no automatic model download — `ollama_client.py` only raises an error telling the
user to manually run `ollama pull {model}` if the model is missing. This is the gap between "smart
installer" and what's actually shipped.

## 4.1 Real hardware detection

**Task:** new module `backend/app/platform/hardware.py`:
1. RAM: `psutil.virtual_memory().total`.
2. CPU: `psutil.cpu_count(logical=False)` and `platform.processor()`.
3. GPU/VRAM: try `torch.cuda.is_available()` + `torch.cuda.get_device_properties(0).total_memory`
   if `torch` is installed; fall back to parsing `nvidia-smi --query-gpu=memory.total --format=csv`
   via subprocess if available; fall back to "no GPU detected" if neither succeeds. **This must
   never crash** — wrap each detection method in try/except and fall back to the next, ending in a
   safe "assume CPU-only, minimum tier" default if all detection fails.
4. Disk free space: `shutil.disk_usage()`.
5. OS: `platform.system()`.
6. Return a structured `HardwareProfile` dataclass, not raw dict, so downstream code gets type
   safety.

## 4.2 Make `/recommend` auto-detect, keep manual override

**Task:**
1. Change `RecommendRequest` fields (`ram_gb`, `vram_gb`) to `Optional`. If omitted, call
   `hardware.py`'s detection and use the real values. If provided, honor the user's override (some
   users legitimately want to force a smaller model even on strong hardware).
2. **Do not break the existing contract** — the fields must stay accepted as-is for backward
   compatibility with any existing caller; this is purely making them optional, not removing them.
3. Extend `backend/app/platform/model_catalog.py`'s tiering logic (currently in
   `backend/app/model/recommend.py`'s `get_recommendation`) to also branch on detected GPU/VRAM,
   not just RAM — currently VRAM is accepted as an input but confirm it's actually used in the
   tiering branches, not just RAM.

## 4.3 Auto-pull instead of "run this command yourself"

**Task:**
1. Add `backend/app/model/ollama_installer.py` calling Ollama's `/api/pull` endpoint with
   `"stream": true`, forwarding progress as newline-delimited JSON.
2. Add `POST /models/pull` (streaming response) that the frontend calls after a model is
   recommended/selected, showing a real progress bar instead of a copy-pasteable shell command.
3. Keep the existing manual `ollama pull` instructions in `README.md` as a documented fallback for
   power users / headless server setups — don't remove the manual path, just stop making it the
   only path.
4. Fault tolerance: if a pull is interrupted (network drop, disk full), the endpoint must report a
   clear failure state the frontend can retry, not leave a partially-pulled model silently marked
   as the active default. Check disk space (via 4.1's `HardwareProfile`) before starting a pull
   large enough to plausibly fail — reject early with a clear message rather than failing halfway.

## 4.4 Dynamic context/chunk/token limits per hardware+model

**Task:** currently `MAX_FILE_SIZE_MB`/`MAX_FILE_PAGES` are static `.env` values regardless of
which model or hardware is active. Add logic (e.g. in `backend/app/config.py` or a new
`context_budget.py`) that derives:
- max chunks retrieved per query,
- max tokens included in the prompt,
- max concurrent PDF pages processed at ingest,

from the **selected generation model's context window** (already present per-model in
`model_catalog.py`, e.g. `qwen2.5:3b` → 4096, `gemma2:2b` → 8192) combined with available RAM from
`HardwareProfile`. This replaces hardcoded limits with limits that scale to whatever model/hardware
combination is actually active — a low-RAM machine running a small-context model should retrieve
fewer, smaller chunks than a high-RAM machine running a large-context model.

## 4.5 Frontend changes

**Task:** update `HardwareForm.jsx` to call `/recommend` with no body first (auto-detect path),
display the detected profile, and only show manual RAM/VRAM inputs behind an "override" toggle.
Add a progress UI for the new `/models/pull` streaming endpoint.

## Testing for this stage

- Unit tests for `hardware.py` mocking `psutil`/`torch`/`subprocess` to cover: GPU present, GPU
  absent, detection-fails-entirely (must return safe default, must not raise).
- Test `/recommend` with no body (auto-detect), with override values, and confirm response shape
  is unchanged from the current `RecommendResponse` schema.
- Test `/models/pull` progress streaming and its failure/retry path with a simulated interrupted
  download.
