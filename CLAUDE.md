# Equilibra - 个人财务管理系统

## 技术栈
- Backend: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- Frontend: Streamlit (multi-page)
- Package Manager: uv
- Python 3.12+

## 项目结构
```
app/                    # 后端
├── models/core.py      # 8张核心表 (Account, Holding, Budget, Expense...)
├── api/core_routes.py  # 20+ API 端点 (/api/v1/core/*)
├── services/           # 业务逻辑
└── database.py         # 数据库连接

streamlit_app/          # 前端
├── api_client.py       # HTTP 客户端
└── pages/              # 资产总览、账户管理、预算管理、支出录入

tests/                  # 测试 (54 tests passing)
```

## 关键设计
- Account: balance(现金) + holdings_value(持仓市值)
- Holding: is_liquid 标志区分高流动性资产(余额宝) vs 普通投资(股票)
- available_cash = balance + 高流动性持仓
- 支出从 cash 账户扣减，同时更新 budget spent

## 开发状态
- Phase 1-2: ✅ 完成 (核心模型 + API + 前端页面)
- Phase 3: 🔲 投资组合增强 (盈亏分析、市值同步)
- Phase 4: 🔲 高级功能 (报表、数据导入导出)

## 多实例分工
- Backend 实例: 只修改 app/ 目录
- Frontend 实例: 只修改 streamlit_app/ 目录
- Testing 实例: 只修改 tests/ 目录
- 共享模型 app/models/core.py 由 Backend 实例独占修改

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
- 会话结束: 保存进展到 claude-mem (project=equilibra)
