@echo off
setlocal

cd /d "%~dp0..\.."

:: ── Checks ────────────────────────────────────────────────────────────────────
if not exist ".venv" (
    echo [jiri] .venv not found -- run setup first: scripts\windows\setup.bat
    exit /b 1
)

if not exist ".env" (
    echo [jiri] .env not found -- run setup first: scripts\windows\setup.bat
    exit /b 1
)

:: ── Activate & start ──────────────────────────────────────────────────────────
call .venv\Scripts\activate.bat

echo [jiri] Starting Jiri...
python -m jiri
