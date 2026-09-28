# Local demo launcher (Windows). Run from the repo root.
# Terminals: this script starts backend + simulator; it prints the frontend command.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:PYTHONPATH = Join-Path $PSScriptRoot "backend"

Write-Host "Installing Python deps if needed..."
python -m pip install -q -r backend/requirements.txt

if (-not (Test-Path "frontend/node_modules")) {
    Write-Host "Installing frontend deps..."
    Push-Location frontend
    npm install
    Pop-Location
}

New-Item -ItemType Directory -Force -Path data | Out-Null

Write-Host ""
Write-Host "Starting backend on http://localhost:8000 ..."
Start-Process python -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--reload" -WorkingDirectory $PSScriptRoot

Start-Sleep -Seconds 2

Write-Host "Starting log simulator -> ./data/app.log ..."
Start-Process python -ArgumentList "-m","backend.simulator.generate_logs","--file","./data/app.log","--rps","30" -WorkingDirectory $PSScriptRoot

Write-Host "Starting Vite dashboard on http://localhost:5173 ..."
Start-Process npm -ArgumentList "run","dev" -WorkingDirectory (Join-Path $PSScriptRoot "frontend")

Write-Host ""
Write-Host "Open http://localhost:5173"
Write-Host "Wait until KPI baseline shows EWMA Tracking Active, then click Inject Spike."
