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

echo "[INFO] Starting Lovart Backend Server..."
echo "[INFO] Listening on 0.0.0.0:5000"

# 设置环境变量
export HOST=0.0.0.0
export PORT=5000
export DEBUG=False
export PLAYWRIGHT_BROWSERS_PATH=0

# 启动服务
python main.py
