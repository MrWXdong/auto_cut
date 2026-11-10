$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Virtual environment not found. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Set-Location $backend
& $python -m app.storage_layout_cli
