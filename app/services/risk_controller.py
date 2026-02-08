import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.schemas import Asset, Transaction
from app.models.stock import StockPosition
from app.services.stock_client import Market, StockClient

logger = logging.getLogger(__name__)
settings = get_settings()

# 汇率配置
EXCHANGE_RATES = {
    "CNY": Decimal("1.0"),
    "HKD": Decimal("0.92"),
    "USD": Decimal("7.2"),
    "USDT": Decimal("7.2"),
}


class RiskController:
    """风险控制逻辑 - 计算资产状况和婚礼金安全水位"""

    def __init__(self):
        self.wedding_budget = Decimal(str(settings.wedding_budget))
        self.wedding_date = datetime.strptime(settings.wedding_date, "%Y-%m-%d")
        self.risk_margin_threshold = settings.risk_margin_threshold
        self.stock_client = StockClient()

    async def calculate_total_assets(self, db: AsyncSession) -> Decimal:
        """计算当前总资产（CNY），包含股票持仓"""
        stmt = select(Asset)
        result = await db.execute(stmt)
        assets = result.scalars().all()

        total = Decimal('0')
        for asset in assets:
            rate = EXCHANGE_RATES.get(asset.currency, Decimal("1.0"))
            total += asset.balance * rate

        # 加上股票持仓市值
        stock_value = await self._calculate_stock_value(db)
        total += stock_value

        return total

    async def _calculate_stock_value(self, db: AsyncSession) -> Decimal:
        """计算股票持仓总市值（CNY）"""
        stmt = select(StockPosition)
        result = await db.execute(stmt)
        positions = list(result.scalars().all())

        total_cny = Decimal("0")

        for position in positions:
            try:
                market_enum = Market(position.market)
                quote = await self.stock_client.fetch_realtime_quote(position.symbol, market_enum)

                if quote:
                    current_value = quote.current_price * position.quantity
                else:
                    current_value = Decimal(str(position.cost_price)) * position.quantity

                currency = position.currency or "CNY"
                rate = EXCHANGE_RATES.get(currency, Decimal("1.0"))
                total_cny += current_value * rate
            except Exception as e:
                logger.warning(f"获取股票 {position.symbol} 市值失败: {e}")
                # 使用成本价作为备选
                cost_value = Decimal(str(position.cost_price)) * position.quantity
                currency = position.currency or "CNY"
                rate = EXCHANGE_RATES.get(currency, Decimal("1.0"))
                total_cny += cost_value * rate

        return total_cny

    async def calculate_asset_allocation(self, db: AsyncSession) -> Dict[str, Dict]:
        """计算各资产占比，包含股票持仓"""
        stmt = select(Asset)
        result = await db.execute(stmt)
        assets = result.scalars().all()

        # 按账户类型分组
        allocation = {}
        total_value = Decimal('0')

        for asset in assets:
            rate = EXCHANGE_RATES.get(asset.currency, Decimal("1.0"))
            value = asset.balance * rate

            account_type = asset.account_type
            if account_type not in allocation:
                allocation[account_type] = {
                    "value": Decimal('0'),
                    "accounts": []
                }

            allocation[account_type]["value"] += value
            allocation[account_type]["accounts"].append({
                "name": asset.account_name,
                "balance": float(asset.balance),
                "currency": asset.currency
            })
            total_value += value

        # 添加股票持仓
        stmt = select(StockPosition)
        result = await db.execute(stmt)
        positions = list(result.scalars().all())

        for position in positions:
            try:
                market_enum = Market(position.market)
                quote = await self.stock_client.fetch_realtime_quote(position.symbol, market_enum)

                if quote:
                    current_value = quote.current_price * position.quantity
                    stock_name = quote.name
                else:
                    current_value = Decimal(str(position.cost_price)) * position.quantity
                    stock_name = position.name or position.symbol

                currency = position.currency or "CNY"
                rate = EXCHANGE_RATES.get(currency, Decimal("1.0"))
                value_cny = current_value * rate

                # 按市场分类（A股/港股/美股）
                market_type = position.market
                if market_type not in allocation:
                    allocation[market_type] = {
                        "value": Decimal('0'),
                        "accounts": []
                    }

                allocation[market_type]["value"] += value_cny
                allocation[market_type]["accounts"].append({
                    "name": f"{stock_name} ({position.symbol})",
                    "balance": float(current_value),
                    "currency": currency,
                    "quantity": position.quantity,
                })
                total_value += value_cny
            except Exception as e:
                logger.warning(f"获取股票 {position.symbol} 配置失败: {e}")

        # 计算百分比
        for account_type in allocation:
            if total_value > 0:
                allocation[account_type]["percentage"] = float(
                    (allocation[account_type]["value"] / total_value) * 100
                )
            else:
                allocation[account_type]["percentage"] = 0.0
            allocation[account_type]["value"] = float(allocation[account_type]["value"])

        return allocation

    async def calculate_wedding_expense_total(self, db: AsyncSession) -> Decimal:
        """计算已支出的婚礼费用"""
        stmt = select(func.sum(Transaction.amount)).where(
            Transaction.is_wedding_expense == True,
            Transaction.transaction_type == "expense"
        )
        result = await db.execute(stmt)
        total = result.scalar()
        return total if total else Decimal('0')

    async def calculate_margin_of_safety(self, db: AsyncSession) -> Dict:
        """计算婚礼金的安全水位（Margin of Safety）"""
        # 当前总资产
        total_assets = await self.calculate_total_assets(db)

        # 已支出婚礼费用
        spent = await self.calculate_wedding_expense_total(db)

        # 剩余需要的婚礼预算
        remaining_budget = self.wedding_budget - spent

        # 安全水位 = (总资产 - 剩余婚礼预算) / 总资产
        if total_assets > 0:
            margin = (total_assets - remaining_budget) / total_assets
        else:
            margin = Decimal('0')

        # 可投资金额 = 总资产 - 剩余婚礼预算 - 安全缓冲
        safety_buffer = remaining_budget * Decimal(str(self.risk_margin_threshold))
        investable_amount = total_assets - remaining_budget - safety_buffer

        # 距离婚礼天数
        days_until_wedding = (self.wedding_date - datetime.now()).days

        return {
            "total_assets": float(total_assets),
            "wedding_budget": float(self.wedding_budget),
            "spent": float(spent),
            "remaining_budget": float(remaining_budget),
            "margin_of_safety": float(margin),
            "margin_percentage": float(margin * 100),
            "investable_amount": float(max(investable_amount, 0)),
            "safety_buffer": float(safety_buffer),
            "days_until_wedding": days_until_wedding,
            "risk_level": self._assess_risk_level(margin)
        }

    def _assess_risk_level(self, margin: Decimal) -> str:
        """评估风险等级"""
        if margin < Decimal('0'):
            return "CRITICAL"  # 资产不足以覆盖婚礼预算
        elif margin < Decimal('0.1'):
            return "HIGH"  # 安全边际 < 10%
        elif margin < Decimal('0.2'):
            return "MEDIUM"  # 安全边际 10-20%
        else:
            return "LOW"  # 安全边际 > 20%

    async def get_risk_report(self, db: AsyncSession) -> Dict:
        """生成完整的风险报告"""
        total_assets = await self.calculate_total_assets(db)
        allocation = await self.calculate_asset_allocation(db)
        margin_info = await self.calculate_margin_of_safety(db)

        return {
            "summary": {
                "total_assets": float(total_assets),
                "asset_count": len(allocation)
            },
            "allocation": allocation,
            "wedding_finance": margin_info,
            "recommendations": self._generate_recommendations(margin_info, allocation)
        }

    def _generate_recommendations(
        self,
        margin_info: Dict,
        allocation: Dict
    ) -> List[str]:
        """生成投资建议"""
        recommendations = []

        risk_level = margin_info["risk_level"]

        if risk_level == "CRITICAL":
            recommendations.append("⚠️ 警告：当前资产不足以覆盖婚礼预算，建议立即调整支出计划")
        elif risk_level == "HIGH":
            recommendations.append("⚠️ 风险较高：建议减少高风险投资，保持流动性")

        if margin_info["investable_amount"] > 0:
            recommendations.append(
                f"💰 可投资金额：¥{margin_info['investable_amount']:,.2f}"
            )
        else:
            recommendations.append("🔒 建议暂停新增投资，保留现金储备")

        # 资产配置建议
        if "OKX" in allocation:
            crypto_percentage = allocation["OKX"]["percentage"]
            if crypto_percentage > 30:
                recommendations.append(
                    f"📊 加密货币占比 {crypto_percentage:.1f}%，建议适当降低风险敞口"
                )

        return recommendations
