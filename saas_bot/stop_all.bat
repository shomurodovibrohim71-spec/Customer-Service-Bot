@echo off
REM Aggressively stop ALL bot-related processes (including any orphans from
REM previous runs that were started outside the supervisor).

echo Stopping cloudflared...
taskkill /F /IM cloudflared.exe >nul 2>&1

echo Stopping all python processes running bot.py / uvicorn / run_all.py...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'bot\.py|uvicorn|run_all\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Done.
timeout /t 2 /nobreak >nul
