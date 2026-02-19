# Equilibra 产品路线图

**项目目标**：构建清晰、易用的个人财务管理系统
**核心理念**：预算作为分类追踪，支出实时扣减现金余额
**最后更新**：2025-02-13

---

## 产品定位

- **目标用户**：需要管理个人/家庭财务的用户
- **核心场景**：日常开销追踪、预算管理、投资记录、负债管理
- **设计原则**：简单直观、数据实时、预算驱动

## 信息架构

```
Home（首页）
├── 1_📊 资产总览    — 数据看板 & 图表分析（只读）
├── 2_💰 账户管理    — 资产账户 + 负债账户 CRUD，转账，持仓，还款
├── 3_📅 预算管理    — 预算全生命周期管理（创建/编辑/取消/删除/结算）
└── 4_📝 日常记账    — 日常消费记录，关联账户和预算
```

## 技术栈

- Backend: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- Frontend: Streamlit (multi-page) + Plotly
- Package Manager: uv
- Python 3.12+

---

## ✅ Phase 1：核心基础

### 数据模型（11 个表）

| 表名 | 用途 |
|------|------|
| accounts | 账户（cash/investment） |
| holdings | 投资持仓（is_liquid 区分流动性） |
| core_investment_transactions | 投资交易 |
| budgets | 预算（periodic/project） |
| expenses | 支出记录 |
| expense_categories | 预定义 9 大分类 |
| core_cash_flows | 现金流水 |
| core_transfers | 账户间转账 |
| market_sync_logs | 市值同步记录 |
| liabilities | 负债账户 |
| liability_payments | 还款记录 |

### 关键设计

- Account: balance(现金) + holdings_value(持仓市值)
- Holding: is_liquid 标志区分高流动性资产(余额宝) vs 普通投资(股票)
- available_cash = balance + 高流动性持仓
- 支出从账户 balance 扣减，同时更新 budget spent
- 净资产 = 总资产 - 总负债

---

## ✅ Phase 2：前后端完整开发

### 2.1 后端 API（30+ 端点）

**账户管理** (5): CRUD + 列表筛选
**持仓管理** (5): CRUD + 市值同步
**转账** (2): 创建 + 列表
**预算管理** (7): CRUD + 完成/取消 + 可用资金
**支出管理** (3): 创建 + 列表 + 删除（回滚余额）
**负债管理** (6): CRUD + 还款记录
**Dashboard** (1): 增强版（net_worth, total_liability, monthly_expense_total）
**辅助** (1): 分类列表

### 2.2 前端页面（4 个核心页面）

1. **资产总览** — 4 指标卡片 + Plotly 图表（资产分布饼图、账户余额柱状图、月度支出趋势、支出分类饼图）+ 负债概览 + 预算执行
2. **账户管理** — 现金/投资/负债三区域 + 侧边栏操作（创建账户、转账、添加持仓、添加负债、同步市值）+ 还款
3. **预算管理** — 创建/编辑/取消/删除/结算 + Tab 分组（活跃/已完成/已取消）+ 使用率排名 + 记一笔跳转
4. **日常记账** — 表单（账户、金额、分类、日期、商户、支付方式、预算关联）+ 近期记录 + 删除支出

### 2.3 测试（76+ 测试函数）

- test_models.py — 模型计算
- test_api.py — API 端点
- test_holdings.py — 持仓功能
- test_transfers.py — 转账功能
- test_expense_extended.py — 扩展支出
- test_market_sync.py — 市值同步
- test_e2e.py — E2E 测试

---

## 🔲 Phase 3：投资组合增强

功能来源：_archive/ 目录中的旧页面代码可作参考

### 3.1 投资持仓管理页面
- 持仓列表（代码、数量、成本、市值、盈亏）
- 按市场、类型筛选
- 盈亏排序

### 3.2 交易录入页面
- 买入/卖出/分红/利息
- 多资产类型（股票/基金/债券/加密货币）
- 多市场支持

### 3.3 市值同步机制
- 接入真实数据源（AkShare 已在依赖中）
- 自动同步配置
- 同步历史记录

### 3.4 盈亏分析
- 累计收益曲线
- 月度/年度收益率
- 资产分布分析

---

## 🔲 Phase 4：高级功能

### 4.1 AI 分析
- LangGraph 智能分析（依赖已就绪）
- 投资建议、风险评估

### 4.2 市场新闻
- 新闻聚合 + pgvector 语义搜索

### 4.3 数据导入/导出
- CSV/Excel 导出
- 批量导入支出

### 4.4 报表统计
- 月度消费报告
- 年度财务总结

---

## 变更记录

- 2025-02-13: 合并 product-improvement.md，统一路线图；旧页面移至 _archive
- 2025-02-08: Phase 2 全部完成（含负债管理、预算生命周期、增强 Dashboard）
- 2025-02-08: Phase 1 完成（核心模型 + API + 测试）
