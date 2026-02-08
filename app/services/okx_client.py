from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OkxClient:
    """OKX 客户端封装 - 统一管理账户、行情与下单接口。

    原有 AssetManager 中的 OKX 余额获取逻辑将逐步迁移到这里，
    方便复用与统一的错误处理 / 限频控制。
    """

    def __init__(self) -> None:
        self._exchange: Optional[ccxt.okx] = None

    async def _get_exchange(self) -> Optional[ccxt.okx]:
        if self._exchange is None:
            if not settings.okx_api_key:
                logger.warning("OKX API credentials not configured")
                return None

            self._exchange = ccxt.okx(
                {
                    "apiKey": settings.okx_api_key,
                    "secret": settings.okx_secret_key,
                    "password": settings.okx_passphrase,
                    "enableRateLimit": True,
                }
            )

        return self._exchange

    async def close(self) -> None:
        if self._exchange is not None:
            try:
                await self._exchange.close()
            except Exception as exc:  # pragma: no cover - best-effort cleanup
                logger.debug("Failed to close OKX client: %s", exc)
            finally:
                self._exchange = None

    async def fetch_balance(self) -> Dict[str, Decimal]:
        """获取 OKX 账户余额，返回 {currency: Decimal}。"""
        exchange = await self._get_exchange()
        if not exchange:
            return {}

        try:
            balance = await exchange.fetch_balance()
            total_balance: Dict[str, Decimal] = {}
            for currency, amount_info in balance.get("total", {}).items():
                try:
                    value = Decimal(str(amount_info or "0"))
                except Exception:
                    continue
                if value > 0:
                    total_balance[currency] = value

            return total_balance
        except Exception as exc:
            logger.error("Failed to fetch OKX balance: %s", exc)
            return {}

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
    ) -> List[List[Any]]:
        """获取 K 线数据，用于策略信号计算。"""
        exchange = await self._get_exchange()
        if not exchange:
            return []
        try:
            candles = await exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit,
            )
            return candles
        except Exception as exc:
            logger.error("Failed to fetch OHLCV for %s: %s", symbol, exc)
            return []

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建订单。默认使用现货交易，具体细节由 params 控制。"""
        exchange = await self._get_exchange()
        if not exchange:
            raise RuntimeError("OKX client not configured")

        params = params or {}
        try:
            if order_type == "market":
                order = await exchange.create_market_order(
                    symbol,
                    side,
                    float(amount),
                    params=params,
                )
            else:
                if price is None:
                    raise ValueError("Limit order requires price")
                order = await exchange.create_limit_order(
                    symbol,
                    side,
                    float(amount),
                    float(price),
                    params=params,
                )
            return order
        except Exception as exc:
            logger.error("Failed to create OKX order: %s", exc)
            raise

