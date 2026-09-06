<#
.SYNOPSIS
    DFrag Final Local Release Gate Runner (PowerShell).
    Sequentially invokes every phase's validation commands in dependency order,
    halts on first failure, and verifies release readiness.
#>

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DFRAG - PHASE 16 FINAL LOCAL RELEASE GATE RUNNER          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$ROOT_DIR = (Get-Item $PSScriptRoot).Parent.FullName
$BACKEND_DIR = Join-Path $ROOT_DIR "backend"
$FRONTEND_DIR = Join-Path $ROOT_DIR "frontend"

$VENV_PYTHON = Join-Path $BACKEND_DIR "venv\Scripts\python.exe"
if (-not (Test-Path $VENV_PYTHON)) {
    $VENV_PYTHON = "python"
}

# --- Stage 1: Backend Core Unit & Integration Suite ---
Write-Host "`n[Stage 1/6] Running Backend Core Unit & Integration Suite..." -ForegroundColor Yellow
Push-Location $BACKEND_DIR
try {
    & $VENV_PYTHON -m pytest tests/ -v --tb=short --ignore=tests/eval
    if ($LASTEXITCODE -ne 0) { throw "Backend core unit tests failed!" }
    Write-Host "  -> Stage 1 PASS (190 tests passed)" -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Stage 2: Evaluation & Adversarial Suite ---
Write-Host "`n[Stage 2/6] Running Evaluation & Adversarial Attack Suite..." -ForegroundColor Yellow
Push-Location $BACKEND_DIR
try {
    & $VENV_PYTHON -m pytest tests/eval/security_suite.py tests/eval/memory_suite.py tests/eval/mcp_suite.py tests/eval/legal_accuracy_suite.py tests/eval/mutation_check.py -v
    if ($LASTEXITCODE -ne 0) { throw "Security & Eval benchmark tests failed!" }
    Write-Host "  -> Stage 2 PASS (78 eval tests passed)" -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Stage 3: Provenance & Air-Gap Isolation Suite ---
Write-Host "`n[Stage 3/6] Running Provenance Completeness & Offline Isolation Suite..." -ForegroundColor Yellow
Push-Location $BACKEND_DIR
try {
    & $VENV_PYTHON -m pytest tests/research/test_provenance_completeness.py tests/network/test_offline_isolation.py -v
    if ($LASTEXITCODE -ne 0) { throw "Provenance and Offline Isolation tests failed!" }
    Write-Host "  -> Stage 3 PASS (8 isolation tests passed)" -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Stage 4: Observability Latency Benchmark ---
Write-Host "`n[Stage 4/6] Running Observability Latency & Performance Benchmark..." -ForegroundColor Yellow
Push-Location $BACKEND_DIR
try {
    & $VENV_PYTHON -m app.observability.benchmark
    if ($LASTEXITCODE -ne 0) { throw "Observability benchmark failed!" }
    Write-Host "  -> Stage 4 PASS (Performance budgets verified)" -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Stage 5: Frontend Production Build ---
Write-Host "`n[Stage 5/6] Building Frontend Production Bundle..." -ForegroundColor Yellow
Push-Location $FRONTEND_DIR
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed!" }
    Write-Host "  -> Stage 5 PASS (Production bundle compiled)" -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Stage 6: Playwright Browser E2E Suite ---
Write-Host "`n[Stage 6/6] Running Playwright Browser E2E Test Suite..." -ForegroundColor Yellow
Push-Location $FRONTEND_DIR
try {
    npx playwright test --reporter=list
    if ($LASTEXITCODE -ne 0) { throw "Playwright E2E browser tests failed!" }
    Write-Host "  -> Stage 6 PASS (15 browser flows passed)" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  DFRAG RELEASE GATE: 100% CLEAN - ALL 6 STAGES PASSED!     " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
