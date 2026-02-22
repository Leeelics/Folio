# Folio - 个人财务管理系统

## 技术栈
- Backend: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- Frontend: Streamlit (multi-page)
- Package Manager: uv
- Python 3.12+

## 项目结构
```
app/                    # 后端
├── models/             # 11 个核心模型 (core.py, investment.py, stock.py, brokerage.py)
├── api/                # 30+ API 端点 (core, investment, stock, brokerage)
├── services/           # 业务逻辑 (asset_manager, investment_manager, stock_client...)
├── database.py         # 数据库连接
└── main.py             # FastAPI 入口

streamlit_app/          # 前端 (目标 6 个页面)
├── api_client.py       # HTTP 客户端 (100+ 方法)
├── Home.py             # 首页
└── pages/              # 1_资产总览, 2_账户管理, 3_预算管理, 4_日常记账
                        # Phase 3 新增: 5_投资组合, 6_交易录入

tests/                  # 测试 (54+ tests)
```

## 关键设计
- Account: balance(现金) + holdings_value(持仓市值)
- Holding: is_liquid 标志区分高流动性资产(余额宝) vs 普通投资(股票)
- available_cash = balance + 高流动性持仓
- 支出从 cash 账户扣减，同时更新 budget spent

## 开发状态
- Phase 1: ✅ 完成 (核心模型 + API)
- Phase 2: ✅ 完成 (前端页面 + 预算 + 负债 + 日常记账)
- **Phase 3: 🔨 进行中 (投资组合增强)**
- Phase 4: 🔲 高级功能 (报表、数据导入导出)

---

## Phase 3 任务总览

Phase 3 目标：投资组合增强，共 4 项工作：

1. **升级市值同步** — 当前 `sync_holdings_value` 使用随机 ±2% 模拟价格，需改为调用 AkShare 真实数据（`stock_client.py` 已有 AkShare 集成）
2. **新增投资组合端点** — `GET /api/v1/investments/portfolio` 汇总持仓 + 市值 + 分配比例；`GET /api/v1/investments/pnl-analysis` 计算盈亏
3. **新建投资组合页面** — `5_📈_投资组合.py`，展示持仓分布饼图、P&L 表格、市值趋势
4. **新建交易录入页面** — `6_📝_交易录入.py`，支持买入/卖出/分红录入，关联 investment_transactions

---

## Phase 3 三终端分工

### 启动方式

每个终端用 `claude --dangerously-skip-permissions` 启动，然后粘贴对应开场白：

```bash
# 三个终端分别执行
claude --dangerously-skip-permissions
```

---

### 信号协议（claude-mem 通信）

终端之间通过 claude-mem 发送完成信号，下游终端自动轮询。信号格式固定，便于搜索：

| 信号 | 发送方 | 含义 |
|------|--------|------|
| `SIGNAL:BACKEND_DONE` | Backend | A1-A3 全部完成，端点可用 |
| `SIGNAL:FRONTEND_DONE` | Frontend | B1-B4 全部完成，页面可测 |
| `SIGNAL:TESTING_DONE` | Testing | C1-C3 全部完成，测试通过 |

**轮询方式**: 完成独立任务后，用 `search(query="SIGNAL:XXX_DONE", project="folio")` 检查上游信号。如果未找到，等待 30 秒后重试（最多重试 20 次，共约 10 分钟）。

---

### Terminal A: Backend（范围: `app/` 目录）

**角色**: 后端开发，独占修改 `app/` 目录。

**开场白**（复制粘贴到新终端）:
```
读取 CLAUDE.md，我是 Backend 终端。按照 Phase 3 三终端分工执行任务 A1→A2→A3，全程自主完成，不要停下来问我。

工作流程：
1. search(query="Phase 3 backend", project="folio") 检查前序进展
2. 按顺序完成 A1、A2、A3（每个任务用 /tdd 驱动开发，完成后 /python-review）
3. 全部完成后发送信号: save_memory(text="SIGNAL:BACKEND_DONE - Phase 3 Backend 完成: A1 sync升级用AkShare替换随机模拟, A2 GET /investments/portfolio 端点, A3 GET /investments/pnl-analysis 端点", project="folio")
4. 最后 git add 并提交所有改动

注意：全程不要停下来问我确认，直接按 CLAUDE.md 中的任务列表和接口契约执行。遇到问题自行决策。
```

**任务列表**:
- **A1**: 升级 `POST /core/holdings/sync` — 修改 `app/api/core_routes.py` 中 `sync_holdings_value`，用 `app/services/stock_client.py` 的 AkShare 接口替换随机模拟
- **A2**: 新增 `GET /investments/portfolio` — 在 `app/api/investment_routes.py` 添加端点，汇总 InvestmentHolding + Holding 数据，返回持仓列表、总市值、分配比例
- **A3**: 新增 `GET /investments/pnl-analysis` — 在 `app/api/investment_routes.py` 添加端点，基于 InvestmentTransaction 计算每个持仓的成本、现价、盈亏额、盈亏率

---

### Terminal B: Frontend（范围: `streamlit_app/` 目录）

**角色**: 前端开发，独占修改 `streamlit_app/` 目录。

**开场白**（复制粘贴到新终端）:
```
读取 CLAUDE.md，我是 Frontend 终端。按照 Phase 3 三终端分工执行任务 B1→B2→B3→B4，全程自主完成，不要停下来问我。

工作流程：
1. search(query="Phase 3 frontend", project="folio") 检查前序进展
2. 立即开始 B1（交易录入页面，不依赖后端）
3. B1 完成后，轮询等待后端信号: search(query="SIGNAL:BACKEND_DONE", project="folio")
   - 如果未找到，sleep 30 秒后重试，最多重试 20 次
4. 收到信号后，先 git pull 拉取后端代码，然后继续 B2→B3→B4
5. 全部完成后发送信号: save_memory(text="SIGNAL:FRONTEND_DONE - Phase 3 Frontend 完成: B1 交易录入页面, B2 api_client新方法(get_portfolio/get_pnl_analysis), B3 投资组合页面, B4 Home快捷链接", project="folio")
6. 最后 git add 并提交所有改动

注意：全程不要停下来问我确认，直接按 CLAUDE.md 中的任务列表和接口契约执行。遇到问题自行决策。
```

**任务列表**:
- **B1**（立即开始）: 新建 `streamlit_app/pages/6_📝_交易录入.py` — 参考 `4_📝_日常记账.py` 的表单模式，支持买入/卖出/分红录入，调用 `api_client.create_transaction()`
- **B2**（Backend 完成后）: 在 `streamlit_app/api_client.py` 新增 `get_portfolio()` 和 `get_pnl_analysis()` 方法
- **B3**: 新建 `streamlit_app/pages/5_📈_投资组合.py` — 持仓分布饼图（st.plotly_chart）、P&L 表格、市值同步按钮
- **B4**: 更新 `streamlit_app/Home.py` 侧边栏快捷链接，包含 6 个页面

---

### Terminal C: Testing（范围: `tests/` 目录）

**角色**: 测试开发，独占修改 `tests/` 目录。

**开场白**（复制粘贴到新终端）:
```
读取 CLAUDE.md，我是 Testing 终端。按照 Phase 3 三终端分工执行任务 C1→C2→C3，全程自主完成，不要停下来问我。

工作流程：
1. search(query="Phase 3 testing", project="folio") 检查前序进展
2. 立即开始 C1（单元测试，mock 数据，不依赖后端）
3. C1 完成后，轮询等待后端信号: search(query="SIGNAL:BACKEND_DONE", project="folio")
   - 如果未找到，sleep 30 秒后重试，最多重试 20 次
4. 收到信号后，先 git pull 拉取后端代码，然后完成 C2（集成测试）
5. C2 完成后，轮询等待前端信号: search(query="SIGNAL:FRONTEND_DONE", project="folio")
   - 同样 sleep 30 秒重试，最多 20 次
6. 收到信号后，先 git pull 拉取前端代码，然后完成 C3（E2E 测试）
7. 运行 uv run pytest -v 确认全部通过
8. 全部完成后发送信号: save_memory(text="SIGNAL:TESTING_DONE - Phase 3 Testing 完成: C1 单元测试, C2 集成测试, C3 E2E测试。全部通过", project="folio")
9. 最后 git add 并提交所有改动

注意：全程不要停下来问我确认，直接按 CLAUDE.md 中的任务列表和接口契约执行。遇到问题自行决策。
```

**任务列表**:
- **C1**（立即开始）: 在 `tests/` 新增 `test_portfolio.py` — 为 portfolio 和 pnl-analysis 端点写单元测试（mock 数据库），参考 `tests/test_api.py` 的模式
- **C2**（Backend 完成后）: 在 `tests/test_api.py` 补充 portfolio/pnl-analysis 的集成测试
- **C3**（Frontend 完成后）: 在 `tests/test_e2e.py` 补充投资组合页面和交易录入页面的 E2E 测试

---

## 接口契约

Frontend 和 Testing 终端参考此契约开发，无需等待后端代码。

### 已有端点（Phase 1-2）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/core/accounts | 创建账户 |
| GET | /api/v1/core/accounts | 账户列表 |
| GET | /api/v1/core/accounts/{id} | 账户详情 |
| PUT | /api/v1/core/accounts/{id} | 更新账户 |
| DELETE | /api/v1/core/accounts/{id} | 删除账户 |
| POST | /api/v1/core/holdings | 创建持仓 |
| GET | /api/v1/core/holdings | 持仓列表 |
| PUT | /api/v1/core/holdings/{id} | 更新持仓 |
| DELETE | /api/v1/core/holdings/{id} | 删除持仓 |
| POST | /api/v1/core/holdings/sync | 同步市值（Phase 3 升级） |
| POST | /api/v1/core/expenses | 创建支出 |
| GET | /api/v1/core/expenses | 支出列表 |
| DELETE | /api/v1/core/expenses/{id} | 删除支出 |
| POST | /api/v1/core/budgets | 创建预算 |
| GET | /api/v1/core/budgets/{id} | 预算详情 |
| PUT | /api/v1/core/budgets/{id} | 更新预算 |
| DELETE | /api/v1/core/budgets/{id} | 删除预算 |
| POST | /api/v1/core/budgets/{id}/complete | 完成预算 |
| POST | /api/v1/core/budgets/{id}/cancel | 取消预算 |
| GET | /api/v1/core/categories | 分类列表 |
| GET | /api/v1/core/dashboard | 仪表盘 |
| POST | /api/v1/core/transfers | 创建转账 |
| GET | /api/v1/core/transfers | 转账列表 |
| POST | /api/v1/core/liabilities | 创建负债 |
| PUT | /api/v1/core/liabilities/{id} | 更新负债 |
| DELETE | /api/v1/core/liabilities/{id} | 删除负债 |
| POST | /api/v1/core/liabilities/{id}/payment | 负债还款 |
| POST | /api/v1/investments/transactions | 创建投资交易 |
| GET | /api/v1/investments/transactions | 投资交易列表 |
| GET | /api/v1/investments/transactions/{id} | 交易详情 |
| PUT | /api/v1/investments/transactions/{id} | 更新交易 |
| DELETE | /api/v1/investments/transactions/{id} | 删除交易 |
| GET | /api/v1/investments/holdings | 投资持仓 |
| GET | /api/v1/investments/holdings/{symbol}/history | 持仓历史 |
| GET | /api/v1/investments/holdings/summary | 持仓汇总 |

### Phase 3 新增端点

| 方法 | 路径 | 请求 | 响应 |
|------|------|------|------|
| GET | /api/v1/investments/portfolio | — | `{total_value, holdings: [{symbol, name, quantity, current_price, market_value, allocation_pct}]}` |
| GET | /api/v1/investments/pnl-analysis | — | `{total_cost, total_value, total_pnl, total_pnl_pct, holdings: [{symbol, name, cost_basis, current_value, pnl, pnl_pct}]}` |

---

## 执行顺序和依赖

```
并行启动:
  Backend:  A1(sync升级) → A2(portfolio端点) → A3(pnl端点)
  Frontend: B1(交易录入页面，不依赖后端)
  Testing:  C1(单元测试，mock数据)

Backend 完成后:
  Frontend: B2(api_client新方法) → B3(投资组合页面) → B4(快捷链接)
  Testing:  C2(集成测试)

Frontend 完成后:
  Testing:  C3(E2E测试)
```

## 验收标准

- `uv run pytest -v` 全部通过
- 侧边栏显示 6 个页面（资产总览、账户管理、预算管理、日常记账、投资组合、交易录入）
- 投资组合页面显示 P&L 数据
- 交易录入页面能创建买入/卖出交易
- claude-mem 中有完整的 Phase 3 各终端进展记录

---

## 多实例分工
- Backend 实例: 只修改 `app/` 目录
- Frontend 实例: 只修改 `streamlit_app/` 目录
- Testing 实例: 只修改 `tests/` 目录
- 共享模型 `app/models/core.py` 由 Backend 实例独占修改

## 快速开始
```bash
bash scripts/setup.sh                          # 首次搭建：安装依赖 + 启动 PostgreSQL
bash scripts/dev.sh                            # 启动后端 + 前端（开发模式）
bash scripts/dev.sh backend                    # 只启动后端
bash scripts/dev.sh frontend                   # 只启动前端
```

## 常用命令
```bash
uv run uvicorn app.main:app --reload          # 启动后端
uv run streamlit run streamlit_app/Home.py    # 启动前端
uv run pytest -v                               # 运行测试
```

## 插件使用约定
- 新功能开始前: /plan
- 后端开发: /tdd → /python-review
- 前端完成后: /e2e
- 提交前: /security-review
- 会话结束: 保存进展到 claude-mem (project=folio)
