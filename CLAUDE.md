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

streamlit_app/          # 前端 (7 个页面)
├── api_client.py       # HTTP 客户端 (140+ 方法)
├── Home.py             # 首页导航
└── pages/
    ├── 1_Assets.py     # 资产总览
    ├── 2_Accounts.py   # 账户管理
    ├── 3_Budgets.py    # 预算管理
    ├── 4_Expenses.py   # 日常记账
    ├── 5_Portfolio.py  # 投资组合
    ├── 6_Trades.py     # 交易录入
    └── 7_Reports.py    # 报表与数据管理

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
- Phase 4: ✅ 完成 (报表、数据导入导出)

## Phase 3 完成内容
1. ✅ 市值同步升级 — Tushare 单只股票查询，3 只 A 股 0.2s 完成
2. ✅ 投资组合端点 — `GET /investments/portfolio` + `GET /investments/pnl-analysis`
3. ✅ 投资组合页面 — 持仓分布饼图、P&L 表格、市值同步按钮
4. ✅ 交易录入页面 — 买入/卖出/分红录入
5. ✅ 分类管理 — CRUD API + 内联编辑 UI
6. ✅ 预算表格化 — 已完成/已取消预算改为表格展示

## Phase 4 完成内容
1. ✅ 报表生成服务 — 投资业绩、支出汇总、账户快照
2. ✅ CSV 导出服务 — 交易记录、支出记录、持仓快照、账户列表
3. ✅ CSV 导入服务 — 交易记录、支出记录、券商对账单（含验证）
4. ✅ 报表 API 端点 — 3 个报表生成端点
5. ✅ 导出 API 端点 — 4 个 CSV 下载端点
6. ✅ 导入 API 端点 — 3 个文件上传端点
7. ✅ 报表与数据管理页面 — 5 个 Tab（报表生成、数据导出、数据导入）

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

### 报表功能 (/api/v1/reports)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /investment-performance | 投资业绩报表 |
| GET | /expense-summary | 支出汇总报表 |
| GET | /account-snapshot | 账户快照报表 |

### 导出功能 (/api/v1/export)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /transactions | 导出交易记录 CSV |
| GET | /expenses | 导出支出记录 CSV |
| GET | /holdings | 导出持仓快照 CSV |
| GET | /accounts | 导出账户列表 CSV |

### 导入功能 (/api/v1/import)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /transactions | 导入交易记录 CSV |
| POST | /expenses | 导入支出记录 CSV |
| POST | /brokerage-statement | 导入券商对账单 CSV |

---

## CSV 格式规范

### 交易记录导入模板
```csv
date,symbol,name,asset_type,type,quantity,price,fees,currency,notes
2026-01-15,600000,浦发银行,stock,buy,100,10.50,5.00,CNY,
2026-01-20,00700,腾讯控股,stock,buy,50,350.00,10.00,HKD,
```
**必填列**: date, symbol, type, quantity, price

### 支出记录导入模板
```csv
date,amount,category,subcategory,merchant,payment_method,is_shared,notes
2026-01-15,50.00,餐饮,午餐,麦当劳,微信支付,false,
2026-01-20,1200.00,住房,房租,链家,银行转账,true,1月房租
```
**必填列**: date, amount, category

### 券商对账单（通用格式）
```csv
date,symbol,name,type,quantity,price,fees,currency
2026-01-15,600000,浦发银行,buy,100,10.50,5.00,CNY
2026-01-20,600000,浦发银行,sell,50,11.00,2.50,CNY
2026-01-25,600000,浦发银行,dividend,100,0.50,0,CNY
```
**必填列**: date, symbol, type, quantity, price

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
