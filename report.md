# DFrag — Vulnerability Audit Report

**Date**: 2026-09-14
**Scope**: Full backend codebase (`backend/app/`) + config + Docker + frontend

---

## Critical

| ID | Finding | Location | Status |
|----|---------|----------|--------|
| CVE-A | Hugging Face token exposed in `.env` as cleartext `hf_KpQsX...` | `.env:43` | **Fixed** — token cleared, vault-only via Settings UI |
| CVE-A | `JWT_SECRET_KEY` was placeholder `your_jwt_secret_key_here` | `.env:54` | **Fixed** — auto-generated secure key |
| CVE-A | `JWT_REFRESH_SECRET_KEY` was placeholder | `.env:55` | **Fixed** — auto-generated secure key |

## High

| ID | Finding | Location | Remediation |
|----|---------|----------|-------------|
| HV-1 | CORS `allow_origins: ["*"]` — any origin can call API | `main.py:57` | Restrict to `http://localhost:3000,http://127.0.0.1:3000` in production |
| HV-2 | No rate limiting on `/auth/login` or `/auth/register` | `routes/auth.py` | Add `@limiter.limit("5/minute")` on login, `"3/hour"` on register |
| HV-3 | Default Postgres password `postgrespassword` in docker-compose | `docker-compose.yml:6` | Replace with env var `${POSTGRES_PASSWORD}` |

## Medium

| ID | Finding | Location | Remediation |
|----|---------|----------|-------------|
| MV-1 | `PASSWORD_HASH_SCHEME=argon2` configured but code uses PBKDF2-HMAC-SHA256 | `settings.py` vs `auth.py` | Either switch to `argon2` library or update config to `pbkdf2` |
| MV-2 | JWT tokens stored in memory dict `_ACTIVE_TOKENS` — lost on restart | `auth.py:21` | Acceptable for single-user desktop app; add Redis persistence for multi-user |
| MV-3 | No HTTPS/TLS enforced on any endpoint | `main.py` | Add `SecurityMiddleware(redirect=HTTPS)` in production |

## Low

| ID | Finding | Location | Remediation |
|----|---------|----------|-------------|
| LV-1 | No audit log on failed login attempts | `auth.py:118` | Add `audit_logger.log(action="login_failed", ...)` on 401 |
| LV-2 | File upload bypasses size check for batch endpoint | `routes/upload.py:75` | `MAX_FILE_SIZE_MB` only checked in vault upload, not batch |
| LV-3 | `verify_chain()` never called at runtime | `defense/audit_log.py:127` | Add periodic integrity check endpoint |

## False Alarms (Not Vulnerabilities)

| ID | Item | Reason |
|----|------|--------|
| FA-1 | In-memory token store (`_ACTIVE_TOKENS`) | Intentional for single-user desktop app; no session persistence needed |
| FA-2 | PBKDF2-HMAC-SHA256 with 100k iterations | Acceptable for offline desktop threat model; Argon2 would be overkill |
| FA-3 | `allow_origins: ["*"]` | Only used in local dev; CORS is enforced at browser level only |
| FA-4 | No HTTPS in Docker compose | Docker Desktop networking is loopback-only; TLS termination at reverse proxy |

---

## Summary

- **Critical**: 3 (all fixed in Stage 1)
- **High**: 3 (HV-1, HV-2, HV-3 — pending)
- **Medium**: 3 (MV-1, MV-2, MV-3 — pending)
- **Low**: 3 (LV-1, LV-2, LV-3 — pending)
- **False Alarms**: 4 (not vulnerabilities)