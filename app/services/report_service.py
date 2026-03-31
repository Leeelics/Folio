"""报表生成服务 - Phase 4"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Account, Expense, Holding
from app.models.investment import InvestmentHolding, InvestmentTransaction
from app.services.asset_manager import EXCHANGE_RATES

logger = logging.getLogger(__name__)


class ReportService:
    """报表生成服务"""

    async def generate_investment_performance_report(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """生成投资业绩报表"""
        # 获取期间内的所有交易
        stmt = select(InvestmentTransaction).where(
            and_(
                InvestmentTransaction.transaction_date >= start_date,
                InvestmentTransaction.transaction_date <= end_date,
            )
        )
        result = await db.execute(stmt)
        transactions = list(result.scalars().all())

        # 获取当前持仓
        holdings_stmt = select(InvestmentHolding).where(InvestmentHolding.quantity > 0)
        holdings_result = await db.execute(holdings_stmt)
        holdings = list(holdings_result.scalars().all())

        # 计算总成本、总市值、总盈亏
        total_cost = Decimal("0")
        total_market_value = Decimal("0")
        dividend_income = Decimal("0")

        holdings_breakdown = []
        for holding in holdings:
            cost = holding.total_cost or Decimal("0")
            # 获取当前价格（从 extra_data 或默认使用 avg_cost）
            current_price = None
            if holding.extra_data and isinstance(holding.extra_data, dict):
                current_price = holding.extra_data.get("current_price")
            if current_price is None:
                current_price = holding.avg_cost  # 默认使用平均成本
            
            market_value = current_price * holding.quantity if current_price else cost
            pnl = market_value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else Decimal("0")

            total_cost += cost
            total_market_value += market_value

            holdings_breakdown.append({
                "symbol": holding.symbol,
                "name": holding.name,
                "asset_type": holding.asset_type,
                "quantity": str(holding.quantity),
                "avg_cost": str(holding.avg_cost),
                "current_price": str(current_price) if current_price else None,
                "cost": str(cost),
                "market_value": str(market_value),
                "pnl": str(pnl),
                "pnl_pct": str(pnl_pct.quantize(Decimal("0.01"))),
                "account": holding.account_name,
                "currency": holding.currency,
            })

        # 计算分红收入
        for tx in transactions:
            if tx.transaction_type == "dividend":
                dividend_income += tx.amount

        # 计算总盈亏和盈亏率
        total_pnl = total_market_value - total_cost
        total_pnl_pct = (
            (total_pnl / total_cost * 100) if total_cost > 0 else Decimal("0")
        )

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_cost": str(total_cost),
                "total_market_value": str(total_market_value),
                "total_pnl": str(total_pnl),
                "total_pnl_pct": str(total_pnl_pct.quantize(Decimal("0.01"))),
                "dividend_income": str(dividend_income),
                "holdings_count": len(holdings),
            },
            "holdings": holdings_breakdown,
        }

    async def generate_expense_summary_report(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成支出汇总报表"""
        # 查询期间内的支出
        stmt = select(Expense).where(
            and_(
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
            )
        )
        if category:
            stmt = stmt.where(Expense.category == category)

        result = await db.execute(stmt)
        expenses = list(result.scalars().all())

        # 计算总支出
        total_amount = sum(exp.amount for exp in expenses)

        # 按分类汇总
        category_breakdown = {}
        for exp in expenses:
            cat = exp.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {
                    "count": 0,
                    "amount": Decimal("0"),
                }
            category_breakdown[cat]["count"] += 1
            category_breakdown[cat]["amount"] += exp.amount

        # 转换为列表并排序
        category_list = [
            {
                "category": cat,
                "count": data["count"],
                "amount": str(data["amount"]),
                "percentage": str(
                    (data["amount"] / total_amount * 100).quantize(Decimal("0.01"))
                )
                if total_amount > 0
                else "0.00",
            }
            for cat, data in category_breakdown.items()
        ]
        category_list.sort(key=lambda x: Decimal(x["amount"]), reverse=True)

        # 计算日均支出
        days = (end_date - start_date).days + 1
        daily_avg = total_amount / days if days > 0 else Decimal("0")

        # 按日期汇总（用于趋势图）
        daily_breakdown = {}
        for exp in expenses:
            day = exp.expense_date.isoformat()
            if day not in daily_breakdown:
                daily_breakdown[day] = Decimal("0")
            daily_breakdown[day] += exp.amount

        daily_trend = [
            {"date": day, "amount": str(amount)}
            for day, amount in sorted(daily_breakdown.items())
        ]

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_amount": str(total_amount),
                "expense_count": len(expenses),
                "daily_avg": str(daily_avg.quantize(Decimal("0.01"))),
                "category_count": len(category_breakdown),
            },
            "category_breakdown": category_list,
            "daily_trend": daily_trend,
        }

    async def generate_account_snapshot_report(
        self,
        db: AsyncSession,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """生成账户快照报表"""
        if not as_of_date:
            as_of_date = date.today()

        # 获取所有活跃账户
        stmt = select(Account).where(Account.is_active == True)
        result = await db.execute(stmt)
        accounts = list(result.scalars().all())

        # 获取所有持仓（用于计算市值）
        holdings_stmt = select(Holding).where(Holding.is_active == True)
        holdings_result = await db.execute(holdings_stmt)
        holdings = list(holdings_result.scalars().all())

        # 按账户组织持仓
        holdings_by_account = {}
        for holding in holdings:
            account_id = holding.account_id
            if account_id not in holdings_by_account:
                holdings_by_account[account_id] = []
            holdings_by_account[account_id].append(holding)

        # 构建账户列表
        accounts_list = []
        total_balance = Decimal("0")
        total_holdings_value = Decimal("0")
        total_net_worth = Decimal("0")

        for account in accounts:
            balance = account.balance or Decimal("0")

            # 计算持仓市值
            account_holdings = holdings_by_account.get(account.id, [])
            holdings_value = Decimal("0")
            for holding in account_holdings:
                if holding.current_value:
                    holdings_value += holding.current_value

            net_worth = balance + holdings_value

            # 汇率转换
            rate = EXCHANGE_RATES.get(account.currency, Decimal("1.0"))
            balance_cny = balance * rate
            holdings_value_cny = holdings_value * rate
            net_worth_cny = net_worth * rate

            total_balance += balance_cny
            total_holdings_value += holdings_value_cny
            total_net_worth += net_worth_cny

            accounts_list.append({
                "id": account.id,
                "name": account.name,
                "type": account.account_type,
                "institution": account.institution,
                "balance": str(balance),
                "holdings_value": str(holdings_value),
                "net_worth": str(net_worth),
                "currency": account.currency,
                "balance_cny": str(balance_cny),
                "holdings_value_cny": str(holdings_value_cny),
                "net_worth_cny": str(net_worth_cny),
            })

        # 构建持仓列表
        holdings_list = []
        for holding in holdings:
            market_value = holding.current_value or Decimal("0")
            cost = holding.total_cost or Decimal("0")
            pnl = market_value - cost

            holdings_list.append({
                "symbol": holding.symbol,
                "name": holding.name,
                "asset_type": holding.asset_type,
                "quantity": str(holding.quantity),
                "avg_cost": str(holding.avg_cost),
                "current_price": str(holding.current_price) if holding.current_price else None,
                "market_value": str(market_value),
                "cost": str(cost),
                "pnl": str(pnl),
                "account_id": holding.account_id,
                "currency": holding.currency,
            })

        return {
            "as_of_date": as_of_date.isoformat(),
            "summary": {
                "total_balance": str(total_balance),
                "total_holdings_value": str(total_holdings_value),
                "total_net_worth": str(total_net_worth),
                "accounts_count": len(accounts),
                "holdings_count": len(holdings),
            },
            "accounts": accounts_list,
            "holdings": holdings_list,
        }
