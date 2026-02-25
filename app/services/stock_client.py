"""股票数据客户端 - 使用 Tushare (A股/港股) + AkShare (美股) 获取行情数据"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

import akshare as ak
import pandas as pd
import tushare as ts

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
    """股票数据客户端 - 使用 Tushare (A股/港股) + AkShare (美股) 获取行情数据

    遵循 OkxClient 的设计模式，提供统一的接口和错误处理。
    """

    def __init__(self) -> None:
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(seconds=30)  # 30秒缓存
        # Per-cache-key locks to prevent stampedes
        self._locks: Dict[str, asyncio.Lock] = {}

        # Initialize Tushare pro API (load from dotenv if not in env)
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            try:
                from dotenv import dotenv_values
                token = dotenv_values(".env").get("TUSHARE_TOKEN", "")
            except Exception:
                pass
        if token:
            ts.set_token(token)
            self._pro = ts.pro_api(token)
        else:
            self._pro = None
            logger.warning("TUSHARE_TOKEN not set, Tushare API unavailable; falling back to AkShare")

    # ── symbol helpers ──────────────────────────────────────────────

    def _normalize_symbol(self, symbol: str, market: Market) -> str:
        """标准化股票代码格式

        A股: 600000 -> 600000 (上海), 000001 -> 000001 (深圳)
        港股: 00700 -> 00700
        美股: AAPL -> AAPL
        """
        symbol = symbol.upper().strip()

        if market == Market.A_SHARE:
            if symbol.startswith(("SH", "SZ")):
                symbol = symbol[2:]
            return symbol.zfill(6)
        elif market == Market.HK:
            if symbol.startswith("HK"):
                symbol = symbol[2:]
            return symbol.zfill(5)
        elif market == Market.US:
            return symbol

        return symbol

    def _to_tushare_symbol(self, symbol: str) -> str:
        """Convert A-share code to Tushare format: 600519 -> 600519.SH, 000001 -> 000001.SZ"""
        code = symbol.zfill(6)
        if code.startswith(("6", "9")) or code.startswith("688"):
            return f"{code}.SH"
        elif code.startswith(("0", "2", "3")):
            return f"{code}.SZ"
        elif code.startswith(("8", "4")):
            return f"{code}.BJ"
        else:
            return f"{code}.SH"

    def _to_tushare_hk_symbol(self, symbol: str) -> str:
        """Convert HK code to Tushare format: 00700 -> 00700.HK"""
        return f"{symbol.zfill(5)}.HK"

    def _a_share_symbol_with_exchange(self, symbol: str) -> str:
        """Convert A-share code to exchange-qualified format for Sina/Tencent."""
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

    # ── cache / lock helpers ────────────────────────────────────────

    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any) -> None:
        self._cache[key] = (data, datetime.now())

    def _get_lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    # ── safe type conversions ───────────────────────────────────────

    def _safe_decimal(self, value: Any, default: Decimal = Decimal("0")) -> Decimal:
        try:
            if pd.isna(value) or value is None or value == "":
                return default
            return Decimal(str(value))
        except Exception:
            return default

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            if pd.isna(value) or value is None or value == "":
                return default
            return int(float(value))
        except Exception:
            return default

    # ── Tushare spot data ───────────────────────────────────────────

    def _fetch_a_share_spot_tushare(self) -> pd.DataFrame:
        """Fetch A-share daily data from Tushare and standardize to spot schema."""
        if self._pro is None:
            raise StockDataError("Tushare API not initialized (missing TUSHARE_TOKEN)")

        # Get latest trade date
        cal = self._pro.trade_cal(exchange="SSE", is_open="1", limit=5,
                                   fields="cal_date", end_date=datetime.now().strftime("%Y%m%d"))
        if cal is None or cal.empty:
            raise StockDataError("Failed to get trade calendar from Tushare")
        trade_date = cal["cal_date"].max()

        # Fetch daily quotes + basic info
        df_daily = self._pro.daily(trade_date=trade_date)
        if df_daily is None or df_daily.empty:
            raise StockDataError(f"No A-share daily data for {trade_date}")

        df_basic = self._pro.daily_basic(trade_date=trade_date,
                                          fields="ts_code,pe_ttm,pb,total_mv,circ_mv,turnover_rate,volume_ratio")

        # Get stock names
        df_names = self._pro.stock_basic(exchange="", list_status="L",
                                          fields="ts_code,name")

        # Merge
        df = df_daily.merge(df_names, on="ts_code", how="left")
        if df_basic is not None and not df_basic.empty:
            df = df.merge(df_basic, on="ts_code", how="left")

        # Extract pure code (000001.SZ -> 000001)
        df["代码"] = df["ts_code"].str.split(".").str[0]
        df["名称"] = df.get("name", "")
        df["最新价"] = pd.to_numeric(df["close"], errors="coerce")
        df["涨跌额"] = pd.to_numeric(df["change"], errors="coerce")
        df["涨跌幅"] = pd.to_numeric(df["pct_chg"], errors="coerce")
        df["今开"] = pd.to_numeric(df["open"], errors="coerce")
        df["最高"] = pd.to_numeric(df["high"], errors="coerce")
        df["最低"] = pd.to_numeric(df["low"], errors="coerce")
        df["成交量"] = pd.to_numeric(df["vol"], errors="coerce")
        df["成交额"] = pd.to_numeric(df["amount"], errors="coerce") * 1000  # Tushare amount is in 千元

        # Financial fields (if available)
        if "pe_ttm" in df.columns:
            df["市盈率-动态"] = pd.to_numeric(df["pe_ttm"], errors="coerce")
        if "pb" in df.columns:
            df["市净率"] = pd.to_numeric(df["pb"], errors="coerce")
        if "total_mv" in df.columns:
            df["总市值"] = pd.to_numeric(df["total_mv"], errors="coerce") * 10000  # 万元 -> 元
        if "circ_mv" in df.columns:
            df["流通市值"] = pd.to_numeric(df["circ_mv"], errors="coerce") * 10000
        if "turnover_rate" in df.columns:
            df["换手率"] = pd.to_numeric(df["turnover_rate"], errors="coerce")
        if "volume_ratio" in df.columns:
            df["量比"] = pd.to_numeric(df["volume_ratio"], errors="coerce")

        return df

    def _fetch_hk_spot_tushare(self) -> pd.DataFrame:
        """Fetch HK daily data from Tushare and standardize to spot schema."""
        if self._pro is None:
            raise StockDataError("Tushare API not initialized (missing TUSHARE_TOKEN)")

        # Get latest HK trade date
        cal = self._pro.hk_tradecal(is_open="1", limit=5,
                                     end_date=datetime.now().strftime("%Y%m%d"))
        if cal is None or cal.empty:
            # Fallback: use today or yesterday
            trade_date = datetime.now().strftime("%Y%m%d")
        else:
            trade_date = cal["cal_date"].max()

        df = self._pro.hk_daily(trade_date=trade_date)
        if df is None or df.empty:
            # Try previous day
            prev = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            df = self._pro.hk_daily(trade_date=prev)
            if df is None or df.empty:
                raise StockDataError(f"No HK daily data for {trade_date}")

        # Get HK stock names
        try:
            df_names = self._pro.hk_basic(fields="ts_code,name")
            if df_names is not None and not df_names.empty:
                df = df.merge(df_names, on="ts_code", how="left")
        except Exception:
            df["name"] = ""

        # Extract pure code (00700.HK -> 00700)
        df["代码"] = df["ts_code"].str.split(".").str[0]
        df["名称"] = df.get("name", "")
        df["最新价"] = pd.to_numeric(df["close"], errors="coerce")
        df["涨跌额"] = pd.to_numeric(df["change"], errors="coerce") if "change" in df.columns else 0
        df["涨跌幅"] = pd.to_numeric(df["pct_chg"], errors="coerce") if "pct_chg" in df.columns else 0
        df["今开"] = pd.to_numeric(df["open"], errors="coerce")
        df["最高"] = pd.to_numeric(df["high"], errors="coerce")
        df["最低"] = pd.to_numeric(df["low"], errors="coerce")
        df["成交量"] = pd.to_numeric(df["vol"], errors="coerce")
        df["成交额"] = pd.to_numeric(df["amount"], errors="coerce") * 1000 if "amount" in df.columns else 0

        return df

    # ── AkShare fallback for US stocks ──────────────────────────────

    def _spot_providers_us(self) -> List[tuple[str, Any]]:
        return [
            ("eastmoney", ak.stock_us_spot_em),
            ("sina", ak.stock_us_spot),
        ]

    def _standardize_spot_df(self, df: pd.DataFrame, market: Market) -> pd.DataFrame:
        """Standardize provider spot dataframe to common schema (used for US AkShare fallback)."""
        if df is None or df.empty:
            return pd.DataFrame()

        standardized = df.copy()

        if "名称" not in standardized.columns and "中文名称" in standardized.columns:
            standardized["名称"] = standardized["中文名称"]

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

        if "代码" in standardized.columns:
            standardized["代码"] = standardized["代码"].astype(str)
        if "名称" in standardized.columns:
            standardized["名称"] = standardized["名称"].astype(str)

        return standardized

    # ── spot data dispatcher ────────────────────────────────────────

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

            if market == Market.A_SHARE:
                df = await self._get_spot_df_tushare(market, self._fetch_a_share_spot_tushare)
            elif market == Market.HK:
                df = await self._get_spot_df_tushare(market, self._fetch_hk_spot_tushare)
            elif market == Market.US:
                df = await self._get_spot_df_akshare_us()
            else:
                raise StockDataError(f"Unsupported market: {market.value}")

            self._set_cache(cache_key, df)
            return df

    async def _get_spot_df_tushare(self, market: Market, fetch_fn) -> pd.DataFrame:
        """Fetch spot data via Tushare, fall back to AkShare on failure."""
        try:
            df = await asyncio.to_thread(fetch_fn)
            if df is not None and not df.empty:
                return df
        except Exception as exc:
            logger.warning("Tushare %s spot failed: %s, falling back to AkShare", market.value, exc)

        # AkShare fallback
        return await self._get_spot_df_akshare_fallback(market)

    async def _get_spot_df_akshare_fallback(self, market: Market) -> pd.DataFrame:
        """AkShare fallback for A-share / HK when Tushare fails."""
        providers: List[tuple[str, Any]] = []
        if market == Market.A_SHARE:
            providers = [("eastmoney", ak.stock_zh_a_spot_em)]
        elif market == Market.HK:
            providers = [("eastmoney", ak.stock_hk_spot_em)]
        else:
            return pd.DataFrame()

        errors: List[str] = []
        for name, fn in providers:
            try:
                df = await asyncio.to_thread(fn)
                df = self._standardize_spot_df(df, market)
                if df is not None and not df.empty:
                    return df
                errors.append(f"{name}: empty")
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        raise StockDataError(f"All providers failed for {market.value}: {', '.join(errors)}")

    async def _get_spot_df_akshare_us(self) -> pd.DataFrame:
        """US stocks use AkShare only."""
        errors: List[str] = []
        for name, fn in self._spot_providers_us():
            try:
                df = await asyncio.to_thread(fn)
                df = self._standardize_spot_df(df, Market.US)
                if df is not None and not df.empty:
                    return df
                errors.append(f"{name}: empty")
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        raise StockDataError(f"All US providers failed: {', '.join(errors)}")

    # ── public: realtime quote ──────────────────────────────────────

    async def _fetch_single_quote_tushare(
        self, normalized: str, market: Market,
    ) -> Optional[StockQuote]:
        """用 Tushare 单只股票 daily 接口获取最新收盘价（免费接口）"""
        if self._pro is None:
            return None

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")

        try:
            if market == Market.A_SHARE:
                ts_code = self._to_tushare_symbol(normalized)
                def _fetch():
                    return self._pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            elif market == Market.HK:
                ts_code = self._to_tushare_hk_symbol(normalized)
                def _fetch():
                    return self._pro.hk_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            else:
                return None

            df = await asyncio.to_thread(_fetch)
            if df is None or df.empty:
                return None

            df = df.sort_values("trade_date", ascending=True)
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else None

            close = self._safe_decimal(latest.get("close"))
            if close == Decimal("0"):
                return None

            prev_close = self._safe_decimal(prev.get("close")) if prev is not None else self._safe_decimal(latest.get("open"))
            if prev_close and prev_close != Decimal("0"):
                change = close - prev_close
                change_pct = (change / prev_close) * Decimal("100")
            else:
                change = self._safe_decimal(latest.get("change"))
                change_pct = self._safe_decimal(latest.get("pct_chg"))

            # Try to get stock name
            name = ""
            try:
                if market == Market.A_SHARE:
                    def _fetch_name():
                        return self._pro.stock_basic(ts_code=ts_code, fields="ts_code,name")
                elif market == Market.HK:
                    def _fetch_name():
                        return self._pro.hk_basic(ts_code=ts_code, fields="ts_code,name")
                else:
                    _fetch_name = None
                if _fetch_name:
                    df_name = await asyncio.to_thread(_fetch_name)
                    if df_name is not None and not df_name.empty:
                        name = str(df_name.iloc[0].get("name", ""))
            except Exception:
                pass

            return StockQuote(
                symbol=normalized,
                name=name,
                market=market,
                current_price=close,
                change=change,
                change_percent=change_pct,
                open_price=self._safe_decimal(latest.get("open")),
                high=self._safe_decimal(latest.get("high")),
                low=self._safe_decimal(latest.get("low")),
                volume=self._safe_int(latest.get("vol")),
                amount=self._safe_decimal(latest.get("amount")) * Decimal("1000"),
                timestamp=datetime.strptime(str(latest["trade_date"]), "%Y%m%d"),
            )
        except Exception as exc:
            logger.warning("Tushare single quote failed for %s (%s): %s", normalized, market.value, exc)
            return None

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

        normalized = self._normalize_symbol(symbol, market)

        # Strategy 1: Tushare single-stock query (free tier, A-share/HK)
        if market in (Market.A_SHARE, Market.HK) and self._pro is not None:
            quote = await self._fetch_single_quote_tushare(normalized, market)
            if quote:
                self._set_cache(cache_key, quote)
                return quote

        # Strategy 2: Spot dataframe (US stocks, or fallback)
        try:
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
            logger.warning("获取 %s (%s) 行情失败，尝试历史数据回退", symbol, market.value)
            fallback = await self.fetch_latest_quote_from_history(symbol, market)
            if fallback:
                self._set_cache(cache_key, fallback)
                return fallback
            return None
        except Exception:
            if strict:
                raise StockDataError(f"Failed to fetch quote for {symbol} ({market.value})")
            logger.warning("获取 %s (%s) 行情失败，尝试历史数据回退", symbol, market.value)
            fallback = await self.fetch_latest_quote_from_history(symbol, market)
            if fallback:
                self._set_cache(cache_key, fallback)
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
            symbol=symbol, market=market, period=period,
            start_date=start_date, end_date=end_date, adjust=adjust,
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

    # ── public: kline ───────────────────────────────────────────────

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

        # Tushare format (trade_date column)
        if "trade_date" in source.columns:
            out = pd.DataFrame()
            out["date"] = pd.to_datetime(source["trade_date"], format="%Y%m%d")
            out["open"] = pd.to_numeric(source.get("open"), errors="coerce")
            out["high"] = pd.to_numeric(source.get("high"), errors="coerce")
            out["low"] = pd.to_numeric(source.get("low"), errors="coerce")
            out["close"] = pd.to_numeric(source.get("close"), errors="coerce")
            out["volume"] = pd.to_numeric(source.get("vol"), errors="coerce")
            out["amount"] = pd.to_numeric(source.get("amount"), errors="coerce") * 1000 if "amount" in source.columns else 0
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

            df = pd.DataFrame()
            errors: List[str] = []

            # Try Tushare first for A-share and HK
            if market in (Market.A_SHARE, Market.HK) and self._pro is not None:
                try:
                    raw_df = await self._fetch_kline_tushare(normalized, market, start_date, end_date, adjust)
                    df = self._standardize_hist_df(raw_df)
                    if df is not None and not df.empty:
                        df = df.dropna(subset=["date"]).sort_values("date")
                        if period != "daily":
                            df = self._resample_hist_df(df, period)
                except Exception as exc:
                    errors.append(f"tushare: {exc}")
                    logger.warning("Tushare kline failed for %s (%s): %s", symbol, market.value, exc)

            # AkShare fallback (or primary for US)
            if df is None or df.empty:
                providers = self._kline_providers_akshare(normalized, market, period, start_date, end_date, adjust)
                for provider_name, fn, kwargs, supports_period in providers:
                    try:
                        raw_df = await asyncio.to_thread(fn, **kwargs)
                        df = self._standardize_hist_df(raw_df)
                        if df is None or df.empty:
                            errors.append(f"{provider_name}: empty dataframe")
                            continue

                        df = df.dropna(subset=["date"]).sort_values("date")
                        start_dt = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
                        if pd.notna(start_dt):
                            df = df[df["date"] >= start_dt]
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
                logger.warning("K线数据获取失败 %s (%s): %s", symbol, market.value, "; ".join(errors))
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

    async def _fetch_kline_tushare(
        self, normalized: str, market: Market,
        start_date: str, end_date: str, adjust: str,
    ) -> pd.DataFrame:
        """Fetch kline from Tushare for A-share or HK."""
        if market == Market.A_SHARE:
            ts_code = self._to_tushare_symbol(normalized)
            adj = {"qfq": "qfq", "hfq": "hfq"}.get(adjust, None)

            def _fetch():
                return self._pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date, adj=adj)
            return await asyncio.to_thread(_fetch)

        elif market == Market.HK:
            ts_code = self._to_tushare_hk_symbol(normalized)

            def _fetch():
                return self._pro.hk_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return await asyncio.to_thread(_fetch)

        return pd.DataFrame()

    def _kline_providers_akshare(
        self, normalized: str, market: Market,
        period: str, start_date: str, end_date: str, adjust: str,
    ) -> List[tuple[str, Any, Dict[str, Any], bool]]:
        """Return AkShare kline provider list (used as fallback for A/HK, primary for US)."""
        if market == Market.A_SHARE:
            return [
                (
                    "eastmoney",
                    ak.stock_zh_a_hist,
                    {"symbol": normalized, "period": period,
                     "start_date": start_date, "end_date": end_date, "adjust": adjust},
                    True,
                ),
            ]
        elif market == Market.HK:
            return [
                (
                    "eastmoney",
                    ak.stock_hk_hist,
                    {"symbol": normalized, "period": period,
                     "start_date": start_date, "end_date": end_date, "adjust": adjust},
                    True,
                ),
            ]
        elif market == Market.US:
            us_adjust = adjust if adjust in ("", "qfq", "qfq-factor") else ""
            return [
                (
                    "eastmoney",
                    ak.stock_us_hist,
                    {"symbol": normalized, "period": period,
                     "start_date": start_date, "end_date": end_date, "adjust": adjust},
                    True,
                ),
                (
                    "sina",
                    ak.stock_us_daily,
                    {"symbol": normalized, "adjust": us_adjust},
                    False,
                ),
            ]
        return []

    # ── public: market overview ─────────────────────────────────────

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

    # ── public: volume surge ────────────────────────────────────────

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

            df = df[df["成交量"].notna() & (df["成交量"] > 0)]
            avg_volume = df["成交量"].mean()

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

    # ── public: financial data ──────────────────────────────────────

    async def fetch_financial_data(
        self,
        symbol: str,
        market: Market
    ) -> Dict[str, Any]:
        """获取股票财务数据（市盈率、市净率等）"""
        try:
            normalized = self._normalize_symbol(symbol, market)

            if market == Market.A_SHARE:
                # Try Tushare daily_basic first
                if self._pro is not None:
                    try:
                        ts_code = self._to_tushare_symbol(normalized)
                        def _fetch():
                            return self._pro.daily_basic(
                                ts_code=ts_code, limit=1,
                                fields="ts_code,trade_date,pe_ttm,pb,total_mv,circ_mv,turnover_rate,volume_ratio"
                            )
                        df_basic = await asyncio.to_thread(_fetch)
                        if df_basic is not None and not df_basic.empty:
                            row = df_basic.iloc[0]
                            quote = await self.fetch_realtime_quote(symbol, market)
                            return {
                                "symbol": normalized,
                                "name": quote.name if quote else "",
                                "market": market.value,
                                "pe_ratio": float(self._safe_decimal(row.get("pe_ttm", 0))),
                                "pb_ratio": float(self._safe_decimal(row.get("pb", 0))),
                                "market_cap": float(self._safe_decimal(row.get("total_mv", 0))) * 10000,
                                "circulating_cap": float(self._safe_decimal(row.get("circ_mv", 0))) * 10000,
                                "turnover_rate": float(self._safe_decimal(row.get("turnover_rate", 0))),
                                "volume_ratio": float(self._safe_decimal(row.get("volume_ratio", 0))),
                                "timestamp": datetime.now().isoformat(),
                            }
                    except Exception as exc:
                        logger.warning("Tushare financial data failed for %s: %s", symbol, exc)

                # Fallback to spot df
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
                # 港股和美股返回基础数据
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

    # ── public: search ──────────────────────────────────────────────

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
                # Try Tushare stock_basic for A-share/HK first
                if m in (Market.A_SHARE, Market.HK) and self._pro is not None:
                    try:
                        tushare_results = await self._search_stock_tushare(keyword, m)
                        results.extend(tushare_results)
                        if tushare_results:
                            continue  # Skip spot df search if Tushare found results
                    except Exception:
                        pass  # Fall through to spot df search

                df = await self._get_spot_df(m)
                if df is None or df.empty:
                    continue

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

        return results[:20]

    async def _search_stock_tushare(self, keyword: str, market: Market) -> List[Dict[str, Any]]:
        """Search stocks via Tushare stock_basic / hk_basic."""
        results = []

        if market == Market.A_SHARE:
            def _fetch():
                return self._pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry")
            df = await asyncio.to_thread(_fetch)
        elif market == Market.HK:
            def _fetch():
                return self._pro.hk_basic(fields="ts_code,name")
            df = await asyncio.to_thread(_fetch)
        else:
            return []

        if df is None or df.empty:
            return []

        # Extract pure code for matching
        df["code"] = df["ts_code"].str.split(".").str[0]
        mask = (
            df["code"].str.contains(keyword, case=False, na=False) |
            df["name"].astype(str).str.contains(keyword, case=False, na=False)
        )
        matched = df[mask].head(10)

        for _, row in matched.iterrows():
            results.append({
                "symbol": row["code"],
                "name": str(row.get("name", "")),
                "market": market.value,
                "current_price": 0.0,  # Basic info only, no price
                "change_percent": 0.0,
            })

        return results
