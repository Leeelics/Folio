#!/bin/bash
# Equilibra - 开发模式启动脚本（后端 + 前端）
# 用法: bash scripts/dev.sh [backend|frontend|all]
# 默认启动全部

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

MODE="${1:-all}"
BACKEND_PORT=8000
FRONTEND_PORT=8501

cleanup() {
    echo ""
    echo "正在停止服务..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo "已停止"
}
trap cleanup EXIT INT TERM

# 检查本地 PostgreSQL
if ! pg_isready &> /dev/null; then
    echo "⚠️  PostgreSQL 未运行，先执行 bash scripts/setup.sh"
    exit 1
fi

# 释放被占用的端口
free_port() {
    local port=$1
    if lsof -ti:"$port" &> /dev/null; then
        echo "释放端口 $port..."
        lsof -ti:"$port" | xargs kill -9 2>/dev/null
        sleep 1
    fi
}

start_backend() {
    free_port $BACKEND_PORT
    echo "启动后端 → http://localhost:$BACKEND_PORT"
    echo "API 文档 → http://localhost:$BACKEND_PORT/docs"
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT &
    BACKEND_PID=$!

    # 等待后端就绪
    for i in $(seq 1 30); do
        if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            echo "✅ 后端就绪"
            return 0
        fi
        sleep 1
    done
    echo "❌ 后端启动超时，查看日志排查"
    return 1
}

start_frontend() {
    free_port $FRONTEND_PORT
    echo "启动前端 → http://localhost:$FRONTEND_PORT"
    uv run streamlit run streamlit_app/Home.py \
        --server.address=0.0.0.0 \
        --server.port=$FRONTEND_PORT \
        --server.headless=true &
    FRONTEND_PID=$!
    echo "✅ 前端已启动"
}

case "$MODE" in
    backend)
        start_backend
        wait "$BACKEND_PID"
        ;;
    frontend)
        start_frontend
        wait "$FRONTEND_PID"
        ;;
    all)
        start_backend
        start_frontend
        echo ""
        echo "=== 开发服务已启动 ==="
        echo "后端: http://localhost:$BACKEND_PORT"
        echo "前端: http://localhost:$FRONTEND_PORT"
        echo "按 Ctrl+C 停止所有服务"
        wait
        ;;
    *)
        echo "用法: bash scripts/dev.sh [backend|frontend|all]"
        exit 1
        ;;
esac
