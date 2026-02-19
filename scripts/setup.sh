#!/bin/bash
# Equilibra - 一键环境搭建脚本（本地 PostgreSQL）
# 用法: bash scripts/setup.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Equilibra 环境搭建 ==="
echo ""

# ---- 1. 检查基础工具 ----
echo "1. 检查基础工具..."

if ! command -v uv &> /dev/null; then
    echo "   uv 未安装，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "   uv $(uv --version)"

# ---- 2. 安装 Python 依赖 ----
echo ""
echo "2. 安装 Python 依赖..."
uv sync
echo "   ✅ 依赖安装完成"

# ---- 3. 配置环境变量 ----
echo ""
echo "3. 检查环境变量..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "   ✅ 已从 .env.example 创建 .env，请按需修改"
else
    echo "   ✅ .env 已存在"
fi

# ---- 4. 检查并启动本地 PostgreSQL ----
echo ""
echo "4. 检查 PostgreSQL..."

# 检查 PostgreSQL 是否已安装
if ! command -v psql &> /dev/null; then
    echo "   PostgreSQL 未安装"
    if command -v brew &> /dev/null; then
        echo "   正在通过 Homebrew 安装..."
        brew install postgresql@16
    else
        echo "   ❌ 请手动安装 PostgreSQL: brew install postgresql@16"
        exit 1
    fi
fi
echo "   psql $(psql --version | awk '{print $3}')"

# 启动 PostgreSQL 服务
if ! pg_isready &> /dev/null; then
    echo "   PostgreSQL 未运行，正在启动..."
    if command -v brew &> /dev/null; then
        brew services start postgresql@16 2>/dev/null || brew services start postgresql 2>/dev/null
    else
        pg_ctl -D /usr/local/var/postgres start 2>/dev/null || pg_ctl -D /opt/homebrew/var/postgres start 2>/dev/null
    fi
    sleep 2
fi

if pg_isready &> /dev/null; then
    echo "   ✅ PostgreSQL 已运行"
else
    echo "   ❌ PostgreSQL 启动失败，请手动检查"
    exit 1
fi

# ---- 5. 创建数据库和用户 ----
echo ""
echo "5. 检查数据库..."

# 创建用户（如果不存在）
if ! psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='equilibra'" postgres 2>/dev/null | grep -q 1; then
    createuser equilibra 2>/dev/null || true
    echo "   ✅ 创建用户 equilibra"
else
    echo "   ✅ 用户 equilibra 已存在"
fi

# 创建数据库（如果不存在）
if ! psql -tAc "SELECT 1 FROM pg_database WHERE datname='equilibra_db'" postgres 2>/dev/null | grep -q 1; then
    createdb -O equilibra equilibra_db 2>/dev/null || true
    echo "   ✅ 创建数据库 equilibra_db"
else
    echo "   ✅ 数据库 equilibra_db 已存在"
fi

echo ""
echo "=== 环境搭建完成 ==="
echo ""
echo "接下来可以运行:"
echo "  bash scripts/dev.sh          # 启动后端 + 前端（开发模式）"
echo "  uv run pytest -v             # 运行测试"
