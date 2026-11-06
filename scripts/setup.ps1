param(
    [switch]$WithAsr
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Set-Location $backend

$pythonPath = $null
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $pythonPath = $pythonCommand.Source
}

if (-not $pythonPath) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        "C:\Python312\python.exe",
        "C:\Python313\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $pythonPath = $candidate
            break
        }
    }
}

if (-not $pythonPath) {
    Write-Host "Python was not found." -ForegroundColor Red
    Write-Host "Install Python 3.12 from https://www.python.org/downloads/windows/"
    Write-Host "and tick 'Add python.exe to PATH' during setup."
    exit 1
}

Write-Host "Using $pythonPath"
& $pythonPath -m venv .venv

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
