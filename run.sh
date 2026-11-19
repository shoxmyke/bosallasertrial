#!/usr/bin/env bash
# Build the frontend and start the planner on http://localhost:8000
set -e
cd "$(dirname "$0")"
pip install -q -r backend/requirements.txt
(cd frontend && npm install --no-audit --no-fund && npm run build)
cd backend
if [ ! -f data/planner.db ] && [ -f ../seed/Laser_Cutting_Planner_v35_November_2026.xlsx ]; then
  python -m app.cli import ../seed/Laser_Cutting_Planner_v35_November_2026.xlsx
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
