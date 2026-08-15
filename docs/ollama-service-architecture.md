# DFrage — Permanent Ollama Service Architecture

## Production-Grade Fix for "Failed to Connect to Ollama"

This guide replaces the fragile `ollama serve` terminal approach with a **Docker-based managed service** that auto-starts, auto-recovers on crash, and survives Windows reboots — no manual terminal sessions required.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│  Windows Host (Your Machine)                         │
│                                                      │
│  ┌─────────────────────┐    ┌──────────────────────┐ │
│  │  DFrage Backend     │    │  Ollama Container    │ │
│  │  FastAPI :8000      │───▶│  ollama/ollama:latest│ │
│  │  + Resilient Client │    │  Port: 11434         │ │
│  └─────────────────────┘    │  Restart: always     │ │
│                              │  GPU: NVIDIA RTX 2050│ │
│  ┌─────────────────────┐    │  Healthcheck: ✓      │ │
│  │  DFrage Frontend    │    └──────────────────────┘ │
│  │  Next.js :3000      │                             │
│  └─────────────────────┘                             │
└──────────────────────────────────────────────────────┘
```

---

## Why This Architecture Solves Your Problem Permanently

| Problem | Old Approach (Terminal) | New Approach (Docker) |
|---------|------------------------|----------------------|
| Ollama dies when terminal closes | Manual `ollama serve` every time | `restart: always` — daemon mode |
| Windows reboot kills Ollama | You must remember to restart | Docker Desktop auto-starts on boot |
| GPU memory pressure | Unmanaged, can OOM | Docker resource reservation |
| No health monitoring | Blind trust | Built-in healthcheck every 30s |
| Version conflicts | Global install conflicts | Containerized, pinned image |
| 502 on first request | Common | Resilient client retries with backoff |

---

## Step 1: Install Docker Desktop (One-Time Manual Work)

**Download**: https://www.docker.com/products/docker-desktop

**Installation steps for Windows:**

1. Download Docker Desktop installer
2. Run installer, select **"Use WSL 2 instead of Hyper-V"** (recommended)
3. After installation, open Docker Desktop
4. Go to **Settings → General →** check "Start Docker Desktop when you sign in to your computer"
5. Go to **Settings → Resources → WSL Integration →** ensure your default WSL distro is enabled
6. **Verify GPU support**:

```powershell
# Open PowerShell as Administrator and run:
docker run --gpus all --rm nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

If this prints your NVIDIA GPU info (GeForce RTX 2050), GPU passthrough is working.

---

## Step 2: Place `docker-compose.yml` in Your Project Root

Copy the provided `docker-compose.yml` to the **same directory as your `.env` file** (your DFrage project root).

---

## Step 3: Start Ollama as a Managed Service

```powershell
# Navigate to your project root
cd C:\path\to\dfrage-legal-workspace

# Start Ollama in the background (daemon mode)
docker compose up -d ollama

# Verify it's running
docker ps
# Should show: dfrage-ollama  running  0.0.0.0:11434->11434/tcp

# Verify health
curl http://localhost:11434/api/health
# Expected: {"status":"running"}
```

From this point on, **Ollama runs silently in the background**. You never need to open a terminal for it again. It starts when Docker Desktop starts (which is at Windows boot, if you enabled it).

---

## Step 4: Pre-Pull Your Model

```powershell
# Pull qwen2.5:3b (recommended for your 4GB VRAM)
docker exec -it dfrage-ollama ollama pull qwen2.5:3b

# Optional: pull other models listed in your UI
docker exec -it dfrage-ollama ollama pull phi3.5
docker exec -it dfrage-ollama ollama pull llama3.2:3b
```

These models persist in the Docker volume and survive container restarts.

---

## Step 5: Integrate the Resilient Client into Your Backend

### 5a. Copy `ollama_client.py` into your backend

Place it in your backend source directory (e.g., `backend/src/ollama_client.py`).

### 5b. Update your `/chat` endpoint

Replace your current Ollama call with the resilient client:

```python
# OLD CODE (fragile — single attempt, no retry):
import httpx
response = httpx.post("http://localhost:11434/api/generate", json={...})
# If Ollama is down → 502 → user sees error

# NEW CODE (resilient):
from src.ollama_client import get_ollama_client

@app.post("/chat")
async def chat(request: ChatRequest):
    client = get_ollama_client()
    try:
        result = await client.chat(
            model="qwen2.5:3b",
            messages=[{"role": "user", "content": request.message}]
        )
        return result
    except RuntimeError as e:
        return {"error": "LLM temporarily unavailable. Retrying...", "retry_after": 5}
```

### 5c. Add the health endpoint

Copy `health_endpoint.py` content into your FastAPI `main.py`:
- Add the `lifespan` handler
- Add the `/health` route
- Add the `/models/pull` route

---

## Step 6: Verify Everything Works

```powershell
# 1. Check Ollama is running
docker ps
# 2. Check DFrage health endpoint
curl http://localhost:8000/health
# 3. Test a chat request from the frontend
#    Navigate to localhost:3000 and send a message
```

---

## Ongoing Operations

| Task | Command |
|------|---------|
| Check Ollama logs | `docker logs dfrage-ollama` |
| Restart Ollama | `docker restart dfrage-ollama` |
| Stop Ollama | `docker compose down` |
| Update Ollama image | `docker compose pull ollama && docker compose up -d ollama` |
| Check GPU usage | `docker exec -it dfrage-ollama nvidia-smi` |
| Pull a new model | `docker exec -it dfrage-ollama ollama pull <model_name>` |

---

## What Happens on Windows Reboot?

1. Windows boots
2. Docker Desktop auto-starts (if enabled in settings)
3. Docker starts the `dfrage-ollama` container (`restart: always`)
4. Ollama is available at `localhost:11434` within ~15 seconds
5. DFrage frontend can immediately send chat requests
6. **Zero manual intervention required**

---

## Troubleshooting

### "docker: not found"
→ Docker Desktop not installed. Install from docker.com.

### "could not select device driver nvidia"
→ Install NVIDIA Container Toolkit or enable GPU support in Docker Desktop settings.

### "permission denied" on `docker exec`
→ Run Docker Desktop as Administrator, or add your user to the `docker` group.

### Ollama container exits immediately
→ Check logs: `docker logs dfrage-ollama`. Common cause: another process using port 11434.

### Model too large for GPU
→ Use quantized models. `qwen2.5:3b` fits in 4GB VRAM. Larger models will auto-fallback to CPU (slower but functional).

### Container starts but health check fails
→ Wait 30-60 seconds. Ollama takes time to initialize on first launch.

---

## ChromeDB Telemetry Fix (Already Applied)

Confirm this line exists in your `.env`:

```
ANONYMOUS_TELEMETRY=false
```

This disables ChromaDB's PostHog telemetry and eliminates the warning messages.
