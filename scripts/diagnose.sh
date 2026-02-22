#!/bin/bash
# Folio 连接诊断脚本

echo "=== Folio 连接诊断 ==="
echo ""

# 1. 检查后端服务
echo "1. 检查后端API服务 (端口 8000)..."
if lsof -i :8000 | grep -q LISTEN; then
    echo "   ✅ 后端服务正在运行"
    lsof -i :8000 | grep LISTEN
else
    echo "   ❌ 后端服务未运行"
    echo ""
    echo "   请运行以下命令启动后端:"
    echo "   ./scripts/start_core.sh"
    echo "   或: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"
fi

echo ""

# 2. 检查前端服务
echo "2. 检查前端服务 (端口 8501)..."
if lsof -i :8501 | grep -q LISTEN; then
    echo "   ✅ 前端服务正在运行"
else
    echo "   ℹ️  前端服务未运行（需要手动启动）"
fi

echo ""

# 3. 检查数据库
echo "3. 检查 PostgreSQL..."
if docker ps | grep -q postgres; then
    echo "   ✅ PostgreSQL 正在运行"
else
    echo "   ❌ PostgreSQL 未运行"
    echo "   请运行: docker-compose up -d postgres"
fi

echo ""

# 4. 测试API连接
echo "4. 测试 API 连接..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ API 连接正常"
    curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
else
    echo "   ❌ 无法连接到 API"
    echo "   请确保:"
    echo "   1. 后端服务已启动"
    echo "   2. 没有防火墙阻止连接"
    echo "   3. 端口 8000 未被占用"
fi

echo ""

# 5. 检查环境变量
echo "5. 检查环境变量..."
if [ -f .env ]; then
    echo "   ✅ .env 文件存在"
    # 检查关键配置
    if grep -q "DATABASE_URL" .env; then
        echo "   ✅ DATABASE_URL 已配置"
    else
        echo "   ⚠️  DATABASE_URL 未配置"
    fi
else
    echo "   ⚠️  .env 文件不存在"
    echo "   请运行: cp .env.example .env"
fi

echo ""
echo "=== 诊断完成 ==="
echo ""
echo "如果后端服务未运行，请执行:"
echo "  ./scripts/start_core.sh"
echo ""
echo "如果前端服务未运行，请执行:"
echo "  cd streamlit_app && uv run streamlit run Home.py"
