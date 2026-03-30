#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# ── Checks ────────────────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "[jiri] .venv not found — run setup first: ./scripts/mac/setup.sh"
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "[jiri] .env not found — run setup first: ./scripts/mac/setup.sh"
  exit 1
fi

# ── Activate & start ──────────────────────────────────────────────────────────
source .venv/bin/activate

echo "[jiri] Starting Jiri..."
python -m jiri
