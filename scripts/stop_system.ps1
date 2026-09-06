<#
.SYNOPSIS
    DFrag Complete System Shutdown (PowerShell).
    Stops background backend and frontend processes cleanly.
#>

$ROOT_DIR = (Get-Item $PSScriptRoot).Parent.FullName
$PID_FILE = Join-Path $ROOT_DIR "scripts\.system_pids.json"

Write-Host "Shutting down DFrag system..." -ForegroundColor Yellow

if (Test-Path $PID_FILE) {
    $pids = Get-Content $PID_FILE | ConvertFrom-Json
    if ($pids.BackendPid) {
        Stop-Process -Id $pids.BackendPid -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Backend process (PID: $($pids.BackendPid))." -ForegroundColor Green
    }
    if ($pids.FrontendPid) {
        Stop-Process -Id $pids.FrontendPid -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Frontend process (PID: $($pids.FrontendPid))." -ForegroundColor Green
    }
    Remove-Item $PID_FILE -Force -ErrorAction SilentlyContinue
}

# Fallback cleanup for orphan port bindings
Get-Process | Where-Object { $_.ProcessName -match "uvicorn" } | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "DFrag system stopped cleanly." -ForegroundColor Green
