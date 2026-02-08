"""投资相关数据模型 - 交易记录、基金产品、目标配置等"""

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.database import Base


class AssetType(str, enum.Enum):
    """资产类型"""
    STOCK = "stock"           # 股票
    FUND = "fund"             # 基金
    BOND = "bond"             # 债券
    BANK_PRODUCT = "bank_product"  # 银行理财
    CRYPTO = "crypto"         # 加密货币


class TransactionType(str, enum.Enum):
    """交易类型"""
    BUY = "buy"               # 买入
    SELL = "sell"             # 卖出
    DIVIDEND = "dividend"     # 分红
    SPLIT = "split"           # 拆股
    INTEREST = "interest"     # 利息
    TRANSFER_IN = "transfer_in"    # 转入
    TRANSFER_OUT = "transfer_out"  # 转出


class InvestmentTransaction(Base):
    """投资交易记录表 - 记录每笔买卖交易"""
    __tablename__ = "investment_transactions"

    id = Column(Integer, primary_key=True, index=True)

    # 资产信息
    asset_type = Column(String(20), nullable=False, index=True)  # stock/fund/bond/bank_product/crypto
    symbol = Column(String(50), nullable=False, index=True)      # 代码: 600000, 000001, BTC
    name = Column(String(100), nullable=True)                    # 名称
    market = Column(String(20), nullable=True, index=True)       # 市场: A股/港股/美股/OKX/fund

    # 交易信息
    transaction_type = Column(String(20), nullable=False, index=True)  # buy/sell/dividend/split/interest
    quantity = Column(Numeric(20, 8), nullable=False)            # 数量（支持小数，如加密货币）
    price = Column(Numeric(20, 8), nullable=False)               # 单价
    amount = Column(Numeric(20, 4), nullable=False)              # 总金额 = quantity * price
    fees = Column(Numeric(15, 4), default=0)                     # 手续费

    # 账户信息
    currency = Column(String(10), default="CNY")                 # 货币: CNY/HKD/USD/USDT
    account_name = Column(String(100), default="默认账户")        # 券商/交易所账户名称

    # 时间信息
    transaction_date = Column(DateTime, nullable=False, index=True)  # 交易日期
    settlement_date = Column(DateTime, nullable=True)            # 结算日期

    # 备注和扩展
    notes = Column(Text, nullable=True)                          # 备注
    extra_data = Column("metadata", JSON, nullable=True)         # 扩展数据

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_investment_tx_asset', 'asset_type', 'symbol'),
        Index('idx_investment_tx_date', 'transaction_date'),
        Index('idx_investment_tx_account', 'account_name'),
    )

    def __repr__(self):
        return f"<InvestmentTransaction(id={self.id}, {self.transaction_type} {self.symbol} x{self.quantity} @{self.price})>"


class FundProduct(Base):
    """基金/债券/理财产品定义表"""
    __tablename__ = "fund_products"

    id = Column(Integer, primary_key=True, index=True)

    # 产品信息
    product_type = Column(String(20), nullable=False, index=True)  # fund/bond/bank_product
    symbol = Column(String(50), nullable=False, unique=True, index=True)  # 产品代码
    name = Column(String(200), nullable=False)                   # 产品名称
    issuer = Column(String(100), nullable=True)                  # 发行机构（基金公司/银行）

    # 风险和收益
    risk_level = Column(String(20), nullable=True)               # 风险等级: R1-R5 或 低/中/高
    expected_return = Column(Numeric(10, 4), nullable=True)      # 预期年化收益率

    # 净值信息（基金）
    nav = Column(Numeric(15, 4), nullable=True)                  # 最新净值
    nav_date = Column(DateTime, nullable=True)                   # 净值日期

    # 产品详情
    currency = Column(String(10), default="CNY")
    min_investment = Column(Numeric(15, 2), nullable=True)       # 最低投资金额
    redemption_days = Column(Integer, nullable=True)             # 赎回到账天数

    # 扩展
    extra_data = Column("metadata", JSON, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_fund_product_type', 'product_type'),
    )

    def __repr__(self):
        return f"<FundProduct(id={self.id}, {self.product_type}: {self.symbol} - {self.name})>"


class InvestmentHolding(Base):
    """投资持仓汇总表 - 从交易记录计算得出的当前持仓"""
    __tablename__ = "investment_holdings"

    id = Column(Integer, primary_key=True, index=True)

    # 资产信息
    asset_type = Column(String(20), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=True)
    market = Column(String(20), nullable=True)

    # 持仓信息
    quantity = Column(Numeric(20, 8), nullable=False)            # 当前持仓数量
    avg_cost = Column(Numeric(20, 8), nullable=False)            # 平均成本价
    total_cost = Column(Numeric(20, 4), nullable=False)          # 总成本

    # 账户信息
    currency = Column(String(10), default="CNY")
    account_name = Column(String(100), default="默认账户")

    # 时间信息
    first_buy_date = Column(DateTime, nullable=True)             # 首次买入日期
    last_transaction_date = Column(DateTime, nullable=True)      # 最后交易日期

    # 扩展
    extra_data = Column("metadata", JSON, nullable=True)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_holding_asset', 'asset_type', 'symbol', 'account_name', unique=True),
    )

    def __repr__(self):
        return f"<InvestmentHolding(id={self.id}, {self.symbol} x{self.quantity} @{self.avg_cost})>"


# ============ Phase 3 模型（预留） ============

class AllocationTarget(Base):
    """目标配置表 - 定义资产配置目标比例"""
    __tablename__ = "allocation_targets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)                   # 配置名称，如 "保守型配置"
    description = Column(Text, nullable=True)                    # 描述
    is_active = Column(Boolean, default=True, index=True)        # 是否启用

    # 目标配置 JSON: {"股票": 60, "债券": 30, "现金": 10}
    targets = Column(JSON, nullable=False)

    # 再平衡阈值
    rebalance_threshold = Column(Numeric(5, 2), default=5.0)     # 偏离阈值百分比，如 5%

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AllocationTarget(id={self.id}, name={self.name}, active={self.is_active})>"


class RebalancingAction(Base):
    """调仓建议记录表"""
    __tablename__ = "rebalancing_actions"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("allocation_targets.id"), nullable=True)

    # 建议内容
    action_type = Column(String(20), nullable=False)             # buy/sell/transfer
    asset_type = Column(String(20), nullable=False)
    symbol = Column(String(50), nullable=True)                   # 具体标的（可选）

    # 配置偏离
    current_allocation = Column(Numeric(5, 2), nullable=False)   # 当前占比 %
    target_allocation = Column(Numeric(5, 2), nullable=False)    # 目标占比 %
    drift = Column(Numeric(5, 2), nullable=False)                # 偏离度 %

    # 建议金额
    suggested_amount = Column(Numeric(20, 4), nullable=True)     # 建议调整金额
    suggested_quantity = Column(Numeric(20, 8), nullable=True)   # 建议调整数量

    # 原因和状态
    reason = Column(Text, nullable=True)                         # 建议原因
    status = Column(String(20), default="pending", index=True)   # pending/executed/dismissed

    created_at = Column(DateTime, server_default=func.now())
    executed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<RebalancingAction(id={self.id}, {self.action_type} {self.asset_type}, status={self.status})>"


# ============ Phase 4 模型（预留） ============

class RiskAlert(Base):
    """风险提醒配置表 - 止损/止盈提醒"""
    __tablename__ = "risk_alerts"

    id = Column(Integer, primary_key=True, index=True)

    # 资产信息
    asset_type = Column(String(20), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    market = Column(String(20), nullable=True)

    # 提醒类型和触发条件
    alert_type = Column(String(20), nullable=False)              # stop_loss/take_profit/trailing_stop
    trigger_price = Column(Numeric(20, 8), nullable=True)        # 触发价格
    trigger_percent = Column(Numeric(10, 4), nullable=True)      # 触发百分比（相对成本价）

    # 状态
    is_active = Column(Boolean, default=True, index=True)
    triggered_at = Column(DateTime, nullable=True)               # 触发时间
    triggered_price = Column(Numeric(20, 8), nullable=True)      # 触发时的价格
    notification_sent = Column(Boolean, default=False)           # 是否已发送通知

    # 备注
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_risk_alert_symbol', 'asset_type', 'symbol'),
    )

    def __repr__(self):
        return f"<RiskAlert(id={self.id}, {self.alert_type} {self.symbol}, active={self.is_active})>"
