@echo off
cd /d "%~dp0"

:: 检查 .venv 是否存在
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    echo [INFO] Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt
    echo [INFO] Installing Playwright browsers...
    .venv\Scripts\playwright install
)

:: 设置目标端口
set PORT=5005

echo [INFO] Checking port %PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":%PORT%" ^| find "LISTENING"') do (
    echo [WARN] Port %PORT% is occupied by PID %%a. Killing it...
    taskkill /F /PID %%a
)

echo [INFO] Starting Lovart Backend Server...
echo [INFO] Listening on 0.0.0.0:%PORT%

:: 设置环境变量
set HOST=0.0.0.0
set DEBUG=False
set PLAYWRIGHT_BROWSERS_PATH=0

:: 启动服务
.venv\Scripts\python main.py

pause
