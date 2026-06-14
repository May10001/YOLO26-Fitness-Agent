#!/bin/bash
# YOLO26 Fitness Agent - 后端一键启动脚本
# 用法: bash scripts/start_server.sh [--port 8002]

set -e

PORT=${2:-8002}
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "============================================"
echo "  YOLO26 Fitness Agent - Backend Server"
echo "============================================"

# 1. 检查 Python
python3 --version || python --version

# 2. 安装依赖
echo "[1/3] 安装 Python 依赖..."
pip install -r requirements.txt openai fastapi uvicorn langgraph -q

# 3. 下载 YOLO 模型（如果不存在）
if [ ! -f "yolo26n-pose.pt" ]; then
    echo "[2/3] 下载 YOLO 模型..."
    python -c "from ultralytics import YOLO; YOLO('yolo26n-pose.pt')"
else
    echo "[2/3] YOLO 模型已存在"
fi

# 4. 检查 API 配置
if [ ! -f "data/api_config.json" ]; then
    echo "[!] 警告: data/api_config.json 不存在，请先配置远程 API"
    echo "    参考 data/api_config.example.json 创建"
    exit 1
fi

# 5. 启动服务
echo "[3/3] 启动 FastAPI 服务 (端口 $PORT)..."
echo "============================================"
uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
