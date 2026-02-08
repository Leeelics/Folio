"""
汇率服务
支持多币种实时汇率获取和缓存
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.brokerage import ExchangeRate

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """
    汇率服务

    支持:
    - 多币种汇率获取和缓存
    - 小时级缓存策略
    - 支持CNY、HKD、USD、XAU、BTC、ETH等
    """

    def __init__(self):
        self.cache_ttl = timedelta(hours=1)  # 1小时缓存
        self._cache: Dict[str, tuple[Decimal, datetime]] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # 基础汇率配置（作为fallback）
        self.base_rates = {
            ("CNY", "CNY"): Decimal("1.0"),
            ("HKD", "CNY"): Decimal("0.92"),
            ("USD", "CNY"): Decimal("7.2"),
            ("USDT", "CNY"): Decimal("7.2"),
            ("BTC", "CNY"): Decimal("500000.0"),  # 需要实时更新
            ("ETH", "CNY"): Decimal("25000.0"),
            ("XAU", "CNY"): Decimal("600.0"),  # 黄金元/克
        }

    async def get_rate(
        self, db: AsyncSession, from_currency: str, to_currency: str, use_cache: bool = True
    ) -> Decimal:
        """
        获取汇率

        优先级:
        1. 内存缓存（1小时内）
        2. 数据库缓存（24小时内）
        3. 实时API获取
        4. 基础汇率配置（fallback）

        Args:
            from_currency: 源币种
            to_currency: 目标币种
            use_cache: 是否使用缓存

        Returns:
            Decimal: 汇率（from_currency -> to_currency）
        """
        # 标准化币种代码
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # 同币种直接返回1.0
        if from_currency == to_currency:
            return Decimal("1.0")

        cache_key = f"{from_currency}_{to_currency}"

        # 1. 检查内存缓存
        if use_cache and cache_key in self._cache:
            rate, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                return rate

        # 2. 检查数据库缓存
        if use_cache:
            db_rate = await self._get_rate_from_db(db, from_currency, to_currency)
            if db_rate:
                # 更新内存缓存
                self._cache[cache_key] = (db_rate, datetime.now())
                return db_rate

        # 3. 实时获取
        try:
            live_rate = await self._fetch_rate(from_currency, to_currency)
            if live_rate:
                # 保存到数据库和内存缓存
                await self._save_rate(db, from_currency, to_currency, live_rate)
                self._cache[cache_key] = (live_rate, datetime.now())
                return live_rate
        except Exception as e:
            logger.warning(f"获取实时汇率失败 {from_currency}->{to_currency}: {e}")

        # 4. 使用基础汇率配置（fallback）
        fallback_rate = self._get_fallback_rate(from_currency, to_currency)
        if fallback_rate:
            logger.info(f"使用基础汇率 {from_currency}->{to_currency}: {fallback_rate}")
            return fallback_rate

        # 无法获取汇率，返回1.0作为最后fallback
        logger.error(f"无法获取汇率 {from_currency}->{to_currency}，使用1.0")
        return Decimal("1.0")

    async def convert(
        self, db: AsyncSession, amount: Decimal, from_currency: str, to_currency: str
    ) -> Decimal:
        """
        货币转换

        Args:
            amount: 金额
            from_currency: 源币种
            to_currency: 目标币种

        Returns:
            Decimal: 转换后的金额
        """
        rate = await self.get_rate(db, from_currency, to_currency)
        return amount * rate

    async def _get_rate_from_db(
        self, db: AsyncSession, from_currency: str, to_currency: str
    ) -> Optional[Decimal]:
        """从数据库获取最近24小时内的汇率"""
        cutoff_time = datetime.now() - timedelta(hours=24)

        stmt = (
            select(ExchangeRate)
            .where(
                ExchangeRate.from_currency == from_currency,
                ExchangeRate.to_currency == to_currency,
                ExchangeRate.recorded_at >= cutoff_time,
            )
            .order_by(desc(ExchangeRate.recorded_at))
            .limit(1)
        )

        result = await db.execute(stmt)
        rate_record = result.scalar_one_or_none()

        if rate_record:
            return rate_record.rate
        return None

    async def _fetch_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """
        从API获取实时汇率

        支持的数据源:
        - Yahoo Finance (主要)
        - Exchange Rate API (备用)
        - 特殊币种（黄金、虚拟币）
        """
        # 策略1: 如果涉及CNY，使用Yahoo Finance
        if from_currency == "CNY" or to_currency == "CNY":
            rate = await self._fetch_from_yahoo(from_currency, to_currency)
            if rate:
                return rate

        # 策略2: 加密货币使用OKX或其他API
        if from_currency in ["BTC", "ETH", "USDT"] or to_currency in ["BTC", "ETH", "USDT"]:
            rate = await self._fetch_crypto_rate(from_currency, to_currency)
            if rate:
                return rate

        # 策略3: 使用通用API
        rate = await self._fetch_from_exchangerate_api(from_currency, to_currency)
        if rate:
            return rate

        return None

    async def _fetch_from_yahoo(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """从Yahoo Finance获取汇率"""
        try:
            # 构建货币对代码
            if from_currency == "CNY":
                symbol = f"{to_currency}CNY=X"
            elif to_currency == "CNY":
                symbol = f"CNY{from_currency}=X"
            else:
                symbol = f"{from_currency}{to_currency}=X"

            # Yahoo Finance API (简化版)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

            response = await self.http_client.get(url)
            if response.status_code == 200:
                data = response.json()
                if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                    meta = data["chart"]["result"][0]["meta"]
                    rate = Decimal(str(meta.get("regularMarketPrice", 0)))
                    if rate > 0:
                        return rate

        except Exception as e:
            logger.debug(f"Yahoo Finance API失败: {e}")

        return None

    async def _fetch_crypto_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """获取加密货币汇率"""
        try:
            # 使用CoinGecko API（免费）
            url = "https://api.coingecko.com/api/v3/simple/price"

            # 映射币种代码
            crypto_map = {"BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether"}

            if from_currency in crypto_map:
                crypto_id = crypto_map[from_currency]
                vs_currency = to_currency.lower()

                params = {"ids": crypto_id, "vs_currencies": vs_currency}

                response = await self.http_client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    price = data.get(crypto_id, {}).get(vs_currency)
                    if price:
                        return Decimal(str(price))

        except Exception as e:
            logger.debug(f"加密货币API失败: {e}")

        return None

    async def _fetch_from_exchangerate_api(
        self, from_currency: str, to_currency: str
    ) -> Optional[Decimal]:
        """使用Exchange Rate API获取汇率"""
        try:
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"

            response = await self.http_client.get(url)
            if response.status_code == 200:
                data = response.json()
                rate = data.get("rates", {}).get(to_currency)
                if rate:
                    return Decimal(str(rate))

        except Exception as e:
            logger.debug(f"Exchange Rate API失败: {e}")

        return None

    async def _save_rate(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        source: str = "api",
    ):
        """保存汇率到数据库"""
        exchange_rate = ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            source=source,
            recorded_at=datetime.now(),
        )
        db.add(exchange_rate)
        await db.commit()

    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """从基础配置获取汇率"""
        # 直接查找
        key = (from_currency, to_currency)
        if key in self.base_rates:
            return self.base_rates[key]

        # 反向查找
        reverse_key = (to_currency, from_currency)
        if reverse_key in self.base_rates:
            return Decimal("1.0") / self.base_rates[reverse_key]

        return None

    async def get_all_rates_for_base(
        self, db: AsyncSession, base_currency: str = "CNY"
    ) -> Dict[str, Decimal]:
        """
        获取所有支持的币种对某基准币的汇率

        用于资产总览页面的统一折算
        """
        base_currency = base_currency.upper()
        supported_currencies = ["CNY", "HKD", "USD", "USDT", "BTC", "ETH", "XAU"]

        rates = {base_currency: Decimal("1.0")}

        for currency in supported_currencies:
            if currency != base_currency:
                rate = await self.get_rate(db, currency, base_currency)
                rates[currency] = rate

        return rates

    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()
