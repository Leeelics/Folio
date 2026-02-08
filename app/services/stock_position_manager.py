"""股票持仓管理服务 - 管理持仓和计算盈亏"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockPosition, StockWatchlist
from app.services.stock_client import Market, StockClient

logger = logging.getLogger(__name__)

# 汇率配置（后续可从配置文件或API获取）
EXCHANGE_RATES = {
    "CNY": Decimal("1.0"),
    "HKD": Decimal("0.92"),  # 港币 -> 人民币
    "USD": Decimal("7.2"),   # 美元 -> 人民币
}

# 市场对应货币
MARKET_CURRENCY = {
    "A股": "CNY",
    "港股": "HKD",
    "美股": "USD",
}


class StockPositionManager:
    """股票持仓管理服务 - 管理持仓、计算盈亏"""

    def __init__(self) -> None:
        self.stock_client = StockClient()

    def _get_currency_for_market(self, market: str) -> str:
        """获取市场对应的货币"""
        return MARKET_CURRENCY.get(market, "CNY")

    def _convert_to_cny(self, amount: Decimal, currency: str) -> Decimal:
        """将金额转换为人民币"""
        rate = EXCHANGE_RATES.get(currency, Decimal("1.0"))
        return amount * rate

    # ==================== 持仓管理 ====================

    async def add_position(
        self,
        db: AsyncSession,
        symbol: str,
        market: str,
        quantity: int,
        cost_price: Decimal,
        account_name: str = "默认账户",
        name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> StockPosition:
        """添加新持仓"""
        currency = self._get_currency_for_market(market)

        # 如果没有提供名称，尝试从API获取
        if not name:
            try:
                market_enum = Market(market)
                quote = await self.stock_client.fetch_realtime_quote(symbol, market_enum)
                if quote:
                    name = quote.name
            except Exception as e:
                logger.warning(f"获取股票名称失败: {e}")

        position = StockPosition(
            symbol=symbol,
            market=market,
            name=name,
            quantity=quantity,
            cost_price=cost_price,
            account_name=account_name,
            currency=currency,
            notes=notes,
        )
        db.add(position)
        await db.commit()
        await db.refresh(position)
        logger.info(f"添加持仓: {symbol} ({market}) x {quantity} @ {cost_price}")
        return position

    async def update_position(
        self,
        db: AsyncSession,
        position_id: int,
        quantity: Optional[int] = None,
        cost_price: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> Optional[StockPosition]:
        """更新持仓"""
        stmt = select(StockPosition).where(StockPosition.id == position_id)
        result = await db.execute(stmt)
        position = result.scalar_one_or_none()

        if not position:
            logger.warning(f"持仓 {position_id} 不存在")
            return None

        if quantity is not None:
            position.quantity = quantity
        if cost_price is not None:
            position.cost_price = cost_price
        if notes is not None:
            position.notes = notes

        await db.commit()
        await db.refresh(position)
        logger.info(f"更新持仓 {position_id}: quantity={quantity}, cost_price={cost_price}")
        return position

    async def delete_position(self, db: AsyncSession, position_id: int) -> bool:
        """删除持仓（清仓）"""
        stmt = delete(StockPosition).where(StockPosition.id == position_id)
        result = await db.execute(stmt)
        await db.commit()
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"删除持仓 {position_id}")
        return deleted

    async def get_position(self, db: AsyncSession, position_id: int) -> Optional[StockPosition]:
        """获取单个持仓"""
        stmt = select(StockPosition).where(StockPosition.id == position_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_positions(self, db: AsyncSession) -> List[StockPosition]:
        """获取所有持仓"""
        stmt = select(StockPosition).order_by(StockPosition.market, StockPosition.symbol)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_positions_by_market(
        self,
        db: AsyncSession,
        market: str
    ) -> List[StockPosition]:
        """按市场获取持仓"""
        stmt = select(StockPosition).where(StockPosition.market == market)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ==================== 盈亏计算 ====================

    async def calculate_position_pnl(
        self,
        db: AsyncSession,
        position_id: int,
    ) -> Dict:
        """计算单个持仓的盈亏"""
        position = await self.get_position(db, position_id)
        if not position:
            return {"error": "持仓不存在"}

        try:
            market_enum = Market(position.market)
        except ValueError:
            return {"error": f"不支持的市场: {position.market}"}

        quote = await self.stock_client.fetch_realtime_quote(position.symbol, market_enum)

        if not quote:
            return {
                "position_id": position_id,
                "symbol": position.symbol,
                "market": position.market,
                "error": "无法获取当前价格",
            }

        current_price = quote.current_price
        cost_price = Decimal(str(position.cost_price))
        quantity = position.quantity

        current_value = current_price * quantity
        cost_value = cost_price * quantity
        pnl = current_value - cost_value
        pnl_percent = (pnl / cost_value * 100) if cost_value > 0 else Decimal("0")

        # 转换为人民币
        currency = position.currency or self._get_currency_for_market(position.market)
        current_value_cny = self._convert_to_cny(current_value, currency)
        cost_value_cny = self._convert_to_cny(cost_value, currency)
        pnl_cny = self._convert_to_cny(pnl, currency)

        return {
            "position_id": position_id,
            "symbol": position.symbol,
            "name": quote.name,
            "market": position.market,
            "quantity": quantity,
            "cost_price": float(cost_price),
            "current_price": float(current_price),
            "cost_value": float(cost_value),
            "current_value": float(current_value),
            "pnl": float(pnl),
            "pnl_percent": float(pnl_percent),
            "currency": currency,
            "cost_value_cny": float(cost_value_cny),
            "current_value_cny": float(current_value_cny),
            "pnl_cny": float(pnl_cny),
            "change_today": float(quote.change_percent),
            "account_name": position.account_name,
        }

    async def calculate_total_stock_value(self, db: AsyncSession) -> Dict:
        """计算所有股票持仓的总市值和盈亏"""
        positions = await self.get_all_positions(db)

        total_cost_cny = Decimal("0")
        total_current_cny = Decimal("0")
        by_market: Dict[str, Dict] = {}
        position_details = []

        for position in positions:
            try:
                market_enum = Market(position.market)
            except ValueError:
                continue

            quote = await self.stock_client.fetch_realtime_quote(position.symbol, market_enum)

            if not quote:
                continue

            current_price = quote.current_price
            cost_price = Decimal(str(position.cost_price))
            quantity = position.quantity

            cost_value = cost_price * quantity
            current_value = current_price * quantity
            pnl = current_value - cost_value

            currency = position.currency or self._get_currency_for_market(position.market)
            cost_cny = self._convert_to_cny(cost_value, currency)
            current_cny = self._convert_to_cny(current_value, currency)
            pnl_cny = self._convert_to_cny(pnl, currency)

            total_cost_cny += cost_cny
            total_current_cny += current_cny

            # 按市场分组
            if position.market not in by_market:
                by_market[position.market] = {
                    "cost_cny": Decimal("0"),
                    "current_cny": Decimal("0"),
                    "positions": [],
                }
            by_market[position.market]["cost_cny"] += cost_cny
            by_market[position.market]["current_cny"] += current_cny
            by_market[position.market]["positions"].append({
                "id": position.id,
                "symbol": position.symbol,
                "name": quote.name,
                "quantity": quantity,
                "current_price": float(current_price),
                "current_value_cny": float(current_cny),
                "pnl_cny": float(pnl_cny),
                "pnl_percent": float((pnl / cost_value * 100) if cost_value > 0 else 0),
            })

            position_details.append({
                "id": position.id,
                "symbol": position.symbol,
                "name": quote.name,
                "market": position.market,
                "quantity": quantity,
                "cost_price": float(cost_price),
                "current_price": float(current_price),
                "pnl_cny": float(pnl_cny),
                "pnl_percent": float((pnl / cost_value * 100) if cost_value > 0 else 0),
            })

        total_pnl_cny = total_current_cny - total_cost_cny
        total_pnl_percent = (total_pnl_cny / total_cost_cny * 100) if total_cost_cny > 0 else Decimal("0")

        return {
            "total_cost_cny": float(total_cost_cny),
            "total_current_cny": float(total_current_cny),
            "total_pnl_cny": float(total_pnl_cny),
            "total_pnl_percent": float(total_pnl_percent),
            "position_count": len(positions),
            "by_market": {
                market: {
                    "cost_cny": float(data["cost_cny"]),
                    "current_cny": float(data["current_cny"]),
                    "pnl_cny": float(data["current_cny"] - data["cost_cny"]),
                    "position_count": len(data["positions"]),
                    "positions": data["positions"],
                }
                for market, data in by_market.items()
            },
            "positions": position_details,
            "timestamp": datetime.now().isoformat(),
        }

    # ==================== 自选股管理 ====================

    async def add_to_watchlist(
        self,
        db: AsyncSession,
        symbol: str,
        market: str,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        alert_price_high: Optional[Decimal] = None,
        alert_price_low: Optional[Decimal] = None,
    ) -> StockWatchlist:
        """添加自选股"""
        # 检查是否已存在
        stmt = select(StockWatchlist).where(
            StockWatchlist.symbol == symbol,
            StockWatchlist.market == market
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # 更新现有记录
            existing.is_active = True
            if notes:
                existing.notes = notes
            if alert_price_high:
                existing.alert_price_high = alert_price_high
            if alert_price_low:
                existing.alert_price_low = alert_price_low
            await db.commit()
            await db.refresh(existing)
            return existing

        # 获取股票名称
        if not name:
            try:
                market_enum = Market(market)
                quote = await self.stock_client.fetch_realtime_quote(symbol, market_enum)
                if quote:
                    name = quote.name
            except Exception:
                pass

        watchlist = StockWatchlist(
            symbol=symbol,
            market=market,
            name=name,
            notes=notes,
            alert_price_high=alert_price_high,
            alert_price_low=alert_price_low,
        )
        db.add(watchlist)
        await db.commit()
        await db.refresh(watchlist)
        return watchlist

    async def remove_from_watchlist(self, db: AsyncSession, watchlist_id: int) -> bool:
        """从自选股移除"""
        stmt = delete(StockWatchlist).where(StockWatchlist.id == watchlist_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    async def get_watchlist(self, db: AsyncSession) -> List[Dict]:
        """获取自选股列表（带实时行情）"""
        stmt = select(StockWatchlist).where(StockWatchlist.is_active == True).order_by(
            StockWatchlist.market, StockWatchlist.symbol
        )
        result = await db.execute(stmt)
        watchlist = list(result.scalars().all())

        results = []
        for item in watchlist:
            try:
                market_enum = Market(item.market)
                quote = await self.stock_client.fetch_realtime_quote(item.symbol, market_enum)

                results.append({
                    "id": item.id,
                    "symbol": item.symbol,
                    "name": quote.name if quote else item.name,
                    "market": item.market,
                    "current_price": float(quote.current_price) if quote else None,
                    "change": float(quote.change) if quote else None,
                    "change_percent": float(quote.change_percent) if quote else None,
                    "volume": quote.volume if quote else None,
                    "notes": item.notes,
                    "alert_price_high": float(item.alert_price_high) if item.alert_price_high else None,
                    "alert_price_low": float(item.alert_price_low) if item.alert_price_low else None,
                })
            except Exception as e:
                logger.error(f"获取自选股 {item.symbol} 行情失败: {e}")
                results.append({
                    "id": item.id,
                    "symbol": item.symbol,
                    "name": item.name,
                    "market": item.market,
                    "error": str(e),
                })

        return results
