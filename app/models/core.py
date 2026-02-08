"""
核心数据模型 - Phase 1
包含账户、投资持仓、投资交易、预算、支出等模型
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    JSON,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


class Account(Base):
    """
    账户表
    区分投资账户和现金账户
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 基本信息
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # cash/investment
    institution: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 余额信息
    # cash账户：实际余额
    # investment账户：可用现金（未投资部分）
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))

    # 投资账户特有：持仓市值（实时计算或缓存）
    holdings_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 4), nullable=True, default=Decimal("0")
    )

    currency: Mapped[str] = mapped_column(String(10), default="CNY")

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关系
    holdings: Mapped[List["Holding"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    core_investment_transactions: Mapped[List["CoreInvestmentTransaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    expenses: Mapped[List["Expense"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    core_cash_flows: Mapped[List["CoreCashFlow"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    def calculate_holdings_value(self) -> Decimal:
        """计算持仓市值（从holdings汇总）"""
        if self.account_type != "investment":
            return Decimal("0")

        # 如果holdings未加载（避免懒加载错误），返回缓存值或0
        try:
            if not self.holdings:
                return Decimal("0")
        except Exception:
            # holdings未加载
            return self.holdings_value if self.holdings_value else Decimal("0")

        total: Decimal = Decimal("0")
        for h in self.holdings:
            if h.is_active and not h.is_liquid:  # 只计算非流动性资产
                val: Decimal = h.current_value if h.current_value else Decimal("0")
                total += val
        return total

    @property
    def total_value(self) -> Decimal:
        """总资产价值 = 余额 + 所有持仓市值（包括流动性和非流动性）"""
        if self.account_type == "investment":
            all_holdings_value = Decimal("0")
            if self.holdings:
                for h in self.holdings:
                    if h.is_active:
                        all_holdings_value += h.current_value if h.current_value else Decimal("0")
            return self.balance + all_holdings_value
        return self.balance

    @property
    def available_cash(self) -> Decimal:
        """可用现金 = 余额 + 高流动性资产（如余额宝，T+0货币基金）"""
        if self.account_type == "investment":
            liquid_value = Decimal("0")
            if self.holdings:
                for h in self.holdings:
                    if h.is_active and h.is_liquid:
                        liquid_value += h.current_value if h.current_value else Decimal("0")
            return self.balance + liquid_value
        return self.balance

    @property
    def investment_value(self) -> Decimal:
        """投资市值 = 非流动性持仓市值（股票、普通基金等长期投资）"""
        if self.account_type == "investment":
            illiquid_value = Decimal("0")
            if self.holdings:
                for h in self.holdings:
                    if h.is_active and not h.is_liquid:
                        illiquid_value += h.current_value if h.current_value else Decimal("0")
            return illiquid_value
        return Decimal("0")

    def update_holdings_value(self) -> None:
        """更新持仓市值缓存（计算所有持仓）"""
        if self.account_type == "investment":
            total = Decimal("0")
            if self.holdings:
                for h in self.holdings:
                    if h.is_active:
                        total += h.current_value if h.current_value else Decimal("0")
            self.holdings_value = total

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}', type='{self.account_type}')>"


class Holding(Base):
    """
    投资持仓表
    记录投资账户的持仓明细
    """

    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 资产信息
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    asset_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # stock/fund/bond/crypto/money_market
    market: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    # 持仓信息
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))

    # 市值信息
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    current_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 流动性标识
    is_liquid: Mapped[bool] = mapped_column(Boolean, default=False)
    # True: 高流动性资产（余额宝等T+0货币基金），计入可用现金
    # False: 普通投资（股票、普通基金等），计入持仓市值

    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关系
    account: Mapped["Account"] = relationship(back_populates="holdings")
    core_investment_transactions: Mapped[List["CoreInvestmentTransaction"]] = relationship(
        back_populates="holding", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Holding(id={self.id}, symbol='{self.symbol}', qty={self.quantity})>"


class CoreInvestmentTransaction(Base):
    """
    投资交易记录表
    记录买入、卖出、分红等投资交易
    """

    __tablename__ = "core_investment_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holding_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("holdings.id", ondelete="SET NULL"), nullable=True
    )

    # 交易信息
    transaction_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # buy/sell/dividend/interest
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))

    trade_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关系
    account: Mapped["Account"] = relationship(back_populates="core_investment_transactions")
    holding: Mapped[Optional["Holding"]] = relationship(
        back_populates="core_investment_transactions"
    )

    def __repr__(self) -> str:
        return f"<InvestmentTransaction(id={self.id}, type='{self.transaction_type}', symbol='{self.symbol}')>"


class Budget(Base):
    """
    预算表
    管理周期性或项目型预算
    """

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    budget_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # periodic/project

    # 金额信息
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    spent: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"))
    remaining: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    # 周期信息
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True
    )  # active/completed/cancelled

    # 关联账户（JSON数组）
    associated_account_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关系
    expenses: Mapped[List["Expense"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Budget(id={self.id}, name='{self.name}', type='{self.budget_type}')>"


class Expense(Base):
    """
    支出表
    记录每一笔支出（核心表）
    """

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 关联信息
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    budget_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("budgets.id"), nullable=True, index=True
    )

    # 基本信息
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # 分类信息
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 属性标识
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)

    # 可选详细信息
    merchant: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    participants: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关系
    account: Mapped["Account"] = relationship(back_populates="expenses")
    budget: Mapped[Optional["Budget"]] = relationship(back_populates="expenses")

    def __repr__(self) -> str:
        return f"<Expense(id={self.id}, amount={self.amount}, category='{self.category}')>"


class ExpenseCategory(Base):
    """
    支出分类表
    预定义分类体系
    """

    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<ExpenseCategory(category='{self.category}', subcategory='{self.subcategory}')>"


class CoreCashFlow(Base):
    """
    现金流水表
    记录现金账户的每一笔变动
    """

    __tablename__ = "core_cash_flows"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    flow_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # income/expense/transfer
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    # 关联
    expense_id: Mapped[Optional[int]] = mapped_column(ForeignKey("expenses.id"), nullable=True)
    investment_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("core_investment_transactions.id"), nullable=True
    )

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关系
    account: Mapped["Account"] = relationship(back_populates="core_cash_flows")

    def __repr__(self) -> str:
        return f"<CoreCashFlow(id={self.id}, type='{self.flow_type}', amount={self.amount})>"


class MarketSyncLog(Base):
    """
    市值同步记录表
    记录投资市值同步历史
    """

    __tablename__ = "market_sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    total_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    holdings_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<MarketSyncLog(id={self.id}, status='{self.status}', value={self.total_value})>"
