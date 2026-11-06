param(
    [switch]$WithAsr
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Set-Location $backend

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python was not found in PATH." -ForegroundColor Red
    Write-Host "Install Python 3.12 from https://www.python.org/downloads/windows/"
    Write-Host "and tick 'Add python.exe to PATH' during setup."
    exit 1
}

Write-Host "Using $($python.Source)"
& $python.Source -m venv .venv

$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip

if ($WithAsr) {
    & $venvPython -m pip install -e ".[dev,asr]"
} else {
    & $venvPython -m pip install -e ".[dev]"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "FFmpeg was not found in PATH. Media nodes will fail until it is installed." -ForegroundColor Yellow
}

& $venvPython -m pytest
