#!/bin/bash
# Equilibra 核心功能测试脚本

echo "=== Equilibra 阶段1核心功能验证 ==="
echo ""

# 检查环境
echo "1. 检查依赖..."
if ! command -v uv &> /dev/null; then
    echo "✗ uv 未安装"
    exit 1
fi
echo "✓ uv 已安装"

# 检查数据库
echo ""
echo "2. 检查 PostgreSQL..."
if ! docker ps | grep -q postgres; then
    echo "⚠ PostgreSQL 未运行，正在启动..."
    docker-compose up -d postgres
    sleep 3
fi

if docker ps | grep -q postgres; then
    echo "✓ PostgreSQL 已运行"
else
    echo "✗ 无法启动 PostgreSQL"
    exit 1
fi

# 运行代码检查
echo ""
echo "3. 代码质量检查..."
uv run ruff check app/ --output-format=concise 2>&1 | tail -5

# 启动服务
echo ""
echo "4. 启动 API 服务..."
echo "服务将在 http://localhost:8000 启动"
echo "API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
