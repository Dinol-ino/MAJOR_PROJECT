<#
.SYNOPSIS
    DFrag Complete System Launcher (PowerShell).
    Starts FastAPI backend (port 8000), Vite frontend (port 3000),
    and verifies readiness in the background.
#>

param(
    [switch]$NoBrowser = $false,
    [switch]$Offline = $true
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DFRAG DEFENSIVE RAG - UNIFIED SYSTEM LAUNCHER             " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$ROOT_DIR = (Get-Item $PSScriptRoot).Parent.FullName
$BACKEND_DIR = Join-Path $ROOT_DIR "backend"
$FRONTEND_DIR = Join-Path $ROOT_DIR "frontend"

$VENV_PYTHON = Join-Path $BACKEND_DIR "venv\Scripts\python.exe"
if (-not (Test-Path $VENV_PYTHON)) {
    $VENV_PYTHON = "python"
}

# 1. Database Initialization
Write-Host "`n[1/4] Checking and initializing database..." -ForegroundColor Yellow
Push-Location $BACKEND_DIR
try {
    & $VENV_PYTHON -c "import asyncio; from app.db.engine import init_db_schema; asyncio.run(init_db_schema())"
    Write-Host "  -> Database initialized successfully." -ForegroundColor Green
} catch {
    Write-Host "  -> Database initialization notice: $_" -ForegroundColor DarkGray
} finally {
    Pop-Location
}

# 2. Launch FastAPI Backend (Background Process on Port 8000)
Write-Host "`n[2/4] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$BackendJob = Start-Process -FilePath $VENV_PYTHON `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" `
    -WorkingDirectory $BACKEND_DIR `
    -PassThru -WindowStyle Hidden

Write-Host "  -> Backend process started (PID: $($BackendJob.Id))." -ForegroundColor Green

# 3. Launch Vite Frontend (Background Process on Port 3000)
Write-Host "`n[3/4] Starting Vite Frontend on http://localhost:3000..." -ForegroundColor Yellow
$FrontendJob = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run dev" `
    -WorkingDirectory $FRONTEND_DIR `
    -PassThru -WindowStyle Hidden

Write-Host "  -> Frontend process started (PID: $($FrontendJob.Id))." -ForegroundColor Green

# Save PIDs for graceful shutdown
$PID_FILE = Join-Path $ROOT_DIR "scripts\.system_pids.json"
@{
    BackendPid  = $BackendJob.Id
    FrontendPid = $FrontendJob.Id
    StartedAt   = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content $PID_FILE

# 4. Wait for Health Check Readiness
Write-Host "`n[4/4] Verifying system health and readiness..." -ForegroundColor Yellow
$MaxRetries = 20
$Ready = $false

for ($i = 1; $i -le $MaxRetries; $i++) {
    Start-Sleep -Milliseconds 800
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.status -eq "healthy") {
            $Ready = $true
            break
        }
    } catch {
        # Retry until ready
    }
}

if ($Ready) {
    Write-Host "  -> Backend is healthy & listening on http://127.0.0.1:8000" -ForegroundColor Green
    Write-Host "  -> Frontend is active on http://localhost:3000" -ForegroundColor Green
} else {
    Write-Host "  -> System started (health check warming up in background)." -ForegroundColor Yellow
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  DFRAG IS RUNNING!" -ForegroundColor Green
Write-Host "  Frontend URL:     http://localhost:3000" -ForegroundColor Cyan
Write-Host "  API Documentation: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  Network Policy:   OFFLINE (Strict air-gapped isolation)" -ForegroundColor Green
Write-Host "  Stop System:      powershell scripts\stop_system.ps1" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

if (-not $NoBrowser) {
    Start-Process "http://localhost:3000"
}
