# Investment Tracker Research UI

A thin interface over the governed, paper-only Investment Tracker. It does not place orders, accept brokerage credentials, expose protected holdouts, or evaluate Phase-7 performance.

## Windows: easiest deployment

Prerequisite: Docker Desktop.

From this directory:

```powershell
.\start.ps1
```

Open `http://localhost:8080`.

## Cross-platform deployment

```bash
docker compose up --build -d
docker compose ps
```

Open `http://localhost:8080`. Set `INVESTMENT_TRACKER_PORT` if port 8080 is already in use.

Both containers have health checks. The web service waits for the API to become healthy before starting. Repository `data/` is mounted read-only into the API container.

## Current boundary

The Phase-7 card reads structural status through the existing governed collector. If evidence is unavailable or unverifiable, the API returns `PHASE7_UNKNOWN_ABSTAIN`.

The Research Strategy form is currently a UX preview for the future governed Strategy Factory. It does **not** run arbitrary strategy search yet. The orchestration contract must be implemented before that button can launch research, so the UI cannot bypass validation, holdout, or paper-only controls.

Live trading and brokerage credential handling remain outside this repository's current authority.
