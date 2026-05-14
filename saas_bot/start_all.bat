@echo off
setlocal
cd /d "%~dp0"

REM Run the Python supervisor that launches uvicorn, cloudflared, and the bot,
REM auto-updating .env with the fresh tunnel URL.
"%~dp0.venv\Scripts\python.exe" "%~dp0run_all.py"
