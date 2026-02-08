"""投资管理服务 - 交易记录 CRUD、持仓计算、基金产品管理"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investment import (
    FundProduct,
    InvestmentHolding,
    InvestmentTransaction,
)

logger = logging.getLogger(__name__)


class InvestmentManager:
    """投资管理服务 - 处理交易记录和持仓计算"""

    # ============ 交易记录 CRUD ============

    async def add_transaction(
        self,
        db: AsyncSession,
        asset_type: str,
        symbol: str,
        transaction_type: str,
        quantity: Decimal,
        price: Decimal,
        transaction_date: datetime,
        name: Optional[str] = None,
        market: Optional[str] = None,
        fees: Decimal = Decimal("0"),
        currency: str = "CNY",
        account_name: str = "默认账户",
        settlement_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        extra_data: Optional[Dict] = None,
    ) -> InvestmentTransaction:
        """录入一笔交易记录"""
        # 计算总金额
        amount = quantity * price

        transaction = InvestmentTransaction(
            asset_type=asset_type,
            symbol=symbol.upper(),
            name=name,
            market=market,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            amount=amount,
            fees=fees,
            currency=currency,
            account_name=account_name,
            transaction_date=transaction_date,
            settlement_date=settlement_date,
            notes=notes,
            extra_data=extra_data,
        )

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)

        logger.info(
            f"录入交易: {transaction_type} {symbol} x{quantity} @{price}, "
            f"账户: {account_name}"
        )

        # 更新持仓汇总
        await self._update_holding(db, transaction)

        return transaction

    async def update_transaction(
        self,
        db: AsyncSession,
        transaction_id: int,
        **kwargs,
    ) -> Optional[InvestmentTransaction]:
        """更新交易记录"""
        stmt = select(InvestmentTransaction).where(
            InvestmentTransaction.id == transaction_id
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            return None

        # 记录旧值用于重新计算持仓
        old_symbol = transaction.symbol
        old_account = transaction.account_name
        old_asset_type = transaction.asset_type

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(transaction, key) and value is not None:
                setattr(transaction, key, value)

        # 重新计算金额
        if "quantity" in kwargs or "price" in kwargs:
            transaction.amount = transaction.quantity * transaction.price

        await db.commit()
        await db.refresh(transaction)

        # 重新计算相关持仓
        await self._recalculate_holding(
            db, old_asset_type, old_symbol, old_account
        )
        if (
            transaction.symbol != old_symbol
            or transaction.account_name != old_account
        ):
            await self._recalculate_holding(
                db, transaction.asset_type, transaction.symbol, transaction.account_name
            )

        return transaction

    async def delete_transaction(
        self,
        db: AsyncSession,
        transaction_id: int,
    ) -> bool:
        """删除交易记录"""
        stmt = select(InvestmentTransaction).where(
            InvestmentTransaction.id == transaction_id
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            return False

        # 记录信息用于重新计算持仓
        asset_type = transaction.asset_type
        symbol = transaction.symbol
        account_name = transaction.account_name

        await db.delete(transaction)
        await db.commit()

        # 重新计算持仓
        await self._recalculate_holding(db, asset_type, symbol, account_name)

        logger.info(f"删除交易记录: ID={transaction_id}")
        return True

    async def get_transaction(
        self,
        db: AsyncSession,
        transaction_id: int,
    ) -> Optional[InvestmentTransaction]:
        """获取单条交易记录"""
        stmt = select(InvestmentTransaction).where(
            InvestmentTransaction.id == transaction_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_transactions(
        self,
        db: AsyncSession,
        asset_type: Optional[str] = None,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        account_name: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[InvestmentTransaction]:
        """查询交易记录（支持多种筛选条件）"""
        stmt = select(InvestmentTransaction)

        # 构建筛选条件
        conditions = []
        if asset_type:
            conditions.append(InvestmentTransaction.asset_type == asset_type)
        if symbol:
            conditions.append(InvestmentTransaction.symbol == symbol.upper())
        if market:
            conditions.append(InvestmentTransaction.market == market)
        if account_name:
            conditions.append(InvestmentTransaction.account_name == account_name)
        if transaction_type:
            conditions.append(InvestmentTransaction.transaction_type == transaction_type)
        if start_date:
            conditions.append(InvestmentTransaction.transaction_date >= start_date)
        if end_date:
            conditions.append(InvestmentTransaction.transaction_date <= end_date)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 按交易日期倒序
        stmt = stmt.order_by(desc(InvestmentTransaction.transaction_date))
        stmt = stmt.limit(limit).offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_transaction_count(
        self,
        db: AsyncSession,
        asset_type: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> int:
        """获取交易记录数量"""
        stmt = select(func.count(InvestmentTransaction.id))

        if asset_type:
            stmt = stmt.where(InvestmentTransaction.asset_type == asset_type)
        if symbol:
            stmt = stmt.where(InvestmentTransaction.symbol == symbol.upper())

        result = await db.execute(stmt)
        return result.scalar() or 0

    # ============ 持仓计算 ============

    async def _update_holding(
        self,
        db: AsyncSession,
        transaction: InvestmentTransaction,
    ) -> None:
        """根据新交易更新持仓汇总"""
        await self._recalculate_holding(
            db,
            transaction.asset_type,
            transaction.symbol,
            transaction.account_name,
        )

    async def _recalculate_holding(
        self,
        db: AsyncSession,
        asset_type: str,
        symbol: str,
        account_name: str,
    ) -> None:
        """重新计算指定资产的持仓"""
        # 获取该资产的所有交易记录
        stmt = select(InvestmentTransaction).where(
            and_(
                InvestmentTransaction.asset_type == asset_type,
                InvestmentTransaction.symbol == symbol,
                InvestmentTransaction.account_name == account_name,
            )
        ).order_by(InvestmentTransaction.transaction_date)

        result = await db.execute(stmt)
        transactions = list(result.scalars().all())

        # 查找现有持仓记录
        holding_stmt = select(InvestmentHolding).where(
            and_(
                InvestmentHolding.asset_type == asset_type,
                InvestmentHolding.symbol == symbol,
                InvestmentHolding.account_name == account_name,
            )
        )
        holding_result = await db.execute(holding_stmt)
        holding = holding_result.scalar_one_or_none()

        if not transactions:
            # 没有交易记录，删除持仓
            if holding:
                await db.delete(holding)
                await db.commit()
            return

        # 计算持仓：使用移动加权平均法
        total_quantity = Decimal("0")
        total_cost = Decimal("0")
        first_buy_date = None
        last_transaction_date = None
        name = None
        market = None
        currency = "CNY"

        for tx in transactions:
            if tx.transaction_type in ("buy", "transfer_in"):
                # 买入：增加持仓和成本
                total_quantity += tx.quantity
                total_cost += tx.amount + (tx.fees or Decimal("0"))
                if first_buy_date is None:
                    first_buy_date = tx.transaction_date
            elif tx.transaction_type in ("sell", "transfer_out"):
                # 卖出：减少持仓，按比例减少成本
                if total_quantity > 0:
                    cost_ratio = tx.quantity / total_quantity
                    total_cost -= total_cost * cost_ratio
                total_quantity -= tx.quantity
            elif tx.transaction_type == "dividend":
                # 分红：不影响持仓数量，可以选择是否计入成本
                pass
            elif tx.transaction_type == "split":
                # 拆股：调整数量和成本价
                # quantity 字段存储拆股后的新数量
                if tx.extra_data and "split_ratio" in tx.extra_data:
                    split_ratio = Decimal(str(tx.extra_data["split_ratio"]))
                    total_quantity = total_quantity * split_ratio

            # 更新元数据
            name = tx.name or name
            market = tx.market or market
            currency = tx.currency or currency
            last_transaction_date = tx.transaction_date

        # 计算平均成本
        if total_quantity > 0:
            avg_cost = total_cost / total_quantity
        else:
            avg_cost = Decimal("0")
            total_cost = Decimal("0")

        # 更新或创建持仓记录
        if holding:
            holding.quantity = total_quantity
            holding.avg_cost = avg_cost
            holding.total_cost = total_cost
            holding.name = name
            holding.market = market
            holding.currency = currency
            holding.first_buy_date = first_buy_date
            holding.last_transaction_date = last_transaction_date
        else:
            holding = InvestmentHolding(
                asset_type=asset_type,
                symbol=symbol,
                name=name,
                market=market,
                quantity=total_quantity,
                avg_cost=avg_cost,
                total_cost=total_cost,
                currency=currency,
                account_name=account_name,
                first_buy_date=first_buy_date,
                last_transaction_date=last_transaction_date,
            )
            db.add(holding)

        await db.commit()

    async def get_holdings(
        self,
        db: AsyncSession,
        asset_type: Optional[str] = None,
        account_name: Optional[str] = None,
        include_zero: bool = False,
    ) -> List[InvestmentHolding]:
        """获取持仓汇总"""
        stmt = select(InvestmentHolding)

        conditions = []
        if asset_type:
            conditions.append(InvestmentHolding.asset_type == asset_type)
        if account_name:
            conditions.append(InvestmentHolding.account_name == account_name)
        if not include_zero:
            conditions.append(InvestmentHolding.quantity > 0)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(
            InvestmentHolding.asset_type,
            InvestmentHolding.symbol,
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_holding(
        self,
        db: AsyncSession,
        asset_type: str,
        symbol: str,
        account_name: str = "默认账户",
    ) -> Optional[InvestmentHolding]:
        """获取单个持仓"""
        stmt = select(InvestmentHolding).where(
            and_(
                InvestmentHolding.asset_type == asset_type,
                InvestmentHolding.symbol == symbol.upper(),
                InvestmentHolding.account_name == account_name,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_transaction_history(
        self,
        db: AsyncSession,
        symbol: str,
        account_name: Optional[str] = None,
    ) -> List[InvestmentTransaction]:
        """获取单个资产的交易历史"""
        stmt = select(InvestmentTransaction).where(
            InvestmentTransaction.symbol == symbol.upper()
        )

        if account_name:
            stmt = stmt.where(InvestmentTransaction.account_name == account_name)

        stmt = stmt.order_by(desc(InvestmentTransaction.transaction_date))

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ============ 基金/理财产品管理 ============

    async def add_fund_product(
        self,
        db: AsyncSession,
        product_type: str,
        symbol: str,
        name: str,
        issuer: Optional[str] = None,
        risk_level: Optional[str] = None,
        expected_return: Optional[Decimal] = None,
        nav: Optional[Decimal] = None,
        nav_date: Optional[datetime] = None,
        currency: str = "CNY",
        min_investment: Optional[Decimal] = None,
        redemption_days: Optional[int] = None,
        extra_data: Optional[Dict] = None,
    ) -> FundProduct:
        """添加基金/理财产品"""
        product = FundProduct(
            product_type=product_type,
            symbol=symbol.upper(),
            name=name,
            issuer=issuer,
            risk_level=risk_level,
            expected_return=expected_return,
            nav=nav,
            nav_date=nav_date,
            currency=currency,
            min_investment=min_investment,
            redemption_days=redemption_days,
            extra_data=extra_data,
        )

        db.add(product)
        await db.commit()
        await db.refresh(product)

        logger.info(f"添加产品: {product_type} {symbol} - {name}")
        return product

    async def update_fund_nav(
        self,
        db: AsyncSession,
        symbol: str,
        nav: Decimal,
        nav_date: Optional[datetime] = None,
    ) -> Optional[FundProduct]:
        """更新基金净值"""
        stmt = select(FundProduct).where(FundProduct.symbol == symbol.upper())
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            return None

        product.nav = nav
        product.nav_date = nav_date or datetime.now()

        await db.commit()
        await db.refresh(product)

        logger.info(f"更新净值: {symbol} = {nav}")
        return product

    async def get_fund_products(
        self,
        db: AsyncSession,
        product_type: Optional[str] = None,
        is_active: bool = True,
    ) -> List[FundProduct]:
        """获取基金/理财产品列表"""
        stmt = select(FundProduct)

        conditions = []
        if product_type:
            conditions.append(FundProduct.product_type == product_type)
        if is_active is not None:
            conditions.append(FundProduct.is_active == is_active)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(FundProduct.product_type, FundProduct.symbol)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_fund_product(
        self,
        db: AsyncSession,
        symbol: str,
    ) -> Optional[FundProduct]:
        """获取单个基金/理财产品"""
        stmt = select(FundProduct).where(FundProduct.symbol == symbol.upper())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # ============ 统计和汇总 ============

    async def get_portfolio_summary(
        self,
        db: AsyncSession,
        account_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取投资组合汇总"""
        holdings = await self.get_holdings(db, account_name=account_name)

        summary = {
            "total_cost": Decimal("0"),
            "holdings_count": len(holdings),
            "by_asset_type": {},
            "by_account": {},
        }

        for holding in holdings:
            # 按资产类型汇总
            asset_type = holding.asset_type
            if asset_type not in summary["by_asset_type"]:
                summary["by_asset_type"][asset_type] = {
                    "count": 0,
                    "total_cost": Decimal("0"),
                }
            summary["by_asset_type"][asset_type]["count"] += 1
            summary["by_asset_type"][asset_type]["total_cost"] += holding.total_cost

            # 按账户汇总
            account = holding.account_name
            if account not in summary["by_account"]:
                summary["by_account"][account] = {
                    "count": 0,
                    "total_cost": Decimal("0"),
                }
            summary["by_account"][account]["count"] += 1
            summary["by_account"][account]["total_cost"] += holding.total_cost

            summary["total_cost"] += holding.total_cost

        # 转换 Decimal 为 float
        summary["total_cost"] = float(summary["total_cost"])
        for key in summary["by_asset_type"]:
            summary["by_asset_type"][key]["total_cost"] = float(
                summary["by_asset_type"][key]["total_cost"]
            )
        for key in summary["by_account"]:
            summary["by_account"][key]["total_cost"] = float(
                summary["by_account"][key]["total_cost"]
            )

        return summary
