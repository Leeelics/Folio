from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import StrategyConfig
from app.services.okx_client import OkxClient


@dataclass
class OrderInstruction:
    """策略生成的下单指令，不直接绑定具体交易所实现。"""

    strategy_name: str
    symbol: str
    side: str  # buy / sell
    order_type: str  # market / limit
    amount: Decimal
    price: Optional[Decimal] = None
    metadata: Optional[Dict] = None


class StrategyEngine:
    """策略引擎 - 根据配置与行情生成下单指令。

    这里实现一个非常简单的示例策略：
    - 策略名称：simple_dca
    - 行为：每次运行在指定交易对买入固定金额（定投）
    - 配置参数示例：
      {
        "symbol": "BTC/USDT",
        "quote_amount": 100.0,
        "timeframe": "1h"
      }
    """

    def __init__(self) -> None:
        self.okx_client = OkxClient()

    async def load_strategy_config(
        self,
        db: AsyncSession,
        name: str,
    ) -> Optional[StrategyConfig]:
        stmt = select(StrategyConfig).where(StrategyConfig.name == name)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def run_simple_dca(
        self,
        db: AsyncSession,
        strategy_name: str = "simple_dca",
    ) -> List[OrderInstruction]:
        """简单定投策略：每次运行买入固定金额的标的。"""
        config = await self.load_strategy_config(db, strategy_name)
        if not config or not config.is_enabled:
            return []

        params = config.params or {}
        symbol = params.get("symbol", "BTC/USDT")
        quote_amount = Decimal(str(params.get("quote_amount", "0")))
        if quote_amount <= 0:
            return []

        candles = await self.okx_client.fetch_ohlcv(symbol, timeframe=params.get("timeframe", "1h"), limit=1)
        if not candles:
            return []

        last_close_price = Decimal(str(candles[-1][4]))
        base_amount = (quote_amount / last_close_price).quantize(Decimal("0.000001"))

        return [
            OrderInstruction(
                strategy_name=strategy_name,
                symbol=symbol,
                side="buy",
                order_type="market",
                amount=base_amount,
                price=None,
                metadata={"last_close": float(last_close_price)},
            )
        ]

