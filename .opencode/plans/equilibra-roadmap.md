# Equilibra 产品重构计划

**项目目标**：构建清晰、易用的个人财务管理系统  
**核心理念**：预算作为分类追踪，支出实时扣减现金余额  
**当前状态**：Phase 1 核心基础已完成 ✅ + 投资账户架构改进 ✅ + 高流动性资产支持 ✅
**最后更新**：2024-02-08

---

## 📊 项目概览

### 产品定位
- **目标用户**：需要管理个人/家庭财务的用户
- **核心场景**：日常开销追踪、预算管理、投资记录
- **设计原则**：简单直观、数据实时、预算驱动

### 架构分层
```
投资层（增值导向）
├── 股票、基金、债券等
├── 买卖交易记录
└── 市值同步、盈亏分析

现金层（支付导向）
├── 银行活期、货币基金
├── 支出发生时立即扣减
└── 余额实时可见

预算层（分类追踪）
├── 周期性预算（月度/季度日常）
├── 项目型预算（婚礼、旅游等大额）
├── 记录支出归属
└── 超支预警、进度追踪
```

---

## ✅ 已完成 Phase 1：核心基础

### 1.1 数据库表结构

**核心表（8个）**

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `accounts` | 账户管理 | id, name, type(cash/investment), balance, **holdings_value**, currency |
| `holdings` | 投资持仓 | account_id, symbol, quantity, avg_cost, current_price, **is_liquid** |
| `core_investment_transactions` | 投资交易 | account_id, type(buy/sell), quantity, price, fees |
| `budgets` | 预算管理 | name, type(periodic/project), amount, spent, remaining, period |
| `expenses` | 支出记录 | account_id, budget_id, amount, category, is_shared, merchant, tags |
| `expense_categories` | 支出分类 | category, subcategory（预定义9大分类） |

**关键设计决策：投资账户架构** ⭐ **2024-02-08 更新**

问题：如何区分富途证券这类账户的「股票持仓」和「现金部分」？

方案对比：
| 方案 | 描述 | 决策 |
|------|------|------|
| A. 保持现状 | InvestmentAccount.balance = 可用现金 | ✅ 采用 + 改进 |
| B. 拆分账户 | 券商现金独立为CashAccount | 增加转账复杂度 |
| C. 虚拟子账户 | 增加子账户概念 | 过度设计 |

**最终方案（改进版A + 高流动性资产）：**
```python
class Account:
    account_type: str  # cash / investment
    
    # cash账户：实际余额
    # investment账户：可用现金（未投资部分，不含高流动性资产）
    balance: Decimal
    
    # investment账户特有：持仓市值（实时计算或缓存）
    holdings_value: Optional[Decimal]
    
    @property
    def total_value(self) -> Decimal:
        """总资产 = balance + 所有持仓市值"""
        if account_type == "investment":
            return balance + sum(h.current_value for h in holdings if h.is_active)
        return balance
    
    @property
    def available_cash(self) -> Decimal:
        """可用现金 = balance + 高流动性持仓（余额宝等）"""
        if account_type == "investment":
            liquid = sum(h.current_value for h in holdings if h.is_active and h.is_liquid)
            return balance + liquid
        return balance
    
    @property
    def investment_value(self) -> Decimal:
        """投资市值 = 非流动性持仓（股票、普通基金等）"""
        if account_type == "investment":
            return sum(h.current_value for h in holdings 
                      if h.is_active and not h.is_liquid)
        return Decimal("0")

class Holding:
    is_liquid: bool  # True: 高流动性（余额宝等T+0），False: 普通投资
```

**支付宝账户示例：**
```
支付宝
├── 余额: ¥1,000（可消费/转账）
├── 余额宝: ¥2,000（T+0货币基金，随时可取）
├── 某基金: ¥2,000.84（1000.42份，成本¥1,500.63，盈亏+¥500.21）
├── 可用现金: ¥3,000（余额+余额宝，可立即使用）
├── 持仓市值: ¥2,000.84（基金，长期投资）
└── 总资产: ¥5,000.84
```

**录入流程：**
1. 创建账户：`initial_balance = 1000`（只录余额）
2. 添加余额宝持仓：`is_liquid = True`
3. 添加基金持仓：`is_liquid = False`

**买卖流程：**
- **买入基金**：balance -= ¥1,000 → holdings 增加基金（is_liquid=False）
- **余额宝转入**：balance -= ¥2,000 → holdings 增加余额宝（is_liquid=True）
- **卖出**：对应holding减少 → balance += 卖出金额

**已实现的计算功能：**
- `Account.calculate_holdings_value()` - 计算非流动性持仓市值
- `Account.total_value` - 总资产（所有资产）
- `Account.available_cash` - 可用现金（含高流动性资产）
- `Account.investment_value` - 投资市值（非流动性资产）
- `Holding.is_liquid` - 流动性标识
- API返回：`balance`, `holdings_value`, `total_value`, `available_cash`
| `core_cash_flows` | 现金流水 | account_id, type, amount, balance_after |
| `market_sync_logs` | 市值同步 | total_value, holdings_count, status |

**预定义支出分类（9大类）**
- 餐饮：早餐、午餐、晚餐、咖啡奶茶、聚餐、食材
- 交通：公共交通、打车、加油、停车、保养维修
- 购物：服饰、数码、日用、美妆、书籍
- 居住：房租、水电煤、物业费、家居、维修
- 娱乐：电影、游戏、运动、旅游、爱好
- 医疗：药品、诊疗、体检、保险
- 教育：书籍课程、培训、考试
- 人情：礼物、红包、请客、捐款
- 其他

### 1.2 SQLAlchemy模型

**模型文件**：`app/models/core.py`

**7个模型类**
- `Account` - 账户
- `Holding` - 投资持仓
- `CoreInvestmentTransaction` - 投资交易
- `Budget` - 预算
- `Expense` - 支出
- `ExpenseCategory` - 支出分类
- `CoreCashFlow` - 现金流水
- `MarketSyncLog` - 市值同步记录

**技术特点**
- SQLAlchemy 2.0 语法（Mapped, mapped_column）
- 完整的关系映射（relationship, ForeignKey）
- 类型注解完整

### 1.3 API接口（12个端点）

**基础路径**：`/api/v1/core`

#### 账户管理（5个）
```
POST   /accounts              创建账户
GET    /accounts              账户列表
GET    /accounts/{id}         账户详情
PUT    /accounts/{id}         更新账户
DELETE /accounts/{id}         删除账户
```

#### 预算管理（3个）
```
POST   /budgets               创建预算
GET    /budgets               预算列表
GET    /budgets/{id}          预算详情
POST   /budgets/{id}/complete 完成/结算预算
```

#### 支出管理（2个）
```
POST   /expenses              录入支出 ⭐核心
GET    /expenses              支出列表（支持筛选）
```

#### 辅助功能（2个）
```
GET    /categories            支出分类列表
GET    /dashboard             仪表盘数据
```

### 1.4 核心逻辑实现

**支出录入流程**
```python
1. 验证现金账户存在且余额充足
2. 如果有预算，验证预算存在且额度充足
3. 扣减现金账户余额（立即生效）
4. 更新预算已支出额度
5. 创建支出记录
6. 创建现金流水记录
```

**关键约束**
- 支出金额必须大于0
- 现金账户余额不能为负
- 预算额度不能为负（超支时阻止或警告）

### 1.5 测试验证结果

**已创建的测试数据**
```json
{
  "accounts": [
    {
      "id": 1,
      "name": "招商银行储蓄卡",
      "type": "cash",
      "balance": "49800.00",
      "currency": "CNY"
    },
    {
      "id": 2,
      "name": "富途证券",
      "type": "investment",
      "balance": "0.00",
      "currency": "HKD"
    }
  ],
  "budgets": [
    {
      "id": 1,
      "name": "3月生活费",
      "type": "periodic",
      "amount": "10000.00",
      "spent": "200.00",
      "remaining": "9800.00"
    }
  ],
  "expenses": [
    {
      "id": 1,
      "amount": "200.00",
      "category": "餐饮",
      "subcategory": "午餐",
      "merchant": "麦当劳"
    }
  ]
}
```

**验证通过的功能**
- ✅ 创建现金账户（带初始余额）
- ✅ 创建投资账户
- ✅ 创建预算
- ✅ 录入支出立即扣减现金余额
- ✅ 预算额度实时更新
- ✅ 仪表盘数据聚合正确

---

## 🚧 Phase 2：前端页面重构（进行中）

### 2.1 技术选型
- **框架**：Streamlit（沿用现有）
- **布局**：侧边栏导航
- **样式**：Streamlit原生组件 + 自定义CSS
- **响应式**：桌面端优先，移动端可用

### 2.2 页面规划（5个页面）

#### 页面1：资产总览（Dashboard）
**定位**：一站式概览，快速了解整体财务状况

**功能模块**
- 关键指标卡片
  - 净资产（现金 + 投资市值）
  - 现金余额
  - 投资市值
  - 本月预算执行率
- 预算执行概况
  - 各预算进度条
  - 超支预警标记
- 资产分布图表
  - 按平台分布（饼图）
  - 按类型分布（饼图）
- 快速入口按钮
  - [录入支出]
  - [录入投资交易]
  - [查看预算]
  - [管理账户]

**设计要点**
- 页面加载时自动刷新数据
- 关键指标使用大字体突出
- 预算进度条使用颜色区分状态（正常/警告/超支）
- 图表使用Plotly交互式

#### 页面2：账户管理（Accounts）
**定位**：管理"容器"——钱放在哪里

**现金账户区域**
- 账户列表卡片
  - 账户名称、机构
  - 实时余额
  - 本月支出统计
- 操作按钮
  - [查看流水]
  - [编辑]
  - [删除]
- 新增账户按钮

**投资账户区域**
- 账户列表卡片
  - 账户名称、机构
  - 持仓数量
  - 市值（需同步）
- 操作按钮
  - [查看持仓]
  - [录入交易]
  - [同步市值]
  - [编辑]
- 新增账户按钮

**设计要点**
- 现金和投资账户分区展示
- 点击账户展开详情
- 支持账户间转账操作

#### 页面3：预算管理（Budget）⭐ 核心页面
**定位**：管理计划——钱打算怎么花

**预算列表**
- 进行中的预算卡片
  - 预算名称、类型图标
  - 进度条（金额 + 百分比）
  - 剩余金额、剩余天数
  - 状态标签（正常/即将超支/已超支）
- 操作按钮
  - [查看详情]
  - [调整预算]
  - [提前结算]

**预算详情（展开/弹窗）**
- 预算概览
  - 预算总额、已支出、剩余
  - 周期信息（开始-结束日期）
- 支出明细表
  - 日期、金额、分类、商家
  - 支持按分类筛选
- 分类统计图表
  - 饼图展示各类别占比
- 操作区域
  - [调整预算金额]
  - [结束预算/结算]

**新建预算**
- 表单字段
  - 名称
  - 类型选择（周期性/项目型）
  - 金额
  - 周期（日期选择器）
  - 关联账户（多选）

**设计要点**
- 进度条直观展示预算使用情况
- 超支时明显标记
- 支持预算调整和提前结算

#### 页面4：支出录入（Expense Entry）
**定位**：快速记录每一笔支出

**录入表单**
- 必填字段
  - 现金账户（下拉选择）
  - 预算类别（下拉选择）
  - 金额（数字输入）
  - 日期（日期选择器，默认今天）
  - 共同/个人（单选按钮）
- 分类字段
  - 一级分类（下拉，9大类）
  - 二级分类（动态下拉）
- 可选字段
  - 商家/地点（文本输入）
  - 支付方式（下拉）
  - 参与人（多选）
  - 标签（文本输入，支持多个）
  - 备注（文本域）
- 提交按钮

**交互优化**
- 连续录入模式：提交后保留部分字段（预算、账户）
- 快速录入：最近使用的分类置顶
- 实时计算：显示录入后账户余额和预算剩余

**设计要点**
- 表单分组（必填/分类/可选）
- 字段过多时使用折叠面板
- 提交成功提示，支持继续录入

#### 页面5：投资组合（Portfolio）
**定位**：投资分析，盈亏追踪

**持仓概览**
- 关键指标
  - 总投资市值
  - 总成本
  - 总盈亏（金额 + 百分比）
- 持仓列表
  - 代码、名称、市场
  - 数量、成本价、当前价
  - 市值、盈亏
  - 按盈亏排序

**收益分析**
- 累计收益曲线（时间轴）
- 月度收益率统计
- 资产分布图表
  - 按市场分布
  - 按类型分布

**市值同步**
- 上次同步时间
- [立即同步] 按钮
- 同步状态显示

**设计要点**
- 盈亏使用红绿色区分
- 支持按不同维度排序
- 图表展示趋势

### 2.3 API Client更新

**新增方法**（添加到 `streamlit_app/api_client.py`）
```python
# 账户管理
create_account(name, account_type, ...) -> Account
list_accounts(account_type=None) -> List[Account]
get_account(account_id) -> Account
update_account(account_id, ...) -> Account
delete_account(account_id)

# 预算管理
create_budget(name, budget_type, ...) -> Budget
list_budgets(budget_type=None) -> List[Budget]
get_budget(budget_id) -> Budget
complete_budget(budget_id)

# 支出管理
create_expense(account_id, budget_id, amount, ...) -> Expense
list_expenses(account_id=None, budget_id=None, ...) -> List[Expense]

# 辅助
get_categories() -> List[Category]
get_dashboard() -> DashboardData
```

### 2.4 开发顺序建议

**推荐顺序**（依赖关系）
```
1. 账户管理页面（基础）
   └── 依赖：账户API ✅已完成
   
2. 支出录入页面（核心）
   └── 依赖：支出API ✅已完成
   └── 依赖：账户列表（从页面1复用）
   └── 依赖：分类API ✅已完成
   
3. 预算管理页面
   └── 依赖：预算API ✅已完成
   └── 依赖：支出列表（复用组件）
   
4. 资产总览页面
   └── 依赖：仪表盘API ✅已完成
   └── 依赖：其他页面的组件
   
5. 投资组合页面
   └── 依赖：投资相关API（需补充）
```

### 2.5 待讨论事项（执行时确认）

**页面布局细节**
- 侧边栏导航的图标和排序
- 主题配色方案
- 是否支持深色模式

**交互细节**
- 支出录入时是否允许不选预算？
- 预算超支时是阻止还是警告？
- 删除账户时的确认流程
- 表单验证的错误提示方式

**功能优先级**
- 是否需要在页面2中实现账户间转账？
- 是否需要在页面4中支持批量导入支出？
- 图表的详细程度

---

## 📋 Phase 3：投资组合功能

### 3.1 投资持仓管理
- 持仓列表展示（代码、数量、成本、市值、盈亏）
- 支持按市场、类型筛选
- 盈亏排序功能

### 3.2 市值同步机制
- 手动同步按钮
- 自动同步配置（频率、时间）
- 同步历史记录
- 同步失败处理

### 3.3 盈亏分析
- 累计收益曲线
- 月度/年度收益率统计
- 与大盘对比（沪深300、标普500）
- 资产分布分析

### 3.4 待讨论事项
- 市值同步的数据源选择（Yahoo Finance、AkShare等）
- 同步频率（实时、收盘后、每日一次）
- 历史数据保留策略

---

## 📋 Phase 4：增强功能

### 4.1 数据导入/导出
- 支出数据导出（CSV、Excel）
- 批量导入支出（CSV模板）
- 数据备份与恢复

### 4.2 报表统计
- 月度消费报告
- 年度财务总结
- 预算执行分析
- 自定义时间范围报表

### 4.3 系统优化
- 性能优化（大数据量处理）
- 缓存策略
- 移动端适配
- 测试覆盖提升

---

## 🔧 技术参考

### 目录结构
```
Equilibra/
├── app/
│   ├── models/
│   │   ├── core.py              # Phase 1 模型 ✅ + holdings_value + is_liquid
│   │   └── ...
│   ├── api/
│   │   ├── core_routes.py       # Phase 1 API ✅ + total_value/available_cash计算
│   │   └── ...
│   └── main.py
├── streamlit_app/
│   ├── api_client.py            # 需要更新
│   ├── Home.py                  # 资产总览
│   └── pages/
│       ├── 1_📊_资产总览.py      # Phase 2
│       ├── 2_💰_账户管理.py      # Phase 2
│       ├── 3_📅_预算管理.py      # Phase 2
│       ├── 4_📝_支出录入.py      # Phase 2
│       ├── 5_📈_投资组合.py      # Phase 3
│       └── ...
├── tests/                       # ✅ 新增测试目录
│   ├── test_models.py           # 模型单元测试
│   └── test_api.py              # API集成测试
└── .opencode/plans/
    └── equilibra-roadmap.md     # 本文件
```

### 测试
```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_models.py -v
uv run pytest tests/test_api.py -v
```

**已实现的测试（2024-02-08 更新）：**
- `test_models.py` - Account模型计算功能测试
  - 现金账户总资产计算
  - 投资账户可用现金+持仓市值计算
  - 支付宝场景测试（余额+余额宝+基金）
  - 高流动性资产（is_liquid=True）识别
  - 持仓市值实时计算（区分流动性/非流动性）
  - total_value / available_cash / investment_value 计算
  - 缓存值更新机制
- `test_api.py` - API端点测试
  - 创建现金账户
  - 创建投资账户
  - 获取包含持仓的账户详情
  - 混合账户列表展示
  - 仪表盘数据聚合

### 启动命令
```bash
# 后端API
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
uv run streamlit run streamlit_app/Home.py

# API文档
http://localhost:8000/docs
```

### 当前测试数据
```json
{
  "cash_account": {
    "id": 1,
    "name": "招商银行储蓄卡",
    "balance": 49800.00
  },
  "investment_account": {
    "id": 2,
    "name": "富途证券"
  },
  "budget": {
    "id": 1,
    "name": "3月生活费",
    "remaining": 9800.00
  }
}
```

---

## ✅ 下一步行动

**Phase 2 准备就绪，等待执行**

当前需要决策：
1. 是否确认Phase 2的开发顺序（账户→支出→预算→总览→投资）？
2. 是否先从"账户管理页面"开始？
3. 是否有特定的设计偏好（颜色、布局等）？

**建议**
- 先完成Phase 2的前4个页面（账户、支出、预算、总览）
- 形成一个可用的MVP（最小可用产品）
- 然后再做投资组合功能

---

## 📝 变更记录

### 2024-02-08
- 创建计划文档
- Phase 1 完成：数据库、模型、API、测试验证
- 设计 Phase 2 前端页面规划
- 记录测试数据和API端点

---

*文档由 OpenCode Agent 维护*  
*最后更新：2024-02-08*
