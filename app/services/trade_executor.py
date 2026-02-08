from __future__ import annotations

import logging
from decimal import Decimal
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import Trade
from app.services.okx_client import OkxClient
from app.services.strategy_engine import OrderInstruction

logger = logging.getLogger(__name__)


class TradeExecutor:
    """交易执行器 - 接收策略指令，调用 OKX 下单并记录到数据库。"""

    def __init__(self) -> None:
        self.okx_client = OkxClient()

    async def execute_instructions(
        self,
        db: AsyncSession,
        instructions: List[OrderInstruction],
        dry_run: bool = False,
    ) -> List[Trade]:
        trades: List[Trade] = []

        for instruction in instructions:
            trade = Trade(
                strategy_name=instruction.strategy_name,
                symbol=instruction.symbol,
                side=instruction.side,
                order_type=instruction.order_type,
                amount=instruction.amount,
                price=instruction.price,
                status="created",
                metadata=instruction.metadata or {},
            )
            db.add(trade)
            await db.flush()

            if dry_run:
                trade.status = "simulated"
                trades.append(trade)
                continue

            try:
                order = await self.okx_client.create_order(
                    symbol=instruction.symbol,
                    side=instruction.side,
                    order_type=instruction.order_type,
                    amount=Decimal(instruction.amount),
                    price=instruction.price,
                )

                trade.status = order.get("status", "submitted")
                trade.exchange_order_id = str(order.get("id") or "")
                trade.metadata = {
                    **(trade.metadata or {}),
                    "raw_order": order,
                }
            except Exception as exc:
                logger.error("Failed to execute order for trade %s: %s", trade.id, exc)
                trade.status = "failed"
                trade.error_message = str(exc)

            trades.append(trade)

        await db.commit()
        return trades

