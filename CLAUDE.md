# Folio - 个人财务管理系统

## 技术栈
- Backend: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- Frontend: Streamlit (multi-page)
- Package Manager: uv
- Python 3.12+
- 行情数据: Tushare (A股/港股) + AkShare (美股 fallback)

## 项目结构
```
app/                    # 后端
├── models/             # 核心模型 (core.py, investment.py, stock.py, brokerage.py)
├── api/                # API 端点 (core_routes, investment_routes, stock_routes, brokerage_routes)
├── services/           # 业务逻辑 (asset_manager, investment_manager, stock_client...)
├── config.py           # Settings (pydantic-settings, 读取 .env)
├── database.py         # 数据库连接 + seed
└── main.py             # FastAPI 入口

streamlit_app/          # 前端 (6 个页面)
├── api_client.py       # HTTP 客户端 (100+ 方法)
├── Home.py             # 首页导航
└── pages/
    ├── 1_Assets.py     # 资产总览
    ├── 2_Accounts.py   # 账户管理
    ├── 3_Budgets.py    # 预算管理
    ├── 4_Expenses.py   # 日常记账
    ├── 5_Portfolio.py  # 投资组合
    └── 6_Trades.py     # 交易录入

tests/                  # 测试
```

## 关键设计
- Account: balance(现金) + holdings_value(持仓市值)
- Holding: is_liquid 标志区分高流动性资产(余额宝) vs 普通投资(股票)
- available_cash = balance + 高流动性持仓
- 支出从 cash 账户扣减，同时更新 budget spent
- StockClient: Tushare 单只股票 daily 接口查最新收盘价（免费接口，0.1s/只），AkShare 作为 fallback
- 市值同步跳过 bond/money_market/crypto 类型持仓

## 开发状态
- Phase 1: ✅ 完成 (核心模型 + API)
- Phase 2: ✅ 完成 (前端页面 + 预算 + 负债 + 日常记账)
- Phase 3: ✅ 完成 (投资组合增强 + Tushare 迁移)
- Phase 4: 🔲 高级功能 (报表、数据导入导出)

## Phase 3 完成内容
1. ✅ 市值同步升级 — Tushare 单只股票查询，3 只 A 股 0.2s 完成
2. ✅ 投资组合端点 — `GET /investments/portfolio` + `GET /investments/pnl-analysis`
3. ✅ 投资组合页面 — 持仓分布饼图、P&L 表格、市值同步按钮
4. ✅ 交易录入页面 — 买入/卖出/分红录入
5. ✅ 分类管理 — CRUD API + 内联编辑 UI
6. ✅ 预算表格化 — 已完成/已取消预算改为表格展示

---

## 环境变量 (.env)
```
DATABASE_URL=postgresql+asyncpg:///folio_db?host=/tmp&user=folio
OKX_API_KEY=...
OKX_SECRET_KEY=...
OKX_PASSPHRASE=...
OPENAI_API_KEY=...
TUSHARE_TOKEN=...          # Tushare pro API token
WEDDING_BUDGET=300000
WEDDING_DATE=2026-06-30
RISK_MARGIN_THRESHOLD=0.2
```

## API 端点

### 核心功能 (/api/v1/core)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST/GET | /accounts | 创建/列表 |
| GET/PUT/DELETE | /accounts/{id} | 详情/更新/删除 |
| POST/GET | /holdings | 创建/列表 |
| PUT/DELETE | /holdings/{id} | 更新/删除 |
| POST | /holdings/sync | 同步市值 (Tushare) |
| POST/GET | /expenses | 创建/列表 |
| DELETE | /expenses/{id} | 删除 |
| POST/GET | /budgets | 创建/列表 |
| GET/PUT/DELETE | /budgets/{id} | 详情/更新/删除 |
| POST | /budgets/{id}/complete | 完成预算 |
| POST | /budgets/{id}/cancel | 取消预算 |
| GET | /categories | 活跃分类列表 |
| GET | /categories/all | 全部分类（含停用） |
| POST | /categories | 创建分类 |
| PUT | /categories/{id} | 更新分类 |
| GET | /dashboard | 仪表盘 |
| POST/GET | /transfers | 创建/列表 |
| POST/PUT/DELETE | /liabilities | 创建/更新/删除 |
| POST | /liabilities/{id}/payment | 负债还款 |

### 投资功能 (/api/v1/investments)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST/GET | /transactions | 创建/列表 |
| GET/PUT/DELETE | /transactions/{id} | 详情/更新/删除 |
| GET | /holdings | 投资持仓 |
| GET | /holdings/{symbol}/history | 持仓历史 |
| GET | /holdings/summary | 持仓汇总 |
| GET | /portfolio | 投资组合（持仓+市值+分配比例） |
| GET | /pnl-analysis | 盈亏分析 |

---

## 快速开始
```bash
bash scripts/setup.sh                          # 首次搭建
bash scripts/dev.sh                            # 启动后端 + 前端
bash scripts/dev.sh backend                    # 只启动后端
bash scripts/dev.sh frontend                   # 只启动前端
```

## 常用命令
```bash
uv run uvicorn app.main:app --reload          # 启动后端
uv run streamlit run streamlit_app/Home.py    # 启动前端
uv run pytest tests/ -v                        # 运行测试
```
