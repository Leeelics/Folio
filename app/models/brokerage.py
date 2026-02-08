"""
平台托管模式数据模型
统一管理平台账户的现金和持仓
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class BrokerageAccount(Base):
    """
    平台账户表

    代表一个托管平台账户，如：
    - 富途证券（支持多币种）
    - 招商银行（储蓄卡）
    - 支付宝（余额宝+基金）
    - OKX（多币种现货）
    """

    __tablename__ = "brokerage_accounts"

    id = Column(Integer, primary_key=True, index=True)

    # 基本信息
    name = Column(String(100), nullable=False, index=True)  # 账户名称
    account_number = Column(String(100), nullable=True)  # 账号（可选）
    platform_type = Column(String(50), nullable=False, index=True)  # 平台类型
    institution = Column(String(100), nullable=True)  # 机构名称

    # 配置
    base_currency = Column(String(10), default="CNY")  # 本位币
    is_active = Column(Boolean, default=True)

    # 元数据
    extra_data = Column("extra_data", Text, nullable=True)  # JSON扩展数据
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    cash_balances = relationship(
        "AccountCashBalance", back_populates="account", cascade="all, delete-orphan"
    )
    holdings = relationship(
        "PortfolioHolding", back_populates="account", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "PortfolioTransaction", back_populates="account", cascade="all, delete-orphan"
    )
    cash_flows = relationship("CashFlow", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BrokerageAccount(id={self.id}, name='{self.name}', type='{self.platform_type}')>"


class AccountCashBalance(Base):
    """
    现金子账户表

    支持多币种、多状态：
    - available: 可用资金
    - frozen: 冻结资金（委托未成交等）
    """

    __tablename__ = "account_cash_balances"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer, ForeignKey("brokerage_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    currency = Column(String(10), nullable=False, index=True)  # 币种
    balance_type = Column(String(20), nullable=False, default="available")  # 状态类型

    amount = Column(Numeric(20, 4), nullable=False, default=0)  # 金额

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 唯一约束：每个账户每种币种的每种状态只能有一条记录
    __table_args__ = (
        UniqueConstraint(
            "account_id", "currency", "balance_type", name="uix_account_currency_type"
        ),
    )

    # 关系
    account = relationship("BrokerageAccount", back_populates="cash_balances")

    def __repr__(self):
        return f"<AccountCashBalance(account_id={self.account_id}, currency='{self.currency}', type='{self.balance_type}', amount={self.amount})>"


class PortfolioHolding(Base):
    """
    统一持仓表

    存储所有类型的持仓：
    - stock: 股票
    - fund: 基金
    - bond: 债券
    - crypto: 加密货币
    - commodity: 商品（黄金等）
    """

    __tablename__ = "portfolio_holdings"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer, ForeignKey("brokerage_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 资产信息
    asset_type = Column(String(20), nullable=False, index=True)  # 资产类型
    symbol = Column(String(50), nullable=False, index=True)  # 代码
    name = Column(String(100), nullable=True)  # 名称
    market = Column(String(20), nullable=True, index=True)  # 市场

    # 持仓信息
    quantity = Column(Numeric(20, 8), nullable=False, default=0)  # 数量
    avg_cost = Column(Numeric(20, 8), nullable=False, default=0)  # 平均成本
    total_cost = Column(Numeric(20, 4), nullable=False, default=0)  # 总成本

    # 币种
    currency = Column(String(10), default="CNY")

    # 状态
    status = Column(String(20), default="active")  # active/frozen

    # 时间
    first_buy_date = Column(DateTime, nullable=True)
    last_transaction_date = Column(DateTime, nullable=True)

    # 扩展
    extra_data = Column("extra_data", Text, nullable=True)  # JSON扩展数据
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 唯一约束
    __table_args__ = (
        UniqueConstraint("account_id", "asset_type", "symbol", "market", name="uix_holding_unique"),
    )

    # 关系
    account = relationship("BrokerageAccount", back_populates="holdings")

    def __repr__(self):
        return f"<PortfolioHolding(account_id={self.account_id}, symbol='{self.symbol}', qty={self.quantity})>"


class PortfolioTransaction(Base):
    """
    交易记录表（增强版）

    记录所有影响持仓和现金的交易
    """

    __tablename__ = "portfolio_transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer, ForeignKey("brokerage_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 资产信息
    asset_type = Column(String(20), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    market = Column(String(20), nullable=True)
    name = Column(String(100), nullable=True)  # 交易时点的名称快照

    # 交易信息
    transaction_type = Column(
        String(20), nullable=False, index=True
    )  # buy/sell/dividend/transfer/interest
    side = Column(String(10), nullable=True)  # buy/sell
    quantity = Column(Numeric(20, 8), nullable=False, default=0)
    price = Column(Numeric(20, 8), nullable=False, default=0)
    amount = Column(Numeric(20, 4), nullable=False, default=0)  # 总金额
    fees = Column(Numeric(20, 4), default=0)  # 手续费

    # 币种
    trade_currency = Column(String(10), nullable=True)

    # 时间和状态
    trade_date = Column(DateTime, nullable=False, index=True)
    settlement_status = Column(String(20), default="completed")  # completed/pending

    # 资金影响
    cash_impact = Column(Numeric(20, 4), default=0)  # 对现金的影响

    # 备注
    notes = Column(Text, nullable=True)
    extra_data = Column("extra_data", Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # 关系
    account = relationship("BrokerageAccount", back_populates="transactions")
    cash_flows = relationship(
        "CashFlow", back_populates="transaction", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PortfolioTransaction(id={self.id}, account_id={self.account_id}, symbol='{self.symbol}', type='{self.transaction_type}')>"


class CashFlow(Base):
    """
    资金流水表

    记录现金的每一笔变动
    """

    __tablename__ = "cash_flows"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer, ForeignKey("brokerage_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    currency = Column(String(10), nullable=False, index=True)
    flow_type = Column(
        String(50), nullable=False, index=True
    )  # deposit/withdrawal/trade/dividend/fee

    amount = Column(Numeric(20, 4), nullable=False)  # 正数流入，负数流出
    balance_after = Column(Numeric(20, 4), nullable=False)  # 变动后余额

    # 关联交易
    transaction_id = Column(Integer, ForeignKey("portfolio_transactions.id"), nullable=True)

    # 描述
    description = Column(Text, nullable=True)

    # 时间
    occurred_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # 关系
    account = relationship("BrokerageAccount", back_populates="cash_flows")
    transaction = relationship("PortfolioTransaction", back_populates="cash_flows")

    def __repr__(self):
        return f"<CashFlow(account_id={self.account_id}, currency='{self.currency}', type='{self.flow_type}', amount={self.amount})>"


class ExchangeRate(Base):
    """
    汇率表

    支持多币种实时汇率和历史汇率查询
    """

    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)

    from_currency = Column(String(10), nullable=False, index=True)
    to_currency = Column(String(10), nullable=False, index=True)

    rate = Column(Numeric(20, 10), nullable=False)  # 汇率

    rate_type = Column(String(20), default="mid")  # mid/bid/ask
    source = Column(String(50), nullable=True)  # 来源
    recorded_at = Column(DateTime, nullable=False, index=True)

    created_at = Column(DateTime, server_default=func.now())

    # 唯一约束
    __table_args__ = (
        UniqueConstraint(
            "from_currency", "to_currency", "recorded_at", name="uix_exchange_rate_unique"
        ),
    )

    def __repr__(self):
        return f"<ExchangeRate({self.from_currency}->{self.to_currency}: {self.rate})>"
