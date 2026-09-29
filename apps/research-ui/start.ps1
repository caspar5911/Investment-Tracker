$ErrorActionPreference = "Stop"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker Desktop is required. Install/start Docker Desktop, then rerun this script." }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Investment Tracker UI failed to start." }
Write-Host "Investment Tracker UI: http://localhost:$($env:INVESTMENT_TRACKER_PORT ?? '8080')"
docker compose ps
