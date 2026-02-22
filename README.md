# Folio - Personal Financial Management System

个人财务管理系统后端原型，集成 OKX、A/H 股数据、AI 分析与风险控制。

## 技术栈

- **Package Manager**: uv (Fast Python package installer)
- **Backend**: FastAPI (Asynchronous)
- **Database**: PostgreSQL + pgvector (Docker-ready)
- **ORM**: SQLAlchemy 2.0 (with pgvector support)
- **Financial Tools**: CCXT (for OKX), AkShare (for A/H Shares)
- **AI Framework**: LangGraph (Ready for LLM decision making)

## 项目结构

```
Folio/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # SQLAlchemy 模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── asset_manager.py    # 资产管理服务
│   │   ├── vector_store.py     # 向量数据库管理
│   │   └── risk_controller.py  # 风险控制逻辑
│   └── api/
│       ├── __init__.py
│       └── routes.py           # API 路由
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml              # uv 项目配置
├── uv.lock                     # uv 依赖锁定文件
├── .env.example
├── init.sql
└── README.md
```

## 核心功能

### 1. 数据库设计

- **assets**: 存储账户余额（银行、A 股、港股、OKX、分红险）
- **market_news**: 利用 pgvector 存储市场新闻的 Embedding
- **transactions**: 记录资金流水，特别标记 2026 年婚礼支出

### 2. 核心服务

- **AssetManager**: 异步集成 CCXT 获取 OKX 实时余额
- **VectorStoreManager**: 封装 pgvector 的增删改查逻辑
- **RiskController**: 计算总资产、资产占比、婚礼金安全水位

### 3. API 端点

- `GET /api/v1/portfolio/status`: 返回当前资产分布饼图数据
- `POST /api/v1/portfolio/sync-okx`: 同步 OKX 交易所余额
- `POST /api/v1/agent/analyze`: 触发 AI 逻辑，给出止盈止损建议
- `POST /api/v1/news/add`: 添加市场新闻并生成 Embedding
- `GET /api/v1/news/latest`: 获取最新市场新闻

## 快速开始

### 前置要求

- [uv](https://docs.astral.sh/uv/) - 快速的 Python 包管理器
- Docker & Docker Compose

### 1. 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip
pip install uv
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥
```

### 3. 启动服务

#### 使用 Docker Compose（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f app
```

#### 本地开发

```bash
# 安装依赖
uv sync

# 启动数据库
docker-compose up -d postgres

# 运行应用
uv run uvicorn app.main:app --reload

# 或者使用 uv run python
uv run python -m app.main
```

### 4. 访问 API 文档

打开浏览器访问: http://localhost:8000/docs

## API 使用示例

### 获取资产组合状态

```bash
curl http://localhost:8000/api/v1/portfolio/status
```

响应示例:
```json
{
  "total_assets": 500000.00,
  "allocation": {
    "银行": {
      "value": 200000.00,
      "percentage": 40.0,
      "accounts": [...]
    },
    "OKX": {
      "value": 100000.00,
      "percentage": 20.0,
      "accounts": [...]
    }
  },
  "wedding_finance": {
    "total_assets": 500000.00,
    "wedding_budget": 300000.00,
    "remaining_budget": 300000.00,
    "margin_of_safety": 0.4,
    "margin_percentage": 40.0,
    "investable_amount": 140000.00,
    "risk_level": "LOW",
    "days_until_wedding": 177
  },
  "recommendations": [
    "💰 可投资金额：¥140,000.00"
  ]
}
```

### 触发 AI 分析

```bash
curl -X POST http://localhost:8000/api/v1/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "分析当前市场情况并给出投资建议",
    "news_limit": 5
  }'
```

### 同步 OKX 余额

```bash
curl -X POST http://localhost:8000/api/v1/portfolio/sync-okx
```

### 添加市场新闻

```bash
curl -X POST "http://localhost:8000/api/v1/news/add" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "比特币突破 10 万美元",
    "content": "比特币价格今日突破历史新高...",
    "source": "财经新闻"
  }'
```

## 风险控制逻辑

系统会自动计算：

1. **总资产**: 所有账户余额的 CNY 等值
2. **资产占比**: 各类资产的百分比分布
3. **婚礼金安全水位**:
   - 剩余预算 = 30w - 已支出
   - 安全边际 = (总资产 - 剩余预算) / 总资产
   - 可投资金额 = 总资产 - 剩余预算 - 安全缓冲(20%)

4. **风险等级**:
   - CRITICAL: 资产不足以覆盖婚礼预算
   - HIGH: 安全边际 < 10%
   - MEDIUM: 安全边际 10-20%
   - LOW: 安全边际 > 20%

## 开发说明

### 依赖管理

```bash
# 添加新依赖
uv add package-name

# 添加开发依赖
uv add --dev package-name

# 更新依赖
uv sync --upgrade

# 查看已安装的包
uv pip list
```

### 代码格式化和检查

```bash
# 格式化代码
uv run black app/

# 代码检查
uv run ruff check app/

# 类型检查
uv run mypy app/
```

### 本地开发

```bash
# 安装依赖（包括开发依赖）
uv sync

# 启动数据库
docker-compose up -d postgres

# 运行应用（开发模式）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 数据库迁移

```bash
# 进入 PostgreSQL 容器
docker-compose exec postgres psql -U folio -d folio_db

# 查看表结构
\dt
\d assets
\d market_news
\d transactions
```

## 注意事项

1. **API 密钥安全**: 请妥善保管 `.env` 文件，不要提交到版本控制
2. **汇率处理**: 当前使用简化的汇率转换（USDT=7.2 CNY），生产环境应接入实时汇率 API
3. **AI 分析**: 需要配置 OpenAI API Key，建议使用 GPT-4 以获得更好的分析质量
4. **向量搜索**: pgvector 的索引需要一定数据量才能发挥最佳性能

## 后续扩展

- [ ] 集成 AkShare 获取 A/H 股实时行情
- [ ] 实现完整的 LangGraph 工作流（多 Agent 协作）
- [ ] 添加定时任务自动同步资产数据
- [ ] 实现更复杂的风险模型（VaR、夏普比率等）
- [ ] 添加用户认证和多用户支持
- [ ] 实现前端可视化界面

## License

MIT
