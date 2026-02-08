"""
平台账户服务
统一管理平台账户的现金和持仓，支持交易联动更新
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from app.models.brokerage import (
    BrokerageAccount,
    AccountCashBalance,
    PortfolioHolding,
    PortfolioTransaction,
    CashFlow,
)
from app.services.exchange_rate_service import ExchangeRateService

logger = logging.getLogger(__name__)


@dataclass
class AccountCashView:
    """现金视图"""

    currency: str
    available: Decimal
    frozen: Decimal
    total: Decimal

    def to_base_currency(self, rate: Decimal) -> Decimal:
        return self.total * rate


@dataclass
class AccountHoldingView:
    """持仓视图"""

    id: int
    asset_type: str
    symbol: str
    name: str
    market: str
    quantity: Decimal
    avg_cost: Decimal
    total_cost: Decimal
    currency: str
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    pnl_percent: Optional[Decimal] = None

    def to_base_currency(self, rate: Decimal) -> Decimal:
        if self.market_value:
            return self.market_value * rate
        return self.total_cost * rate


@dataclass
class UnifiedAccountView:
    """统一账户视图 - 包含现金和持仓"""

    account_id: int
    account_name: str
    platform_type: str
    institution: str
    base_currency: str

    # 现金（按币种分组）
    cash_balances: List[AccountCashView]

    # 持仓
    holdings: List[AccountHoldingView]

    # 汇总（本位币）
    total_cash: Decimal
    total_holdings: Decimal
    total_assets: Decimal

    # 盈亏
    total_cost: Decimal
    total_pnl: Optional[Decimal] = None
    total_pnl_percent: Optional[Decimal] = None


@dataclass
class AccountSummary:
    """账户摘要（用于列表展示）"""

    account_id: int
    account_name: str
    platform_type: str
    institution: str
    cash_count: int
    holding_count: int
    total_assets_cny: Decimal


class BrokerageAccountService:
    """
    平台账户服务

    核心功能：
    1. 账户CRUD
    2. 现金管理（多币种）
    3. 持仓管理
    4. 交易录入（自动联动更新现金和持仓）
    5. 统一视图查询
    """

    def __init__(self):
        self.exchange_service = ExchangeRateService()

    # ============ 账户管理 ============

    async def create_account(
        self,
        db: AsyncSession,
        name: str,
        platform_type: str,
        institution: str = None,
        account_number: str = None,
        base_currency: str = "CNY",
        notes: str = None,
    ) -> BrokerageAccount:
        """创建平台账户"""
        account = BrokerageAccount(
            name=name,
            platform_type=platform_type,
            institution=institution,
            account_number=account_number,
            base_currency=base_currency,
            notes=notes,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        logger.info(f"创建账户: {name} ({platform_type})")
        return account

    async def get_account(self, db: AsyncSession, account_id: int) -> Optional[BrokerageAccount]:
        """获取单个账户"""
        stmt = select(BrokerageAccount).where(BrokerageAccount.id == account_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_accounts(
        self, db: AsyncSession, platform_type: str = None, is_active: bool = True
    ) -> List[BrokerageAccount]:
        """获取所有账户"""
        stmt = select(BrokerageAccount)

        if platform_type:
            stmt = stmt.where(BrokerageAccount.platform_type == platform_type)
        if is_active is not None:
            stmt = stmt.where(BrokerageAccount.is_active == is_active)

        stmt = stmt.order_by(BrokerageAccount.platform_type, BrokerageAccount.name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_account(
        self, db: AsyncSession, account_id: int, **kwargs
    ) -> Optional[BrokerageAccount]:
        """更新账户信息"""
        account = await self.get_account(db, account_id)
        if not account:
            return None

        # 允许的字段
        allowed_fields = [
            "name",
            "institution",
            "account_number",
            "base_currency",
            "is_active",
            "notes",
        ]

        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(account, key, value)

        await db.commit()
        await db.refresh(account)
        return account

    async def delete_account(self, db: AsyncSession, account_id: int) -> bool:
        """删除账户（级联删除所有关联数据）"""
        account = await self.get_account(db, account_id)
        if not account:
            return False

        await db.delete(account)
        await db.commit()

        logger.info(f"删除账户: {account_id}")
        return True

    # ============ 现金管理 ============

    async def get_cash_balance(
        self, db: AsyncSession, account_id: int, currency: str, balance_type: str = "available"
    ) -> Optional[AccountCashBalance]:
        """获取现金余额记录"""
        stmt = select(AccountCashBalance).where(
            and_(
                AccountCashBalance.account_id == account_id,
                AccountCashBalance.currency == currency.upper(),
                AccountCashBalance.balance_type == balance_type,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_cash_balance(
        self,
        db: AsyncSession,
        account_id: int,
        currency: str,
        amount: Decimal,
        balance_type: str = "available",
    ) -> AccountCashBalance:
        """
        设置现金余额（创建或更新）

        如果余额记录不存在则创建，否则更新
        """
        balance = await self.get_cash_balance(db, account_id, currency, balance_type)

        if balance:
            # 更新
            old_amount = balance.amount
            balance.amount = amount
        else:
            # 创建
            balance = AccountCashBalance(
                account_id=account_id,
                currency=currency.upper(),
                balance_type=balance_type,
                amount=amount,
            )
            db.add(balance)
            old_amount = Decimal("0")

        await db.commit()
        await db.refresh(balance)

        # 记录资金流水
        if amount != old_amount:
            await self._record_cash_flow(
                db, account_id, currency, amount - old_amount, amount, "adjustment", "余额调整"
            )

        return balance

    async def adjust_cash_balance(
        self,
        db: AsyncSession,
        account_id: int,
        currency: str,
        delta: Decimal,
        balance_type: str = "available",
        description: str = None,
    ) -> AccountCashBalance:
        """
        调整现金余额（增加或减少）

        Args:
            delta: 变动金额（正数增加，负数减少）
        """
        balance = await self.get_cash_balance(db, account_id, currency, balance_type)

        if balance:
            new_amount = balance.amount + delta
        else:
            new_amount = delta
            balance = AccountCashBalance(
                account_id=account_id,
                currency=currency.upper(),
                balance_type=balance_type,
                amount=new_amount,
            )
            db.add(balance)

        balance.amount = new_amount
        await db.commit()
        await db.refresh(balance)

        # 记录资金流水
        flow_type = "deposit" if delta > 0 else "withdrawal"
        await self._record_cash_flow(
            db, account_id, currency, delta, new_amount, flow_type, description or "余额调整"
        )

        return balance

    async def get_all_cash_balances(
        self, db: AsyncSession, account_id: int
    ) -> List[AccountCashBalance]:
        """获取账户的所有现金余额"""
        stmt = (
            select(AccountCashBalance)
            .where(AccountCashBalance.account_id == account_id)
            .order_by(AccountCashBalance.currency, AccountCashBalance.balance_type)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ============ 持仓管理 ============

    async def get_holding(
        self, db: AsyncSession, account_id: int, asset_type: str, symbol: str, market: str = None
    ) -> Optional[PortfolioHolding]:
        """获取持仓记录"""
        stmt = select(PortfolioHolding).where(
            and_(
                PortfolioHolding.account_id == account_id,
                PortfolioHolding.asset_type == asset_type,
                PortfolioHolding.symbol == symbol.upper(),
            )
        )
        if market:
            stmt = stmt.where(PortfolioHolding.market == market)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_holdings(
        self, db: AsyncSession, account_id: int = None, asset_type: str = None
    ) -> List[PortfolioHolding]:
        """获取持仓列表"""
        stmt = select(PortfolioHolding)

        if account_id:
            stmt = stmt.where(PortfolioHolding.account_id == account_id)
        if asset_type:
            stmt = stmt.where(PortfolioHolding.asset_type == asset_type)

        stmt = stmt.order_by(PortfolioHolding.asset_type, PortfolioHolding.symbol)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ============ 交易录入（核心功能：联动更新） ============

    async def add_transaction(
        self,
        db: AsyncSession,
        account_id: int,
        asset_type: str,
        symbol: str,
        transaction_type: str,
        quantity: Decimal,
        price: Decimal,
        trade_date: datetime,
        market: str = None,
        name: str = None,
        fees: Decimal = Decimal("0"),
        trade_currency: str = "CNY",
        notes: str = None,
    ) -> PortfolioTransaction:
        """
        录入交易（自动联动更新现金和持仓）

        支持的交易类型：
        - buy: 买入（扣减现金，增加持仓）
        - sell: 卖出（增加现金，减少持仓）
        - dividend: 分红（增加现金）
        - transfer_in: 转入（增加持仓，不扣现金）
        - transfer_out: 转出（减少持仓，不加现金）
        - interest: 利息（增加现金）

        Args:
            account_id: 账户ID
            asset_type: 资产类型
            symbol: 代码
            transaction_type: 交易类型
            quantity: 数量
            price: 价格
            trade_date: 交易日期
            market: 市场
            name: 名称
            fees: 手续费
            trade_currency: 交易币种
            notes: 备注

        Returns:
            PortfolioTransaction: 创建的交易记录
        """
        # 计算总金额
        amount = quantity * price

        # 确定交易方向
        side = None
        if transaction_type in ["buy", "transfer_in"]:
            side = "buy"
        elif transaction_type in ["sell", "transfer_out"]:
            side = "sell"

        # 创建交易记录
        transaction = PortfolioTransaction(
            account_id=account_id,
            asset_type=asset_type,
            symbol=symbol.upper(),
            market=market,
            name=name or symbol.upper(),
            transaction_type=transaction_type,
            side=side,
            quantity=quantity,
            price=price,
            amount=amount,
            fees=fees,
            trade_currency=trade_currency,
            trade_date=trade_date,
            settlement_status="completed",  # 方案A：立即完成
            notes=notes,
        )
        db.add(transaction)
        await db.flush()  # 获取ID

        # 联动更新现金和持仓
        if transaction_type == "buy":
            # 买入：扣减现金，增加持仓
            cash_impact = -(amount + fees)
            await self.adjust_cash_balance(
                db, account_id, trade_currency, cash_impact, "available", f"买入 {symbol}"
            )
            await self._update_holding_on_buy(
                db, account_id, asset_type, symbol, market, quantity, price, trade_date, name
            )

        elif transaction_type == "sell":
            # 卖出：增加现金，减少持仓
            cash_impact = amount - fees
            await self.adjust_cash_balance(
                db, account_id, trade_currency, cash_impact, "available", f"卖出 {symbol}"
            )
            await self._update_holding_on_sell(db, account_id, asset_type, symbol, market, quantity)

        elif transaction_type == "dividend":
            # 分红：增加现金
            await self.adjust_cash_balance(
                db, account_id, trade_currency, amount, "available", f"{symbol} 分红"
            )

        elif transaction_type == "interest":
            # 利息：增加现金
            await self.adjust_cash_balance(
                db, account_id, trade_currency, amount, "available", f"{symbol} 利息"
            )

        elif transaction_type == "transfer_in":
            # 转入：增加持仓（不扣现金）
            await self._update_holding_on_buy(
                db, account_id, asset_type, symbol, market, quantity, price, trade_date, name
            )

        elif transaction_type == "transfer_out":
            # 转出：减少持仓（不加现金）
            await self._update_holding_on_sell(db, account_id, asset_type, symbol, market, quantity)

        # 更新交易记录的现金影响
        transaction.cash_impact = (
            cash_impact if transaction_type in ["buy", "sell"] else Decimal("0")
        )

        await db.commit()
        await db.refresh(transaction)

        logger.info(f"录入交易: {account_id} {transaction_type} {symbol} x{quantity} @ {price}")
        return transaction

    async def _update_holding_on_buy(
        self,
        db: AsyncSession,
        account_id: int,
        asset_type: str,
        symbol: str,
        market: str,
        quantity: Decimal,
        price: Decimal,
        trade_date: datetime,
        name: str = None,
    ):
        """买入时更新持仓（移动加权平均法）"""
        holding = await self.get_holding(db, account_id, asset_type, symbol, market)

        if holding:
            # 现有持仓，计算新的平均成本
            old_quantity = holding.quantity
            old_cost = holding.total_cost

            new_quantity = old_quantity + quantity
            new_cost = old_cost + (quantity * price)

            if new_quantity > 0:
                holding.avg_cost = new_cost / new_quantity
            else:
                holding.avg_cost = Decimal("0")

            holding.quantity = new_quantity
            holding.total_cost = new_cost
            holding.last_transaction_date = trade_date
        else:
            # 新建持仓
            holding = PortfolioHolding(
                account_id=account_id,
                asset_type=asset_type,
                symbol=symbol.upper(),
                market=market,
                name=name or symbol.upper(),
                quantity=quantity,
                avg_cost=price,
                total_cost=quantity * price,
                first_buy_date=trade_date,
                last_transaction_date=trade_date,
            )
            db.add(holding)

    async def _update_holding_on_sell(
        self,
        db: AsyncSession,
        account_id: int,
        asset_type: str,
        symbol: str,
        market: str,
        quantity: Decimal,
    ):
        """卖出时更新持仓"""
        holding = await self.get_holding(db, account_id, asset_type, symbol, market)

        if not holding:
            logger.warning(f"卖出时未找到持仓: {account_id} {symbol}")
            return

        # 按比例减少成本
        if holding.quantity > 0:
            cost_ratio = quantity / holding.quantity
            holding.total_cost -= holding.total_cost * cost_ratio

        holding.quantity -= quantity
        holding.last_transaction_date = datetime.now()

        # 如果持仓为0，可以选择删除或保留记录
        if holding.quantity <= 0:
            holding.quantity = Decimal("0")
            holding.total_cost = Decimal("0")

    async def _record_cash_flow(
        self,
        db: AsyncSession,
        account_id: int,
        currency: str,
        amount: Decimal,
        balance_after: Decimal,
        flow_type: str,
        description: str,
        transaction_id: int = None,
    ):
        """记录资金流水"""
        flow = CashFlow(
            account_id=account_id,
            currency=currency,
            flow_type=flow_type,
            amount=amount,
            balance_after=balance_after,
            transaction_id=transaction_id,
            description=description,
            occurred_at=datetime.now(),
        )
        db.add(flow)

    # ============ 统一视图查询 ============

    async def get_unified_account_view(
        self,
        db: AsyncSession,
        account_id: int,
        base_currency: str = "CNY",
        include_prices: bool = False,
    ) -> Optional[UnifiedAccountView]:
        """
        获取统一账户视图（现金 + 持仓）

        Args:
            account_id: 账户ID
            base_currency: 折算基准币种
            include_prices: 是否查询实时价格计算盈亏
        """
        # 获取账户信息
        account = await self.get_account(db, account_id)
        if not account:
            return None

        # 获取所有现金余额
        cash_balances_db = await self.get_all_cash_balances(db, account_id)
        cash_balances = []
        total_cash = Decimal("0")

        for cash in cash_balances_db:
            # 折算为基准币种
            rate = await self.exchange_service.get_rate(db, cash.currency, base_currency)
            cash_cny = cash.amount * rate
            total_cash += cash_cny

            # 合并同一币种的不同状态
            existing = next((c for c in cash_balances if c.currency == cash.currency), None)
            if existing:
                if cash.balance_type == "available":
                    existing.available = cash.amount
                elif cash.balance_type == "frozen":
                    existing.frozen = cash.amount
                existing.total = existing.available + existing.frozen
            else:
                cash_balances.append(
                    AccountCashView(
                        currency=cash.currency,
                        available=cash.amount if cash.balance_type == "available" else Decimal("0"),
                        frozen=cash.amount if cash.balance_type == "frozen" else Decimal("0"),
                        total=cash.amount,
                    )
                )

        # 获取所有持仓
        holdings_db = await self.get_all_holdings(db, account_id)
        holdings = []
        total_holdings = Decimal("0")
        total_cost = Decimal("0")

        for holding in holdings_db:
            rate = await self.exchange_service.get_rate(db, holding.currency, base_currency)

            # 计算市值和盈亏
            current_price = None
            market_value = None
            pnl = None
            pnl_percent = None

            if include_prices and holding.quantity > 0:
                # TODO: 从行情服务获取实时价格
                current_price = holding.avg_cost  # 暂时使用成本价
                market_value = holding.quantity * current_price
                pnl = market_value - holding.total_cost
                if holding.total_cost > 0:
                    pnl_percent = (pnl / holding.total_cost) * 100

            holding_value = (market_value or holding.total_cost) * rate
            total_holdings += holding_value
            total_cost += holding.total_cost * rate

            holdings.append(
                AccountHoldingView(
                    id=holding.id,
                    asset_type=holding.asset_type,
                    symbol=holding.symbol,
                    name=holding.name or holding.symbol,
                    market=holding.market or "",
                    quantity=holding.quantity,
                    avg_cost=holding.avg_cost,
                    total_cost=holding.total_cost,
                    currency=holding.currency,
                    current_price=current_price,
                    market_value=market_value,
                    pnl=pnl,
                    pnl_percent=pnl_percent,
                )
            )

        # 计算总盈亏
        total_pnl = None
        total_pnl_percent = None
        if include_prices and total_cost > 0:
            total_pnl = total_holdings - total_cost
            total_pnl_percent = (total_pnl / total_cost) * 100

        return UnifiedAccountView(
            account_id=account_id,
            account_name=account.name,
            platform_type=account.platform_type,
            institution=account.institution or "",
            base_currency=base_currency,
            cash_balances=cash_balances,
            holdings=holdings,
            total_cash=total_cash,
            total_holdings=total_holdings,
            total_assets=total_cash + total_holdings,
            total_cost=total_cost,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
        )

    async def get_all_accounts_summary(
        self, db: AsyncSession, base_currency: str = "CNY"
    ) -> Dict[str, Any]:
        """
        获取所有账户的汇总统计

        Returns:
            {
                "total_assets_cny": Decimal,
                "total_cash_cny": Decimal,
                "total_holdings_cny": Decimal,
                "accounts": List[AccountSummary]
            }
        """
        accounts = await self.get_all_accounts(db)

        summary = {
            "total_assets_cny": Decimal("0"),
            "total_cash_cny": Decimal("0"),
            "total_holdings_cny": Decimal("0"),
            "accounts": [],
        }

        for account in accounts:
            view = await self.get_unified_account_view(db, account.id, base_currency)
            if view:
                summary["total_assets_cny"] += view.total_assets
                summary["total_cash_cny"] += view.total_cash
                summary["total_holdings_cny"] += view.total_holdings

                summary["accounts"].append(
                    {
                        "account_id": view.account_id,
                        "account_name": view.account_name,
                        "platform_type": view.platform_type,
                        "institution": view.institution,
                        "cash_count": len(view.cash_balances),
                        "holding_count": len(view.holdings),
                        "total_assets_cny": view.total_assets,
                    }
                )

        return summary

    async def get_portfolio_allocation(
        self, db: AsyncSession, base_currency: str = "CNY"
    ) -> Dict[str, Any]:
        """
        获取资产分配统计（用于饼图）

        Returns:
            {
                "by_platform_type": Dict[str, Decimal],
                "by_currency": Dict[str, Decimal],
                "by_asset_type": Dict[str, Decimal]
            }
        """
        summary = await self.get_all_accounts_summary(db, base_currency)

        allocation = {"by_platform_type": {}, "by_currency": {}, "by_asset_type": {}}

        for account_summary in summary["accounts"]:
            account_id = account_summary["account_id"]
            view = await self.get_unified_account_view(db, account_id, base_currency)

            if view:
                # 按平台类型
                p_type = view.platform_type
                allocation["by_platform_type"][p_type] = (
                    allocation["by_platform_type"].get(p_type, Decimal("0")) + view.total_assets
                )

                # 按币种
                for cash in view.cash_balances:
                    allocation["by_currency"][cash.currency] = allocation["by_currency"].get(
                        cash.currency, Decimal("0")
                    ) + cash.to_base_currency(Decimal("1"))

                # 按资产类型
                for holding in view.holdings:
                    allocation["by_asset_type"][holding.asset_type] = allocation[
                        "by_asset_type"
                    ].get(holding.asset_type, Decimal("0")) + holding.to_base_currency(Decimal("1"))

        return allocation
