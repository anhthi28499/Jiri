#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# ── 1. Virtual environment ────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "[jiri] Creating virtual environment..."
  python3 -m venv .venv
else
  echo "[jiri] Virtual environment already exists, skipping."
fi

source .venv/bin/activate

# ── 2. Dependencies ───────────────────────────────────────────────────────────
echo "[jiri] Installing dependencies..."
pip install -q -r requirements.txt

# ── 3. Playwright ─────────────────────────────────────────────────────────────
if [ -f ".env" ] && grep -q "UI_TEST_ENABLED=true" .env 2>/dev/null; then
  echo "[jiri] UI_TEST_ENABLED=true detected — installing Playwright chromium..."
  playwright install chromium
fi

# ── 4. .env ───────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "[jiri] .env not found — copying from .env.example"
  cp .env.example .env
  echo ""
  echo "[jiri] Fill in .env (at minimum: GITHUB_TOKEN, WEBHOOK_SECRET), then run:"
  echo "  ./scripts/mac/runserver.sh"
  exit 1
fi

echo ""
echo "[jiri] Setup complete."
echo "  Run: ./scripts/mac/runserver.sh"
