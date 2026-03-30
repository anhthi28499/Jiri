@echo off
setlocal

cd /d "%~dp0..\.."

:: ── 1. Virtual environment ────────────────────────────────────────────────────
if not exist ".venv" (
    echo [jiri] Creating virtual environment...
    python -m venv .venv
) else (
    echo [jiri] Virtual environment already exists, skipping.
)

call .venv\Scripts\activate.bat

:: ── 2. Dependencies ───────────────────────────────────────────────────────────
echo [jiri] Installing dependencies...
pip install -q -r requirements.txt

:: ── 3. Playwright ─────────────────────────────────────────────────────────────
if exist ".env" (
    findstr /C:"UI_TEST_ENABLED=true" .env >nul 2>&1
    if not errorlevel 1 (
        echo [jiri] UI_TEST_ENABLED=true detected -- installing Playwright chromium...
        playwright install chromium
    )
)

:: ── 4. .env ───────────────────────────────────────────────────────────────────
if not exist ".env" (
    echo [jiri] .env not found -- copying from .env.example
    copy .env.example .env
    echo.
    echo [jiri] Fill in .env (at minimum: GITHUB_TOKEN, WEBHOOK_SECRET), then run:
    echo   scripts\windows\runserver.bat
    exit /b 1
)

echo.
echo [jiri] Setup complete.
echo   Run: scripts\windows\runserver.bat
