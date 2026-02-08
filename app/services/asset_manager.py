import logging
from decimal import Decimal
from typing import Dict, List, Optional

import ccxt.async_support as ccxt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.schemas import Asset
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


class AssetManager:
    """资产管理服务 - 集成 CCXT 获取 OKX 实时余额，以及股票持仓"""

    def __init__(self):
        self.okx_exchange: Optional[ccxt.okx] = None
        self.stock_client = StockClient()

    async def _init_okx(self):
        """初始化 OKX 交易所连接"""
        if not self.okx_exchange and settings.okx_api_key:
            self.okx_exchange = ccxt.okx({
                'apiKey': settings.okx_api_key,
                'secret': settings.okx_secret_key,
                'password': settings.okx_passphrase,
                'enableRateLimit': True,
            })
        return self.okx_exchange

    async def fetch_okx_balance(self) -> Dict[str, float]:
        """从 OKX 获取实时余额"""
        try:
            exchange = await self._init_okx()
            if not exchange:
                logger.warning("OKX API credentials not configured")
                return {}

            balance = await exchange.fetch_balance()

            # 提取总余额（包括现货、合约等）
            total_balance = {}
            for currency, amount_info in balance['total'].items():
                if amount_info and float(amount_info) > 0:
                    total_balance[currency] = float(amount_info)

            return total_balance
        except Exception as e:
            logger.error(f"Failed to fetch OKX balance: {e}")
            return {}
        finally:
            if self.okx_exchange:
                await self.okx_exchange.close()

    async def sync_okx_to_db(self, db: AsyncSession) -> List[Asset]:
        """同步 OKX 余额到数据库"""
        balances = await self.fetch_okx_balance()
        updated_assets = []

        for currency, amount in balances.items():
            # 查找或创建资产记录
            stmt = select(Asset).where(
                Asset.account_type == "OKX",
                Asset.currency == currency
            )
            result = await db.execute(stmt)
            asset = result.scalar_one_or_none()

            if asset:
                # 更新现有记录
                asset.balance = Decimal(str(amount))
            else:
                # 创建新记录
                asset = Asset(
                    account_type="OKX",
                    account_name=f"OKX {currency}",
                    balance=Decimal(str(amount)),
                    currency=currency
                )
                db.add(asset)

            updated_assets.append(asset)

        await db.commit()
        return updated_assets

    async def get_all_assets(self, db: AsyncSession) -> List[Asset]:
        """获取所有资产"""
        stmt = select(Asset)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_assets_by_type(self, db: AsyncSession, account_type: str) -> List[Asset]:
        """按类型获取资产"""
        stmt = select(Asset).where(Asset.account_type == account_type)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def calculate_total_assets(self, db: AsyncSession) -> Decimal:
        """计算总资产（CNY），包含股票持仓"""
        assets = await self.get_all_assets(db)
        total = Decimal('0')

        for asset in assets:
            rate = EXCHANGE_RATES.get(asset.currency, Decimal("1.0"))
            total += asset.balance * rate

        # 加上股票持仓市值
        stock_value = await self.calculate_stock_value(db)
        total += stock_value

        return total

    async def calculate_stock_value(self, db: AsyncSession) -> Decimal:
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

    async def get_asset_distribution(self, db: AsyncSession) -> Dict[str, float]:
        """获取资产分布（用于饼图），包含股票持仓"""
        assets = await self.get_all_assets(db)
        distribution = {}

        for asset in assets:
            account_type = asset.account_type
            rate = EXCHANGE_RATES.get(asset.currency, Decimal("1.0"))
            amount = float(asset.balance * rate)

            if account_type in distribution:
                distribution[account_type] += amount
            else:
                distribution[account_type] = amount

        # 添加股票持仓分布
        stmt = select(StockPosition)
        result = await db.execute(stmt)
        positions = list(result.scalars().all())

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
                amount = float(current_value * rate)

                # 按市场分类
                market_type = position.market  # A股/港股/美股
                if market_type in distribution:
                    distribution[market_type] += amount
                else:
                    distribution[market_type] = amount
            except Exception as e:
                logger.warning(f"获取股票 {position.symbol} 分布失败: {e}")

        return distribution
