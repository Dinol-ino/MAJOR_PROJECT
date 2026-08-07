# Stage 6 — Enterprise Deployment & Operations

> **This stage transforms the local development stack into a production-grade platform.**
> Stage 5 built the runtime intelligence. Stage 6 makes it deployable, observable, auditable,
> and recoverable at enterprise scale.
>
> **Prerequisite:** Stages 1–5 stable. Stage 5 runtime abstraction layer in place.
> All `tests/` passing. `GET /health` returning healthy for all components.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                  STAGE 6 — OPERATIONS LAYER                         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  GitHub Actions CI/CD                                       │    │
│  │  ├─ Lint + Test on every PR                                │    │
│  │  ├─ Docker image build + push                              │    │
│  │  └─ Deploy to target environment                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Docker Compose (Single-Host / Team)                        │    │
│  │  ├─ backend (FastAPI + Uvicorn)                             │    │
│  │  ├─ frontend (Nginx serving React build)                    │    │
│  │  ├─ postgres (pgvector extension)                           │    │
│  │  ├─ redis                                                   │    │
│  │  ├─ ollama                                                  │    │
│  │  └─ langfuse (optional, compose profile)                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Kubernetes Manifests (Enterprise Scale)                    │    │
│  │  ├─ Deployment + HPA for backend                           │    │
│  │  ├─ StatefulSet for Postgres                               │    │
│  │  ├─ StatefulSet for Redis                                  │    │
│  │  ├─ DaemonSet for Ollama (GPU nodes)                       │    │
│  │  ├─ Secrets via Kubernetes Secrets / Vault                 │    │
│  │  └─ Ingress + TLS                                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Observability Stack                                        │    │
│  │  ├─ Langfuse (LLM traces, retrieval traces)                │    │
│  │  ├─ Prometheus + Grafana (metrics)                         │    │
│  │  └─ Structured JSON logging (stdout → log aggregator)      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Security & Access Control                                  │    │
│  │  ├─ RBAC (admin / user / readonly)                         │    │
│  │  ├─ Audit log (all actions, all users)                     │    │
│  │  ├─ Secrets Management (env files / Vault / K8s Secrets)  │    │
│  │  └─ TLS termination at ingress                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 6.A — Docker & Docker Compose

> The primary deployment target is Docker Compose on a single host. This is the path for
> law firms running on their own server, a cloud VM, or a high-spec workstation.

### 6.A.1 Production Docker Compose

File: `docker-compose.yml` (update existing file)

```yaml
version: "3.9"

services:
  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    volumes:
      - ollama_models:/root/.ollama
    # Uncomment for GPU support:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    env_file: .env
    environment:
      OLLAMA_URL: http://ollama:11434
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    volumes:
      - ./data:/app/data         # model registry, exports, corpus
      - ./chroma_db:/app/chroma_db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "${FRONTEND_PORT:-3000}:80"

volumes:
  postgres_data:
  redis_data:
  ollama_models:
```

**Langfuse compose profile** (opt-in, not always-on):

```yaml
# docker-compose.langfuse.yml — append with: docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up
services:
  langfuse:
    image: ghcr.io/langfuse/langfuse:latest
    restart: unless-stopped
    ports: ["4000:3000"]
    environment:
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/langfuse
      NEXTAUTH_SECRET: ${LANGFUSE_SECRET}
      NEXTAUTH_URL: http://localhost:4000
```

### 6.A.2 Backend Dockerfile

File: `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg, WeasyPrint, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl libgobject-2.0-0 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Alembic migrations then start Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
```

### 6.A.3 Frontend Production Dockerfile

File: `frontend/Dockerfile.prod`

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --production=false
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

File: `frontend/nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # React SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API and WebSocket to backend
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /chat/stream {
        proxy_pass http://backend:8000/chat/stream;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
    }
}
```

---

## 6.B — One-Command Installer

> A complete stranger should be able to install the system in one command. The installer
> handles Docker detection, environment setup, first-user creation, and model pull.

### 6.B.1 Linux / macOS Installer

File: `install.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> DFrag Enterprise Installer"

# Check Docker
if ! command -v docker &>/dev/null; then
    echo "Docker not found. Install from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! docker compose version &>/dev/null; then
    echo "Docker Compose v2 required. Update Docker Desktop or install the plugin."
    exit 1
fi

# Generate .env if not present
if [ ! -f .env ]; then
    cp .env.example .env
    JWT_SECRET=$(openssl rand -base64 48)
    REFRESH_SECRET=$(openssl rand -base64 48)
    REDIS_PASS=$(openssl rand -hex 16)
    DB_PASS=$(openssl rand -hex 16)
    sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=${JWT_SECRET}/" .env
    sed -i "s/JWT_REFRESH_SECRET_KEY=.*/JWT_REFRESH_SECRET_KEY=${REFRESH_SECRET}/" .env
    sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASS}/" .env
    sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${DB_PASS}/" .env
    echo "==> .env generated with secure secrets."
fi

# Start services
docker compose up -d

echo "==> Waiting for services to become healthy..."
timeout 120 bash -c 'until docker compose exec backend curl -sf http://localhost:8000/health; do sleep 3; done'

# Pull default model
docker compose exec ollama ollama pull qwen2.5:3b

echo "==> DFrag is ready at http://localhost:3000"
```

### 6.B.2 Windows Installer

File: `install.ps1`

```powershell
#Requires -Version 5.0
$ErrorActionPreference = "Stop"

Write-Host "==> DFrag Enterprise Installer"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found. Install from https://docs.docker.com/get-docker/"
    exit 1
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> .env created. Edit it to set your passwords before continuing."
    Write-Host "    Minimum: set POSTGRES_PASSWORD, REDIS_PASSWORD, JWT_SECRET_KEY"
    exit 0
}

docker compose up -d

Write-Host "==> Waiting for backend..."
$timeout = 120
$elapsed = 0
while ($elapsed -lt $timeout) {
    try {
        Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction Stop | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 3
        $elapsed += 3
    }
}

docker compose exec ollama ollama pull qwen2.5:3b

Write-Host "==> DFrag is ready at http://localhost:3000"
```

---

## 6.C — GitHub Actions CI/CD

### 6.C.1 CI Pipeline

File: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: dfrag_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: testpass
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }

      - name: Install dependencies
        working-directory: backend
        run: pip install -r requirements.txt

      - name: Run migrations
        working-directory: backend
        env:
          DATABASE_URL: postgresql+psycopg://postgres:testpass@localhost:5432/dfrag_test
        run: alembic upgrade head

      - name: Run tests
        working-directory: backend
        env:
          DATABASE_URL: postgresql+psycopg://postgres:testpass@localhost:5432/dfrag_test
          REDIS_URL: redis://localhost:6379/0
          MODEL_RUNTIME: mock
          JWT_SECRET_KEY: ci-test-secret
        run: pytest tests/ -v --tb=short --timeout=60

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend

  docker-build:
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ghcr.io/${{ github.repository }}/backend:latest
      - name: Build and push frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: ./frontend/Dockerfile.prod
          push: true
          tags: ghcr.io/${{ github.repository }}/frontend:latest
```

### 6.C.2 Security Scanning

File: `.github/workflows/security.yml`

```yaml
name: Security Scan

on:
  schedule:
    - cron: "0 2 * * 1"   # weekly Monday 2am
  push:
    branches: [main]

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Python dependency audit
        run: pip install pip-audit && pip-audit -r backend/requirements.txt
      - name: Node dependency audit
        run: npm audit --prefix frontend --audit-level=high
      - name: Docker image scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/${{ github.repository }}/backend:latest
          severity: HIGH,CRITICAL
          exit-code: 1
```

---

## 6.D — Kubernetes-Ready Design

> The Docker Compose stack is designed so that each service maps 1:1 to a Kubernetes
> workload. No refactoring is needed to move from Compose to Kubernetes.

### 6.D.1 Kubernetes Manifest Structure

```
k8s/
  namespace.yaml
  secrets/
    app-secrets.yaml           # JWT keys, DB password, Redis password
  postgres/
    statefulset.yaml
    service.yaml
    pvc.yaml
  redis/
    statefulset.yaml
    service.yaml
  ollama/
    daemonset.yaml             # GPU DaemonSet — one pod per GPU node
    service.yaml
  backend/
    deployment.yaml
    service.yaml
    hpa.yaml                   # HorizontalPodAutoscaler: scale on CPU > 70%
    configmap.yaml
  frontend/
    deployment.yaml
    service.yaml
  ingress/
    ingress.yaml               # nginx-ingress + cert-manager TLS
```

### 6.D.2 Backend HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dfrag-backend
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dfrag-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### 6.D.3 Deployment Principles

- **Stateless backend**: all session state is in Redis. All persistent data is in Postgres.
  Any backend pod can handle any request. Horizontal scaling is safe.
- **Ollama runs on GPU nodes**: deploy Ollama as a DaemonSet with `nodeSelector` targeting
  GPU nodes. The backend connects to Ollama via service DNS.
- **Postgres and Redis are not in Kubernetes for small installs**: use managed services
  (AWS RDS + ElastiCache, GCP CloudSQL + Memorystore) for production Kubernetes deployments.

---

## 6.E — Health Monitoring & Metrics

### 6.E.1 Health Endpoints

Extend `GET /health` (already exists) with granular sub-checks:

```
GET /health          -> overall: healthy | degraded | unhealthy
GET /health/db       -> postgres connection + pgvector extension check
GET /health/redis    -> redis PING check
GET /health/ollama   -> ollama /api/version + default model loaded check
GET /health/runtime  -> active runtime status from RuntimeManager (Stage 5)
```

Response format:

```json
{
  "status": "healthy",
  "checks": {
    "database": {"status": "healthy", "latency_ms": 2},
    "redis": {"status": "healthy", "latency_ms": 1},
    "ollama": {"status": "healthy", "model": "qwen2.5:7b", "latency_ms": 45},
    "runtime": {"status": "healthy", "backend": "ollama"}
  },
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

### 6.E.2 Prometheus Metrics

New module: `backend/app/observability/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

CHAT_REQUESTS_TOTAL = Counter(
    "dfrag_chat_requests_total",
    "Total chat requests",
    ["shield_on", "blocked_by"]
)

CHAT_LATENCY_MS = Histogram(
    "dfrag_chat_latency_ms",
    "Chat request latency in ms",
    ["shield_on"],
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000]
)

RETRIEVAL_CHUNKS = Histogram(
    "dfrag_retrieval_chunks",
    "Number of chunks retrieved per request",
    buckets=[0, 1, 2, 3, 5, 10]
)

ACTIVE_SESSIONS = Gauge(
    "dfrag_active_sessions",
    "Number of active Redis sessions"
)

MODEL_CONFIDENCE = Histogram(
    "dfrag_confidence_score",
    "Confidence score distribution",
    buckets=[0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0]
)
```

New endpoint: `GET /metrics` (Prometheus scrape endpoint, protected by `METRICS_AUTH_TOKEN`).

**Add to `.env.example` and `config.py`:**

```ini
METRICS_ENABLED=true
METRICS_AUTH_TOKEN=              # Bearer token for /metrics endpoint
```

### 6.E.3 Structured Logging

Replace all `logger.info()` calls with structured JSON logging using `structlog`.

Every log line includes: `timestamp`, `level`, `event`, `request_id`, `user_id`,
`session_id`, `latency_ms` (where applicable). Compatible with any log aggregator
(ELK, Loki, CloudWatch, Datadog).

```python
import structlog

logger = structlog.get_logger()

# Usage in chat.py:
logger.info(
    "chat_completed",
    session_id=request.session_id,
    user_id=str(current_user.id),
    latency_ms=total_ms,
    blocked_by=None,
    confidence=confidence_score,
    chunks_retrieved=len(retrieved_chunks),
)
```

**Add to `requirements.txt`:**

```
structlog>=24.0.0
prometheus-client>=0.21.0
```

---

## 6.F — Secrets Management

### 6.F.1 Local Development

`.env` file (never committed, gitignored). `.env.example` committed with placeholder values.

### 6.F.2 Docker Compose (Team / Staging)

Secrets passed via `env_file: .env` in compose. The `.env` file is generated by the installer
with cryptographically random values.

### 6.F.3 Kubernetes (Enterprise Production)

```yaml
# k8s/secrets/app-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: dfrag-secrets
  namespace: dfrag
type: Opaque
stringData:
  JWT_SECRET_KEY: "..."
  POSTGRES_PASSWORD: "..."
  REDIS_PASSWORD: "..."
```

For Vault integration: mount secrets as environment variables via the Vault Agent Sidecar.
No application code changes required — secrets still arrive as environment variables.

### 6.F.4 Secret Rotation

JWT secrets can be rotated by updating the Kubernetes Secret and rolling the backend deployment.
Active sessions are invalidated on rotation (users must re-login). This is intentional for
security events.

---

## 6.G — RBAC (Role-Based Access Control)

> The existing user model has a `role` field. Stage 6 formalizes three roles and enforces them
> at the API level.

### 6.G.1 Role Definitions

| Role | Capabilities |
|------|-------------|
| `admin` | All endpoints. User management. Model management. Audit log access. System config. |
| `user` | Chat. Upload (own workspace). View own sessions/history. Export own sessions. |
| `readonly` | Chat (no upload). View own sessions/history. No export. |

### 6.G.2 Role Enforcement

New decorator: `backend/app/auth/rbac.py`

```python
from functools import wraps
from fastapi import HTTPException, status

def require_role(*allowed_roles: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=None, **kwargs):
            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{current_user.role}' is not permitted for this action."
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
```

Apply to protected endpoints:

```python
# Only admins can manage models
@router.post("/models/pull")
@require_role("admin")
async def pull_model(...): ...

# Only admins see audit logs
@router.get("/audit/{session_id}")
@require_role("admin", "user")   # user can only see own session
async def get_audit(...): ...

# User management — admin only
@router.get("/admin/users")
@require_role("admin")
async def list_users(...): ...
```

### 6.G.3 Admin API Routes

New file: `backend/app/routes/admin.py`

```
GET  /admin/users                 -> list all users with role + last login
PUT  /admin/users/{id}/role       -> change user role
DELETE /admin/users/{id}          -> deactivate user (soft delete)
GET  /admin/audit                 -> full audit log (paginated, filterable)
GET  /admin/system/stats          -> active sessions, total documents, model usage
POST /admin/system/clear-cache    -> flush Redis cache (emergency)
GET  /admin/system/backup         -> trigger Postgres backup to BACKUP_DIR
```

---

## 6.H — Backup & Restore

### 6.H.1 Backup Script

File: `scripts/backup.sh`

```bash
#!/usr/bin/env bash
# Usage: ./scripts/backup.sh
# Creates a timestamped backup of Postgres + Redis + chroma_db

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEST="${BACKUP_DIR}/${TIMESTAMP}"
mkdir -p "${DEST}"

echo "==> Backing up Postgres..."
docker compose exec postgres pg_dump \
    -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${DEST}/postgres.sql.gz"

echo "==> Backing up Redis..."
docker compose exec redis redis-cli \
    -a "${REDIS_PASSWORD}" BGSAVE
sleep 2
docker compose cp redis:/data/dump.rdb "${DEST}/redis.rdb"

echo "==> Backing up ChromaDB..."
tar -czf "${DEST}/chroma_db.tar.gz" ./chroma_db/

echo "==> Backing up model registry and data..."
tar -czf "${DEST}/data.tar.gz" ./data/

echo "==> Backup complete: ${DEST}"
echo "==> Sizes:"
du -sh "${DEST}"/*
```

### 6.H.2 Restore Script

File: `scripts/restore.sh`

```bash
#!/usr/bin/env bash
# Usage: ./scripts/restore.sh ./backups/20260101_120000

set -euo pipefail

BACKUP="${1:?Usage: restore.sh <backup_dir>}"

echo "==> Restoring from: ${BACKUP}"

echo "==> Restoring Postgres..."
gunzip -c "${BACKUP}/postgres.sql.gz" | \
    docker compose exec -T postgres psql -U "${POSTGRES_USER}" "${POSTGRES_DB}"

echo "==> Restoring Redis..."
docker compose stop redis
docker compose cp "${BACKUP}/redis.rdb" redis:/data/dump.rdb
docker compose start redis

echo "==> Restoring ChromaDB..."
rm -rf ./chroma_db
tar -xzf "${BACKUP}/chroma_db.tar.gz"

echo "==> Restoring data..."
rm -rf ./data
tar -xzf "${BACKUP}/data.tar.gz"

echo "==> Restore complete. Restart the stack: docker compose restart"
```

### 6.H.3 Automated Backup Schedule

```yaml
# docker-compose.yml addition — backup sidecar
  backup:
    image: alpine
    profiles: ["backup"]
    volumes:
      - ./backups:/backups
      - ./scripts:/scripts
    environment:
      BACKUP_DIR: /backups
      BACKUP_RETAIN_DAYS: 30
    entrypoint: ["sh", "-c"]
    command: |
      "while true; do
        sleep 86400
        /scripts/backup.sh
        find /backups -type d -mtime +${BACKUP_RETAIN_DAYS} -exec rm -rf {} +
      done"
```

---

## 6.I — Session Persistence & Multi-User Support

> Session data survives restart because it is stored in Postgres. Redis is a cache only.
> The system is multi-user from Stage 1 (workspace isolation). Stage 6 verifies this at scale.

### 6.I.1 Session Persistence Contract

- **Redis TTL**: 2 hours of inactivity drops the Redis cache. This is acceptable.
- **Postgres persistence**: every chat message is written to `chat_messages` synchronously.
  On cold start, `chat.py` reloads the last 10 messages from Postgres.
- **On browser reload**: the session sidebar calls `GET /me/sessions` (Stage 5.L), which
  queries Postgres. The user sees all sessions including those older than the Redis TTL.

**No session data is ever lost due to restart, upgrade, or deployment.**

### 6.I.2 Multi-User Connection Isolation

Each user request carries a JWT. The JWT is verified before any database operation.
`workspace_id` is derived from `session_id` and validated against `session_records.owner_user_id`.
This is the Stage 1 contract. Stage 6 adds load testing to confirm it holds under concurrency.

Load test (using `locust`):

```
File: tests/load/locustfile.py
Scenario: 20 concurrent users, each sending 10 chat messages in sequence.
Assert: No user receives another user's session data.
Assert: P95 latency < 5000ms at 20 concurrent users.
Assert: Zero 500 errors.
```

---

## 6.J — Environment Profiles

Three named environment profiles:

| Profile | File | Use |
|---------|------|-----|
| `development` | `.env.dev` | Local dev, mock LLM, SQLite optional |
| `staging` | `.env.staging` | Dockerized, real Postgres, real Ollama, Langfuse on |
| `production` | `.env.prod` | Full stack, secrets from Vault or K8s Secrets |

**Profile switching:**

```bash
# Development
cp .env.dev .env && docker compose up

# Staging
cp .env.staging .env && docker compose up

# Production (environment variables already injected by Kubernetes)
docker compose up
```

Key differences between profiles:

```ini
# .env.dev
MODEL_RUNTIME=mock
LANGFUSE_ENABLED=false
METRICS_ENABLED=false
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# .env.staging
MODEL_RUNTIME=ollama
LANGFUSE_ENABLED=true
METRICS_ENABLED=true
LOG_LEVEL=INFO
LOG_FORMAT=json

# .env.prod
MODEL_RUNTIME=ollama
LANGFUSE_ENABLED=true
METRICS_ENABLED=true
LOG_LEVEL=WARNING
LOG_FORMAT=json
REFRESH_TOKEN_COOKIE_SECURE=true
```

---

## 6.K — Automatic Update System

### 6.K.1 Application Updates

```bash
# scripts/update.sh
git pull origin main
docker compose build backend frontend
docker compose up -d --no-deps backend frontend
# Migrations run automatically at container startup (CMD in Dockerfile)
echo "==> Update complete"
```

### 6.K.2 Model Registry Updates

The `backend/data/model_registry.yaml` file is updated via `git pull`. No container rebuild
required. The registry is reloaded on the next backend restart (or via `POST /admin/system/reload-registry`).

### 6.K.3 Ollama Model Updates

```bash
# scripts/update_models.sh
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull llama3.2:3b
```

---

## 6.L — Disaster Recovery

### 6.L.1 Recovery Time Objective (RTO)

| Failure | Recovery Action | Expected RTO |
|---------|----------------|-------------|
| Backend crash | Docker restarts automatically (`restart: unless-stopped`) | < 30s |
| Redis crash | Docker restarts. Active sessions fall back to Postgres. | < 60s |
| Postgres crash | Docker restarts. All data persisted on volume. | < 120s |
| Host machine restart | `docker compose up -d` on reboot (or systemd service) | < 5min |
| Full data loss | Restore from latest backup | < 30min |

### 6.L.2 Systemd Auto-Start (Linux)

File: `/etc/systemd/system/dfrag.service`

```ini
[Unit]
Description=DFrag Enterprise AI Platform
Requires=docker.service
After=docker.service

[Service]
WorkingDirectory=/opt/dfrag
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable dfrag
sudo systemctl start dfrag
```

---

## 6.M — All New Environment Variables

```ini
# 6.E Monitoring
METRICS_ENABLED=true
METRICS_AUTH_TOKEN=
LOG_LEVEL=INFO
LOG_FORMAT=json                # "json" | "text"

# 6.F Secrets
# All existing JWT, Postgres, Redis vars — no new additions

# 6.G RBAC
# Role is a column in the users table — no new env var

# 6.H Backup
BACKUP_DIR=./backups
BACKUP_RETAIN_DAYS=30

# 6.J Profile
APP_ENV=development            # development | staging | production
FRONTEND_PORT=3000
```

---

## 6.N — Testing Plan

| Test file | What is tested |
|-----------|---------------|
| `tests/test_health_endpoints.py` | All `/health/*` sub-checks with mocked services |
| `tests/test_rbac.py` | Role enforcement: admin-only routes reject user role |
| `tests/test_admin_api.py` | User list, role change, soft delete |
| `tests/test_metrics.py` | Prometheus metrics registration, counter increment |
| `tests/load/locustfile.py` | 20-user concurrency, isolation, P95 latency |
| `tests/test_backup_restore.py` | Backup script produces valid files, restore is idempotent |

### Manual Verification Before Sign-Off

1. Run `./install.sh` on a clean machine. Confirm it completes without errors.
2. Stop all containers (`docker compose down`). Start again (`docker compose up -d`).
   Confirm all prior sessions still visible in the UI.
3. Login as `user` role. Confirm `POST /models/pull` returns 403.
4. Login as `admin`. Confirm `GET /admin/users` returns the full user list.
5. Run `./scripts/backup.sh`. Confirm backup directory is created with three files.
6. Delete the postgres volume. Run `./scripts/restore.sh`. Confirm chat history is restored.
7. Confirm `GET /metrics` returns Prometheus-format text with all counters present.

---

## 6.O — Execution Order Within Stage 6

```
6.A  Docker Compose (production-grade, with healthchecks)
 ↓
6.B  Installer scripts (install.sh + install.ps1)
 ↓
6.C  GitHub Actions CI (test + build + push)
 ↓
6.E  Health endpoints (granular /health/*) + Prometheus metrics
 ↓
6.E  Structured logging (structlog)
 ↓
6.F  Secrets management documentation
 ↓
6.G  RBAC (role enforcement + admin API)
 ↓
6.H  Backup + restore scripts
 ↓
6.I  Load test (locust — session isolation + P95)
 ↓
6.J  Environment profiles (.env.dev / staging / prod)
 ↓
6.K  Update system (update.sh + model registry reload)
 ↓
6.D  Kubernetes manifests (after Compose is stable)
 ↓
6.L  Disaster recovery playbook
 ↓
Full test suite + manual verification — sign off only when all pass
```
