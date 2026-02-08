-- ============================================
-- Equilibra 数据库初始化脚本
-- Phase 1: 核心基础表
-- ============================================

-- Enable pgvector extension (optional)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- 1. 账户表 (Accounts)
-- 区分投资账户和现金账户
-- ============================================
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    
    -- 基本信息
    name VARCHAR(100) NOT NULL,                    -- 账户名称
    account_type VARCHAR(20) NOT NULL,             -- 类型: cash/investment
    institution VARCHAR(100),                      -- 机构名称
    account_number VARCHAR(100),                   -- 账号
    
    -- 余额信息
    balance DECIMAL(20, 4) DEFAULT 0,              -- 当前余额（现金账户实时，投资账户为成本）
    currency VARCHAR(10) DEFAULT 'CNY',            -- 币种
    
    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_accounts_type ON accounts(account_type);
CREATE INDEX idx_accounts_institution ON accounts(institution);

-- ============================================
-- 2. 投资持仓表 (Holdings)
-- 记录投资账户的持仓明细
-- ============================================
CREATE TABLE IF NOT EXISTS holdings (
    id SERIAL PRIMARY KEY,
    
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- 资产信息
    symbol VARCHAR(50) NOT NULL,                   -- 代码
    name VARCHAR(100),                             -- 名称
    asset_type VARCHAR(20) NOT NULL,               -- 类型: stock/fund/bond/crypto
    market VARCHAR(20),                            -- 市场: A股/港股/美股
    
    -- 持仓信息
    quantity DECIMAL(20, 8) NOT NULL DEFAULT 0,    -- 数量
    avg_cost DECIMAL(20, 8) NOT NULL DEFAULT 0,    -- 平均成本
    total_cost DECIMAL(20, 4) NOT NULL DEFAULT 0,  -- 总成本
    
    -- 市值信息（需同步）
    current_price DECIMAL(20, 8),                  -- 当前价格
    current_value DECIMAL(20, 4),                  -- 当前市值
    last_sync_at TIMESTAMP,                        -- 上次同步时间
    
    currency VARCHAR(10) DEFAULT 'CNY',
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(account_id, symbol, asset_type, market)
);

CREATE INDEX idx_holdings_account ON holdings(account_id);
CREATE INDEX idx_holdings_symbol ON holdings(symbol);
CREATE INDEX idx_holdings_asset_type ON holdings(asset_type);

-- ============================================
-- 3. 投资交易记录表 (Investment Transactions)
-- 记录买入、卖出、分红等投资交易
-- ============================================
CREATE TABLE IF NOT EXISTS investment_transactions (
    id SERIAL PRIMARY KEY,
    
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    holding_id INTEGER REFERENCES holdings(id) ON DELETE SET NULL,
    
    -- 交易信息
    transaction_type VARCHAR(20) NOT NULL,         -- buy/sell/dividend/interest
    symbol VARCHAR(50) NOT NULL,                   -- 代码
    name VARCHAR(100),                             -- 名称快照
    
    quantity DECIMAL(20, 8) NOT NULL DEFAULT 0,    -- 数量
    price DECIMAL(20, 8) NOT NULL DEFAULT 0,       -- 价格
    fees DECIMAL(20, 4) DEFAULT 0,                 -- 手续费
    amount DECIMAL(20, 4) NOT NULL DEFAULT 0,      -- 总金额
    
    trade_date TIMESTAMP NOT NULL,
    currency VARCHAR(10) DEFAULT 'CNY',
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_inv_tx_account ON investment_transactions(account_id);
CREATE INDEX idx_inv_tx_date ON investment_transactions(trade_date);
CREATE INDEX idx_inv_tx_type ON investment_transactions(transaction_type);

-- ============================================
-- 4. 预算表 (Budgets)
-- 管理周期性或项目型预算
-- ============================================
CREATE TABLE IF NOT EXISTS budgets (
    id SERIAL PRIMARY KEY,
    
    name VARCHAR(100) NOT NULL,                    -- 预算名称
    budget_type VARCHAR(20) NOT NULL,              -- 类型: periodic/project
    
    -- 金额信息
    amount DECIMAL(20, 4) NOT NULL,                -- 预算总额
    spent DECIMAL(20, 4) DEFAULT 0,                -- 已支出
    remaining DECIMAL(20, 4) NOT NULL,             -- 剩余额度
    
    -- 周期信息
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',           -- active/completed/cancelled
    
    -- 关联账户（哪些现金账户的钱可用于此预算）
    associated_account_ids JSONB,                  -- [1, 2, 3]
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_budgets_type ON budgets(budget_type);
CREATE INDEX idx_budgets_status ON budgets(status);
CREATE INDEX idx_budgets_period ON budgets(period_start, period_end);

-- ============================================
-- 5. 支出表 (Expenses)
-- 记录每一笔支出（核心表）
-- ============================================
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    
    -- 关联信息
    account_id INTEGER NOT NULL REFERENCES accounts(id),  -- 现金账户（钱从这里出）
    budget_id INTEGER REFERENCES budgets(id),             -- 所属预算
    
    -- 基本信息
    amount DECIMAL(20, 4) NOT NULL,                -- 金额
    expense_date DATE NOT NULL,                    -- 日期
    
    -- 分类信息
    category VARCHAR(50) NOT NULL,                 -- 一级分类
    subcategory VARCHAR(50),                       -- 二级分类
    
    -- 属性标识
    is_shared BOOLEAN DEFAULT FALSE,               -- 共同开销(true) or 个人(false)
    
    -- 可选详细信息
    merchant VARCHAR(100),                         -- 商家/地点
    payment_method VARCHAR(20),                    -- 支付方式
    participants JSONB,                            -- 参与人 ["我", "伴侣"]
    tags JSONB,                                    -- 标签 ["出差", "约会"]
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_expenses_account ON expenses(account_id);
CREATE INDEX idx_expenses_budget ON expenses(budget_id);
CREATE INDEX idx_expenses_date ON expenses(expense_date);
CREATE INDEX idx_expenses_category ON expenses(category);

-- ============================================
-- 6. 支出分类表 (Expense Categories)
-- 预定义分类体系
-- ============================================
CREATE TABLE IF NOT EXISTS expense_categories (
    id SERIAL PRIMARY KEY,
    
    category VARCHAR(50) NOT NULL,                 -- 一级分类
    subcategory VARCHAR(50) NOT NULL,              -- 二级分类
    
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    
    UNIQUE(category, subcategory)
);

-- 插入默认分类数据
INSERT INTO expense_categories (category, subcategory, sort_order) VALUES
-- 餐饮
('餐饮', '早餐', 1),
('餐饮', '午餐', 2),
('餐饮', '晚餐', 3),
('餐饮', '咖啡奶茶', 4),
('餐饮', '聚餐', 5),
('餐饮', '食材', 6),
('餐饮', '其他', 7),
-- 交通
('交通', '公共交通', 1),
('交通', '打车', 2),
('交通', '加油', 3),
('交通', '停车', 4),
('交通', '保养维修', 5),
('交通', '其他', 6),
-- 购物
('购物', '服饰', 1),
('购物', '数码', 2),
('购物', '日用', 3),
('购物', '美妆', 4),
('购物', '书籍', 5),
('购物', '其他', 6),
-- 居住
('居住', '房租', 1),
('居住', '水电煤', 2),
('居住', '物业费', 3),
('居住', '家居', 4),
('居住', '维修', 5),
('居住', '其他', 6),
-- 娱乐
('娱乐', '电影', 1),
('娱乐', '游戏', 2),
('娱乐', '运动', 3),
('娱乐', '旅游', 4),
('娱乐', '爱好', 5),
('娱乐', '其他', 6),
-- 医疗
('医疗', '药品', 1),
('医疗', '诊疗', 2),
('医疗', '体检', 3),
('医疗', '保险', 4),
('医疗', '其他', 5),
-- 教育
('教育', '书籍课程', 1),
('教育', '培训', 2),
('教育', '考试', 3),
('教育', '其他', 4),
-- 人情
('人情', '礼物', 1),
('人情', '红包', 2),
('人情', '请客', 3),
('人情', '捐款', 4),
('人情', '其他', 5),
-- 其他
('其他', '其他', 1)
ON CONFLICT DO NOTHING;

-- ============================================
-- 7. 现金流水表 (Cash Flows)
-- 记录现金账户的每一笔变动
-- ============================================
CREATE TABLE IF NOT EXISTS cash_flows (
    id SERIAL PRIMARY KEY,
    
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    
    flow_type VARCHAR(50) NOT NULL,                -- income/expense/transfer
    amount DECIMAL(20, 4) NOT NULL,                -- 变动金额（正数流入，负数流出）
    balance_after DECIMAL(20, 4) NOT NULL,         -- 变动后余额
    
    -- 关联
    expense_id INTEGER REFERENCES expenses(id),
    investment_transaction_id INTEGER REFERENCES investment_transactions(id),
    
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cash_flows_account ON cash_flows(account_id);
CREATE INDEX idx_cash_flows_type ON cash_flows(flow_type);
CREATE INDEX idx_cash_flows_date ON cash_flows(created_at);

-- ============================================
-- 8. 市值同步记录表
-- 记录投资市值同步历史
-- ============================================
CREATE TABLE IF NOT EXISTS market_sync_logs (
    id SERIAL PRIMARY KEY,
    
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_value DECIMAL(20, 4),                    -- 总市值
    holdings_count INTEGER,                        -- 持仓数量
    status VARCHAR(20) DEFAULT 'success',          -- success/failed
    error_message TEXT,
    
    details JSONB                                  -- 详细数据
);

CREATE INDEX idx_sync_logs_date ON market_sync_logs(synced_at);

-- ============================================
-- 9. 保留旧表（兼容性）
-- ============================================
-- 旧资产表
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    account_type VARCHAR(50) NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    balance DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'CNY',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- 旧股票持仓表
CREATE TABLE IF NOT EXISTS stock_positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    quantity INTEGER NOT NULL,
    cost_price DECIMAL(15, 4) NOT NULL,
    account_name VARCHAR(100) DEFAULT '默认账户',
    currency VARCHAR(10) DEFAULT 'CNY',
    notes TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 旧交易流水表
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    transaction_type VARCHAR(50) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'CNY',
    from_account VARCHAR(100),
    to_account VARCHAR(100),
    category VARCHAR(50),
    is_wedding_expense BOOLEAN DEFAULT FALSE,
    description TEXT,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- ============================================
-- 10. 其他辅助表
-- ============================================
-- 汇率表
CREATE TABLE IF NOT EXISTS exchange_rates (
    id SERIAL PRIMARY KEY,
    from_currency VARCHAR(10) NOT NULL,
    to_currency VARCHAR(10) NOT NULL,
    rate DECIMAL(20, 10) NOT NULL,
    source VARCHAR(50),
    recorded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_currency, to_currency, recorded_at)
);

-- 行情缓存表
CREATE TABLE IF NOT EXISTS stock_quote_cache (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    current_price DECIMAL(15, 4),
    change DECIMAL(15, 4),
    change_percent DECIMAL(10, 4),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, market)
);
