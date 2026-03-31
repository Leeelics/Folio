"""CSV 导出服务 - Phase 4"""

import io
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

import pandas as pd
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Account, Expense, Holding
from app.models.investment import InvestmentTransaction

logger = logging.getLogger(__name__)


class ExportService:
    """CSV 导出服务"""

    async def export_transactions_csv(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        asset_type: Optional[str] = None,
    ) -> str:
        """导出交易记录为 CSV"""
        # 查询交易记录
        stmt = select(InvestmentTransaction).where(
            and_(
                InvestmentTransaction.transaction_date >= start_date,
                InvestmentTransaction.transaction_date <= end_date,
            )
        )
        if asset_type:
            stmt = stmt.where(InvestmentTransaction.asset_type == asset_type)

        stmt = stmt.order_by(InvestmentTransaction.transaction_date)
        result = await db.execute(stmt)
        transactions = list(result.scalars().all())

        # 限制导出数量
        if len(transactions) > 10000:
            logger.warning(f"导出交易记录数量过多: {len(transactions)}, 限制为 10000")
            transactions = transactions[:10000]

        # 构建 DataFrame
        data = []
        for tx in transactions:
            data.append({
                "id": tx.id,
                "date": tx.transaction_date.strftime("%Y-%m-%d"),
                "symbol": tx.symbol,
                "name": tx.name or "",
                "asset_type": tx.asset_type,
                "type": tx.transaction_type,
                "quantity": float(tx.quantity),
                "price": float(tx.price),
                "amount": float(tx.amount),
                "fees": float(tx.fees or Decimal("0")),
                "currency": tx.currency,
                "account": tx.account_name,
                "notes": tx.notes or "",
            })

        df = pd.DataFrame(data)

        # 转换为 CSV（UTF-8 with BOM，Excel 兼容）
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig", float_format="%.4f")
        return csv_buffer.getvalue()

    async def export_expenses_csv(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        category: Optional[str] = None,
    ) -> str:
        """导出支出记录为 CSV"""
        # 查询支出记录
        stmt = select(Expense).where(
            and_(
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )
        )
        if category:
            stmt = stmt.where(Expense.category == category)

        stmt = stmt.order_by(Expense.expense_date)
        result = await db.execute(stmt)
        expenses = list(result.scalars().all())

        # 限制导出数量
        if len(expenses) > 10000:
            logger.warning(f"导出支出记录数量过多: {len(expenses)}, 限制为 10000")
            expenses = expenses[:10000]

        # 构建 DataFrame
        data = []
        for exp in expenses:
            data.append({
                "id": exp.id,
                "date": exp.expense_date.strftime("%Y-%m-%d"),
                "amount": float(exp.amount),
                "category": exp.category,
                "subcategory": exp.subcategory or "",
                "merchant": exp.merchant or "",
                "payment_method": exp.payment_method or "",
                "is_shared": exp.is_shared,
                "notes": exp.notes or "",
            })

        df = pd.DataFrame(data)

        # 转换为 CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig", float_format="%.2f")
        return csv_buffer.getvalue()

    async def export_holdings_snapshot_csv(
        self,
        db: AsyncSession,
        as_of_date: Optional[date] = None,
    ) -> str:
        """导出持仓快照为 CSV"""
        # 查询当前持仓
        stmt = select(Holding).where(
            and_(
                Holding.is_active == True,
                Holding.quantity > 0,
            )
        )
        result = await db.execute(stmt)
        holdings = list(result.scalars().all())

        # 构建 DataFrame
        data = []
        for holding in holdings:
            market_value = (
                float(holding.current_price * holding.quantity)
                if holding.current_price
                else float(holding.total_cost)
            )

            data.append({
                "symbol": holding.symbol,
                "name": holding.name or "",
                "asset_type": holding.asset_type,
                "market": holding.market or "",
                "quantity": float(holding.quantity),
                "avg_cost": float(holding.avg_cost),
                "current_price": float(holding.current_price) if holding.current_price else "",
                "market_value": market_value,
                "account_id": holding.account_id,
                "currency": holding.currency,
                "is_liquid": holding.is_liquid,
            })

        df = pd.DataFrame(data)

        # 转换为 CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig", float_format="%.4f")
        return csv_buffer.getvalue()

    async def export_accounts_csv(
        self,
        db: AsyncSession,
    ) -> str:
        """导出账户列表为 CSV"""
        # 查询所有账户
        stmt = select(Account).order_by(Account.account_type, Account.name)
        result = await db.execute(stmt)
        accounts = list(result.scalars().all())

        # 构建 DataFrame
        data = []
        for account in accounts:
            holdings_value = account.holdings_value or Decimal("0")
            total_value = account.balance + holdings_value

            data.append({
                "id": account.id,
                "name": account.name,
                "type": account.account_type,
                "institution": account.institution or "",
                "balance": float(account.balance),
                "holdings_value": float(holdings_value),
                "total_value": float(total_value),
                "currency": account.currency,
                "is_active": account.is_active,
            })

        df = pd.DataFrame(data)

        # 转换为 CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig", float_format="%.2f")
        return csv_buffer.getvalue()
