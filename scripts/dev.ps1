param(
    [int]$Port = 8010
)

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
Write-Host "AutoCut API: http://127.0.0.1:$Port"
Write-Host "API docs:    http://127.0.0.1:$Port/docs"
& $python -m uvicorn app.api.main:app --host 127.0.0.1 --port $Port --reload
