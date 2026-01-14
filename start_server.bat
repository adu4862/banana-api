@echo off
cd /d "%~dp0"

:: Check if .venv exists
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
)

echo [INFO] Installing dependencies...
.venv\Scripts\pip install -r requirements.txt

:: Set target port
set PORT=5005

echo [INFO] Checking port %PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":%PORT%" ^| find "LISTENING"') do (
    echo [WARN] Port %PORT% is occupied by PID %%a. Killing it...
    taskkill /F /PID %%a >nul 2>&1
)

echo [INFO] Starting Lovart Backend Server...
echo [INFO] Listening on 0.0.0.0:%PORT%

:: Set environment variables
set HOST=0.0.0.0
set DEBUG=False

:: --- Browser Configuration ---
:: Option 1: Use Local Edge (Default)
set USE_LOCAL_EDGE=true

:: Start service
.venv\Scripts\python main.py

pause
