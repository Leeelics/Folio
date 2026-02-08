"""股票数据客户端 - 封装 AkShare API，支持 A股/港股/美股"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


class StockDataError(RuntimeError):
    """Raised when stock data providers are unavailable or return unexpected data."""

class Market(str, Enum):
    """支持的股票市场"""
    A_SHARE = "A股"
    HK = "港股"
    US = "美股"


@dataclass
class StockQuote:
    """实时行情数据"""
    symbol: str
    name: str
    market: Market
    current_price: Decimal
    change: Decimal
    change_percent: Decimal
    open_price: Decimal
    high: Decimal
    low: Decimal
    volume: int
    amount: Decimal
    timestamp: datetime
    pe_ratio: Optional[Decimal] = None
    pb_ratio: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None


@dataclass
class KlineData:
    """K线数据"""
    date: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal


class StockClient:
    """股票数据客户端 - 使用 AkShare 获取 A股/港股/美股 数据

    遵循 OkxClient 的设计模式，提供统一的接口和错误处理。
    """

    def __init__(self) -> None:
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(seconds=30)  # 30秒缓存
        # Per-cache-key locks to prevent stampedes (e.g. multiple requests fetching
        # the same full-market spot dataframe concurrently).
        self._locks: Dict[str, asyncio.Lock] = {}

    def _normalize_symbol(self, symbol: str, market: Market) -> str:
        """标准化股票代码格式

        A股: 600000 -> 600000 (上海), 000001 -> 000001 (深圳)
        港股: 00700 -> 00700
        美股: AAPL -> AAPL
        """
        symbol = symbol.upper().strip()

        if market == Market.A_SHARE:
            # 移除前缀 (SH600000 -> 600000)
            if symbol.startswith(("SH", "SZ")):
                symbol = symbol[2:]
            return symbol.zfill(6)
        elif market == Market.HK:
            # 移除前缀 (HK00700 -> 00700)
            if symbol.startswith("HK"):
                symbol = symbol[2:]
            return symbol.zfill(5)
        elif market == Market.US:
            return symbol

        return symbol

    def _a_share_symbol_with_exchange(self, symbol: str) -> str:
        """Convert A-share code to exchange-qualified format for Sina/Tencent.

        Examples:
        - 600000 -> sh600000
        - 000001 -> sz000001
        """
        s = symbol.upper().strip()
        if s.startswith(("SH", "SZ", "BJ")):
            prefix = s[:2].lower()
            code = s[2:]
            return f"{prefix}{code.zfill(6)}"

        code = s.zfill(6)
        if code.startswith(("6", "9")) or code.startswith("688"):
            prefix = "sh"
        elif code.startswith(("0", "2", "3")):
            prefix = "sz"
        elif code.startswith(("8", "4")):
            prefix = "bj"
        else:
            prefix = "sh"
        return f"{prefix}{code}"

    def _standardize_hist_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize kline dataframe to columns: date, open, high, low, close, volume, amount."""
        if df is None or df.empty:
            return pd.DataFrame()

        source = df.copy()

        # Eastmoney (中文列)
        if "日期" in source.columns:
            out = pd.DataFrame()
            out["date"] = pd.to_datetime(source["日期"])
            out["open"] = pd.to_numeric(source.get("开盘"), errors="coerce")
            out["high"] = pd.to_numeric(source.get("最高"), errors="coerce")
            out["low"] = pd.to_numeric(source.get("最低"), errors="coerce")
            out["close"] = pd.to_numeric(source.get("收盘"), errors="coerce")
            out["volume"] = pd.to_numeric(source.get("成交量"), errors="coerce")
            out["amount"] = pd.to_numeric(source.get("成交额"), errors="coerce")
            return out

        # Sina/Tencent (英文列)
        if "date" not in source.columns:
            if isinstance(source.index, pd.DatetimeIndex):
                source = source.reset_index().rename(columns={"index": "date"})

        out = pd.DataFrame()
        out["date"] = pd.to_datetime(source.get("date"))
        out["open"] = pd.to_numeric(source.get("open"), errors="coerce")
        out["high"] = pd.to_numeric(source.get("high"), errors="coerce")
        out["low"] = pd.to_numeric(source.get("low"), errors="coerce")
        out["close"] = pd.to_numeric(source.get("close"), errors="coerce")
        out["volume"] = pd.to_numeric(source.get("volume"), errors="coerce")
        out["amount"] = pd.to_numeric(source.get("amount"), errors="coerce") if "amount" in source.columns else 0
        return out

    def _resample_hist_df(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """Resample daily OHLCV to weekly/monthly when providers don't support it."""
        if df is None or df.empty or period == "daily":
            return df

        rule = {"weekly": "W", "monthly": "M"}.get(period)
        if not rule:
            return df

        temp = df.copy()
        temp["date"] = pd.to_datetime(temp["date"])
        temp = temp.sort_values("date").set_index("date")

        agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        if "amount" in temp.columns:
            agg["amount"] = "sum"

        out = temp.resample(rule).agg(agg).dropna(subset=["open", "close"]).reset_index()
        return out

    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存数据（如果未过期）"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any) -> None:
        """设置缓存"""
        self._cache[key] = (data, datetime.now())

    def _get_lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _spot_providers(self, market: Market) -> List[tuple[str, Any]]:
        """Return provider callables for spot data in priority order.

        We default to Eastmoney (`*_em`) for richer fields, but it may be
        unreachable in some networks. Sina is used as a fallback.
        """
        if market == Market.A_SHARE:
            return [
                ("eastmoney", ak.stock_zh_a_spot_em),
                ("sina", ak.stock_zh_a_spot),
            ]
        if market == Market.HK:
            return [
                ("eastmoney", ak.stock_hk_spot_em),
                ("sina", ak.stock_hk_spot),
            ]
        if market == Market.US:
            return [
                ("eastmoney", ak.stock_us_spot_em),
                ("sina", ak.stock_us_spot),
            ]
        return []

    def _standardize_spot_df(self, df: pd.DataFrame, market: Market) -> pd.DataFrame:
        """Standardize provider spot dataframe to a common schema.

        Goal: normalize to columns commonly used across the service:
        - 代码, 名称, 最新价, 涨跌额, 涨跌幅, 今开, 最高, 最低, 成交量, 成交额
        """
        if df is None or df.empty:
            return pd.DataFrame()

        standardized = df.copy()

        # HK Sina uses 中文名称
        if "名称" not in standardized.columns and "中文名称" in standardized.columns:
            standardized["名称"] = standardized["中文名称"]

        # US Sina uses english keys
        if "代码" not in standardized.columns:
            if "symbol" in standardized.columns:
                standardized.rename(columns={"symbol": "代码"}, inplace=True)
            elif "code" in standardized.columns:
                standardized.rename(columns={"code": "代码"}, inplace=True)

        if "名称" not in standardized.columns:
            if "cname" in standardized.columns:
                standardized.rename(columns={"cname": "名称"}, inplace=True)
            elif "name" in standardized.columns:
                standardized.rename(columns={"name": "名称"}, inplace=True)

        # Numeric columns
        if "最新价" not in standardized.columns:
            for candidate in ("trade", "price", "last", "close"):
                if candidate in standardized.columns:
                    standardized["最新价"] = standardized[candidate]
                    break
        if "涨跌额" not in standardized.columns:
            for candidate in ("pricechange", "change"):
                if candidate in standardized.columns:
                    standardized["涨跌额"] = standardized[candidate]
                    break
        if "涨跌幅" not in standardized.columns:
            for candidate in ("changepercent", "change_percent", "chg"):
                if candidate in standardized.columns:
                    standardized["涨跌幅"] = standardized[candidate]
                    break
        if "今开" not in standardized.columns and "open" in standardized.columns:
            standardized["今开"] = standardized["open"]
        if "最高" not in standardized.columns and "high" in standardized.columns:
            standardized["最高"] = standardized["high"]
        if "最低" not in standardized.columns and "low" in standardized.columns:
            standardized["最低"] = standardized["low"]
        if "成交量" not in standardized.columns and "volume" in standardized.columns:
            standardized["成交量"] = standardized["volume"]
        if "成交额" not in standardized.columns and "amount" in standardized.columns:
            standardized["成交额"] = standardized["amount"]

        # Ensure expected dtypes (best-effort).
        if "代码" in standardized.columns:
            standardized["代码"] = standardized["代码"].astype(str)
        if "名称" in standardized.columns:
            standardized["名称"] = standardized["名称"].astype(str)

        return standardized

    async def _get_spot_df(self, market: Market) -> pd.DataFrame:
        cache_key = f"spot:{market.value}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        lock = self._get_lock(cache_key)
        async with lock:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            errors: List[str] = []
            for provider_name, fn in self._spot_providers(market):
                try:
                    df = await asyncio.to_thread(fn)
                    df = self._standardize_spot_df(df, market)
                    if df is None or df.empty:
                        errors.append(f"{provider_name}: empty dataframe")
                        continue

                    self._set_cache(cache_key, df)
                    return df
                except Exception as exc:
                    errors.append(f"{provider_name}: {exc}")

            raise StockDataError(
                f"Failed to fetch spot data for {market.value}. Providers tried: {', '.join(errors)}"
            )

    def _safe_decimal(self, value: Any, default: Decimal = Decimal("0")) -> Decimal:
        """安全转换为 Decimal"""
        try:
            if pd.isna(value) or value is None or value == "":
                return default
            return Decimal(str(value))
        except Exception:
            return default

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """安全转换为 int"""
        try:
            if pd.isna(value) or value is None or value == "":
                return default
            return int(float(value))
        except Exception:
            return default

    async def fetch_realtime_quote(
        self,
        symbol: str,
        market: Market,
        strict: bool = False,
    ) -> Optional[StockQuote]:
        """获取单只股票的实时行情"""
        cache_key = f"quote:{market.value}:{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            normalized = self._normalize_symbol(symbol, market)
            df = await self._get_spot_df(market)

            if "代码" not in df.columns:
                raise StockDataError(f"Spot dataframe missing 代码 column for {market.value}")

            code_series = df["代码"].astype(str)
            if market == Market.US:
                match = code_series.str.upper() == normalized.upper()
            else:
                match = code_series == normalized

            matched = df[match]
            if matched.empty and market == Market.HK:
                # Some providers may not left-pad HK codes; try both.
                try:
                    alt = str(int(normalized))
                except Exception:
                    alt = normalized.lstrip("0")
                if alt:
                    matched = df[code_series == alt]

            if matched.empty:
                logger.warning("%s 股票 %s 未找到", market.value, normalized)
                return None

            row = matched.iloc[0]

            quote = StockQuote(
                symbol=str(row.get("代码") or normalized),
                name=str(row.get("名称") or ""),
                market=market,
                current_price=self._safe_decimal(row.get("最新价")),
                change=self._safe_decimal(row.get("涨跌额")),
                change_percent=self._safe_decimal(row.get("涨跌幅")),
                open_price=self._safe_decimal(row.get("今开")),
                high=self._safe_decimal(row.get("最高")),
                low=self._safe_decimal(row.get("最低")),
                volume=self._safe_int(row.get("成交量")),
                amount=self._safe_decimal(row.get("成交额")),
                timestamp=datetime.now(),
                pe_ratio=self._safe_decimal(row.get("市盈率-动态")) if row.get("市盈率-动态") is not None else None,
                pb_ratio=self._safe_decimal(row.get("市净率")) if row.get("市净率") is not None else None,
                market_cap=self._safe_decimal(row.get("总市值")) if row.get("总市值") is not None else None,
            )

            self._set_cache(cache_key, quote)
            return quote

        except StockDataError:
            if strict:
                raise
            logger.exception("获取 %s (%s) 行情失败，尝试历史数据回退", symbol, market.value)
            fallback = await self.fetch_latest_quote_from_history(symbol, market)
            if fallback:
                return fallback
            return None
        except Exception:
            if strict:
                raise StockDataError(f"Failed to fetch quote for {symbol} ({market.value})")
            logger.exception("获取 %s (%s) 行情失败，尝试历史数据回退", symbol, market.value)
            fallback = await self.fetch_latest_quote_from_history(symbol, market)
            if fallback:
                return fallback
            return None

    async def fetch_latest_quote_from_history(
        self,
        symbol: str,
        market: Market,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
    ) -> Optional[StockQuote]:
        """从历史K线生成最近交易日行情快照（非实时）"""
        end_date = end_date or datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")

        klines = await self.fetch_kline(
            symbol=symbol,
            market=market,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        if not klines:
            return None

        klines_sorted = sorted(klines, key=lambda k: k.date)
        latest = klines_sorted[-1]
        prev = klines_sorted[-2] if len(klines_sorted) > 1 else None

        prev_close = prev.close if prev else latest.open or latest.close
        if prev_close and prev_close != Decimal("0"):
            change = latest.close - prev_close
            change_percent = (change / prev_close) * Decimal("100")
        else:
            change = Decimal("0")
            change_percent = Decimal("0")

        return StockQuote(
            symbol=self._normalize_symbol(symbol, market),
            name="",
            market=market,
            current_price=latest.close,
            change=change,
            change_percent=change_percent,
            open_price=latest.open,
            high=latest.high,
            low=latest.low,
            volume=latest.volume,
            amount=latest.amount,
            timestamp=latest.date,
        )

    async def fetch_realtime_quotes_batch(
        self,
        symbols: List[tuple[str, Market]]
    ) -> Dict[str, StockQuote]:
        """批量获取实时行情"""
        results = {}
        for symbol, market in symbols:
            quote = await self.fetch_realtime_quote(symbol, market)
            if quote:
                results[f"{market.value}:{symbol}"] = quote
        return results

    async def fetch_kline(
        self,
        symbol: str,
        market: Market,
        period: str = "daily",  # daily, weekly, monthly
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",  # qfq=前复权, hfq=后复权, ""=不复权
    ) -> List[KlineData]:
        """获取历史K线数据"""
        try:
            normalized = self._normalize_symbol(symbol, market)
            end_date = end_date or datetime.now().strftime("%Y%m%d")
            start_date = start_date or (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

            providers: List[tuple[str, Any, Dict[str, Any], bool]] = []
            if market == Market.A_SHARE:
                providers = [
                    (
                        "eastmoney",
                        ak.stock_zh_a_hist,
                        {
                            "symbol": normalized,
                            "period": period,
                            "start_date": start_date,
                            "end_date": end_date,
                            "adjust": adjust,
                        },
                        True,
                    ),
                    (
                        "tencent",
                        ak.stock_zh_a_hist_tx,
                        {
                            "symbol": self._a_share_symbol_with_exchange(normalized),
                            "start_date": start_date,
                            "end_date": end_date,
                            "adjust": adjust,
                        },
                        False,
                    ),
                    (
                        "sina",
                        ak.stock_zh_a_daily,
                        {
                            "symbol": self._a_share_symbol_with_exchange(normalized),
                            "start_date": start_date,
                            "end_date": end_date,
                            "adjust": adjust,
                        },
                        False,
                    ),
                ]
            elif market == Market.HK:
                hk_adjust = adjust if adjust in ("", "qfq", "qfq-factor") else ""
                providers = [
                    (
                        "eastmoney",
                        ak.stock_hk_hist,
                        {
                            "symbol": normalized,
                            "period": period,
                            "start_date": start_date,
                            "end_date": end_date,
                            "adjust": adjust,
                        },
                        True,
                    ),
                    (
                        "sina",
                        ak.stock_hk_daily,
                        {
                            "symbol": normalized,
                            "adjust": hk_adjust,
                        },
                        False,
                    ),
                ]
            elif market == Market.US:
                us_adjust = adjust if adjust in ("", "qfq", "qfq-factor") else ""
                providers = [
                    (
                        "eastmoney",
                        ak.stock_us_hist,
                        {
                            "symbol": normalized,
                            "period": period,
                            "start_date": start_date,
                            "end_date": end_date,
                            "adjust": adjust,
                        },
                        True,
                    ),
                    (
                        "sina",
                        ak.stock_us_daily,
                        {
                            "symbol": normalized,
                            "adjust": us_adjust,
                        },
                        False,
                    ),
                ]
            else:
                return []

            df = pd.DataFrame()
            errors: List[str] = []
            for provider_name, fn, kwargs, supports_period in providers:
                try:
                    raw_df = await asyncio.to_thread(fn, **kwargs)
                    df = self._standardize_hist_df(raw_df)
                    if df is None or df.empty:
                        errors.append(f"{provider_name}: empty dataframe")
                        continue

                    df = df.dropna(subset=["date"]).sort_values("date")
                    if start_date:
                        start_dt = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
                        if pd.notna(start_dt):
                            df = df[df["date"] >= start_dt]
                    if end_date:
                        end_dt = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
                        if pd.notna(end_dt):
                            df = df[df["date"] <= end_dt]

                    if not supports_period and period != "daily":
                        df = self._resample_hist_df(df, period)

                    if df.empty:
                        errors.append(f"{provider_name}: empty after filtering")
                        continue

                    break
                except Exception as exc:
                    errors.append(f"{provider_name}: {exc}")
                    continue

            if df is None or df.empty:
                logger.warning(
                    "K线数据获取失败 %s (%s): %s",
                    symbol,
                    market.value,
                    "; ".join(errors),
                )
                return []

            klines = []
            for _, row in df.iterrows():
                klines.append(
                    KlineData(
                        date=pd.to_datetime(row["date"]),
                        open=self._safe_decimal(row.get("open")),
                        high=self._safe_decimal(row.get("high")),
                        low=self._safe_decimal(row.get("low")),
                        close=self._safe_decimal(row.get("close")),
                        volume=self._safe_int(row.get("volume")),
                        amount=self._safe_decimal(row.get("amount")),
                    )
                )
            return klines

        except Exception as e:
            logger.error(f"获取 {symbol} ({market.value}) K线数据失败: {e}")
            return []

    async def fetch_market_overview(self, market: Market) -> Dict[str, Any]:
        """获取市场概览统计（涨跌家数等）"""
        cache_key = f"overview:{market.value}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            df = await self._get_spot_df(market)
            if df is None or df.empty:
                raise StockDataError(f"spot dataframe empty for {market.value}")

            if "最新价" not in df.columns:
                raise StockDataError(f"spot dataframe missing 最新价 for {market.value}")

            total = len(df)
            active_df = df[df["最新价"].notna() & (df["最新价"] != 0)]
            active_total = len(active_df)

            if "涨跌幅" in active_df.columns:
                up = len(active_df[active_df["涨跌幅"] > 0])
                down = len(active_df[active_df["涨跌幅"] < 0])
            else:
                up = 0
                down = 0
            flat = active_total - up - down

            result = {
                "market": market.value,
                "total_stocks": total,
                "active_stocks": active_total,
                "up_count": up,
                "down_count": down,
                "flat_count": flat,
                "up_ratio": round(up / active_total * 100, 2) if active_total > 0 else 0,
                "timestamp": datetime.now().isoformat(),
            }

            if market == Market.A_SHARE and "涨跌幅" in active_df.columns:
                result["limit_up_count"] = len(active_df[active_df["涨跌幅"] >= 9.9])
                result["limit_down_count"] = len(active_df[active_df["涨跌幅"] <= -9.9])

                if "成交量" in active_df.columns:
                    avg_volume = active_df["成交量"].mean()
                    result["high_volume_count"] = (
                        len(active_df[active_df["成交量"] > avg_volume * 2]) if avg_volume > 0 else 0
                    )

            self._set_cache(cache_key, result)
            return result

        except StockDataError:
            raise
        except Exception as e:
            raise StockDataError(f"Failed to compute market overview for {market.value}: {e}")

    async def fetch_volume_surge_stocks(
        self,
        market: Market,
        threshold: float = 2.0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取放量股票列表"""
        cache_key = f"volume_surge:{market.value}:{threshold}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            df = await self._get_spot_df(market)
            if df is None or df.empty:
                return []

            if "成交量" not in df.columns:
                raise StockDataError(f"spot dataframe missing 成交量 for {market.value}")

            # 过滤有效数据
            df = df[df["成交量"].notna() & (df["成交量"] > 0)]

            # 计算平均成交量
            avg_volume = df["成交量"].mean()

            # 筛选放量股票
            surge_df = df[df["成交量"] > avg_volume * threshold]
            surge_df = surge_df.sort_values("成交量", ascending=False).head(limit)

            results = []
            for _, row in surge_df.iterrows():
                results.append({
                    "symbol": str(row.get("代码")),
                    "name": str(row.get("名称")),
                    "current_price": float(self._safe_decimal(row.get("最新价"))),
                    "change_percent": float(self._safe_decimal(row.get("涨跌幅"))),
                    "volume": self._safe_int(row.get("成交量")),
                    "volume_ratio": round(row.get("成交量", 0) / avg_volume, 2) if avg_volume > 0 else 0,
                    "amount": float(self._safe_decimal(row.get("成交额"))),
                })

            self._set_cache(cache_key, results)
            return results

        except StockDataError:
            raise
        except Exception as e:
            raise StockDataError(f"Failed to compute volume surge for {market.value}: {e}")

    async def fetch_financial_data(
        self,
        symbol: str,
        market: Market
    ) -> Dict[str, Any]:
        """获取股票财务数据（市盈率、市净率等）"""
        try:
            normalized = self._normalize_symbol(symbol, market)

            if market == Market.A_SHARE:
                df = await self._get_spot_df(market)
                if df is None or df.empty or "代码" not in df.columns:
                    return {}
                row = df[df["代码"].astype(str) == normalized]
                if row.empty:
                    return {}
                row = row.iloc[0]

                return {
                    "symbol": normalized,
                    "name": str(row.get("名称")),
                    "market": market.value,
                    "pe_ratio": float(self._safe_decimal(row.get("市盈率-动态", 0))),
                    "pb_ratio": float(self._safe_decimal(row.get("市净率", 0))),
                    "market_cap": float(self._safe_decimal(row.get("总市值", 0))),
                    "circulating_cap": float(self._safe_decimal(row.get("流通市值", 0))),
                    "turnover_rate": float(self._safe_decimal(row.get("换手率", 0))),
                    "volume_ratio": float(self._safe_decimal(row.get("量比", 0))),
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                # 港股和美股暂时返回基础数据
                quote = await self.fetch_realtime_quote(symbol, market)
                if quote:
                    return {
                        "symbol": quote.symbol,
                        "name": quote.name,
                        "market": market.value,
                        "pe_ratio": float(quote.pe_ratio) if quote.pe_ratio else None,
                        "pb_ratio": float(quote.pb_ratio) if quote.pb_ratio else None,
                        "market_cap": float(quote.market_cap) if quote.market_cap else None,
                        "timestamp": datetime.now().isoformat(),
                    }
                return {}

        except Exception as e:
            logger.error(f"获取 {symbol} ({market.value}) 财务数据失败: {e}")
            return {}

    async def search_stock(
        self,
        keyword: str,
        market: Optional[Market] = None
    ) -> List[Dict[str, Any]]:
        """搜索股票（按代码或名称）"""
        results = []

        try:
            markets = [market] if market else [Market.A_SHARE, Market.HK, Market.US]

            for m in markets:
                df = await self._get_spot_df(m)
                if df is None or df.empty:
                    continue

                # 按代码或名称搜索
                mask = (
                    df["代码"].astype(str).str.contains(keyword, case=False, na=False) |
                    df["名称"].astype(str).str.contains(keyword, case=False, na=False)
                )
                matched = df[mask].head(10)

                for _, row in matched.iterrows():
                    results.append({
                        "symbol": str(row.get("代码")),
                        "name": str(row.get("名称")),
                        "market": m.value,
                        "current_price": float(self._safe_decimal(row.get("最新价"))),
                        "change_percent": float(self._safe_decimal(row.get("涨跌幅"))),
                    })

        except StockDataError:
            raise
        except Exception as e:
            raise StockDataError(f"搜索股票 '{keyword}' 失败: {e}")

        return results[:20]  # 最多返回20条
