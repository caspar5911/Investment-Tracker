# Investment Tracker Research UI

Thin UI over the governed, paper-only Investment Tracker. It does not place orders, accept brokerage credentials, expose protected holdouts, or evaluate Phase-7 performance.

## One-command deployment

From this directory:

\`\`\`bash
docker compose up --build
\`\`\`

Open http://localhost:8080.

The API mounts repository data read-only. If prospective evidence is unavailable or unverifiable, the UI reports PHASE7_UNKNOWN_ABSTAIN rather than inventing status.

## Current boundary

The Research Strategy form is the UX shell for the future governed Strategy Factory. It deliberately does not launch arbitrary strategy search yet. That orchestration needs its own contract so the UI cannot bypass validation, holdout, or paper-only controls.