$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Virtual environment not found. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Set-Location $backend
$env:AUTOCUT_DEMO_MODE = "false"
Write-Host "AutoCut Worker starting..."
& $python -m app.worker
