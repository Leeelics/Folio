#!/bin/bash
# Equilibra 完整启动脚本

echo "=== Equilibra 启动脚本 ==="
echo ""

# 检查端口8000
echo "1. 检查端口8000..."
if lsof -i :8000 | grep -q LISTEN; then
    echo "   ⚠️ 端口8000被占用，正在释放..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 2
fi
echo "   ✅ 端口8000可用"

# 尝试启动PostgreSQL
echo ""
echo "2. 检查PostgreSQL..."
if docker ps | grep -q postgres 2>/dev/null; then
    echo "   ✅ PostgreSQL已运行"
else
    echo "   ⚠️ 尝试启动PostgreSQL..."
    if docker-compose up -d postgres 2>/dev/null; then
        echo "   ✅ PostgreSQL启动成功"
        sleep 3
    else
        echo "   ❌ 无法启动PostgreSQL（Docker可能未运行）"
        echo ""
        echo "   请手动启动Docker Desktop，然后重试"
        echo "   或使用SQLite模式（需修改配置）"
        exit 1
    fi
fi

# 启动后端API
echo ""
echo "3. 启动后端API服务..."
echo "   在后台启动: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"

# 使用nohup在后台启动
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

# 等待后端启动
sleep 5

# 检查后端是否成功启动
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ 后端API启动成功 (PID: $BACKEND_PID)"
    echo ""
    echo "=== 服务状态 ==="
    echo "✅ 后端API: http://localhost:8000"
    echo "✅ API文档: http://localhost:8000/docs"
    echo "✅ 前端: http://localhost:8501"
    echo ""
    echo "后端日志: tail -f backend.log"
    echo ""
    echo "停止后端: kill $BACKEND_PID"
else
    echo "   ❌ 后端启动失败，查看日志: backend.log"
    cat backend.log | tail -20
    exit 1
fi

echo ""
echo "=== 启动完成 ==="
echo ""
echo "提示:"
echo "- 后端已在后台运行"
echo "- 前端已在端口8501运行"
echo "- 如果前端显示连接错误，请刷新页面"
