#!/bin/bash

# 获取脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 检查 .venv 是否存在
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv .venv
    echo "[INFO] Installing dependencies..."
    source .venv/bin/activate
    pip install -r requirements.txt
    echo "[INFO] Installing Playwright browsers..."
    playwright install
else
    source .venv/bin/activate
fi

# 检查并释放端口 5005
PORT=5005
echo "[INFO] Checking port $PORT..."
# Check if lsof is available
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -t -i:$PORT)
    if [ -n "$PID" ]; then
        echo "[WARN] Port $PORT is occupied by PID $PID. Killing it..."
        kill -9 $PID
    fi
else
    echo "[WARN] 'lsof' not found. Skipping port check."
fi

echo "[INFO] Starting Lovart Backend Server..."
echo "[INFO] Listening on 0.0.0.0:5005"

# 设置环境变量
export HOST=0.0.0.0
export PORT=5005
export DEBUG=False
export PLAYWRIGHT_BROWSERS_PATH=0

# 启动服务
python main.py
