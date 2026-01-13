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

echo [INFO] Starting Lovart Backend Server...
echo [INFO] Listening on 0.0.0.0:5000

:: 设置环境变量
set HOST=0.0.0.0
set PORT=5000
set DEBUG=False
set PLAYWRIGHT_BROWSERS_PATH=0

:: 启动服务
.venv\Scripts\python main.py

pause
