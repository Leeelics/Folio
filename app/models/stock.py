"""股票相关数据模型"""

from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.sql import func

from app.database import Base


class StockPosition(Base):
    """股票持仓表 - 记录用户的股票持仓"""
    __tablename__ = "stock_positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)  # 股票代码: 600000, 00700, AAPL
    market = Column(String(20), nullable=False, index=True)  # 市场: A股/港股/美股
    name = Column(String(100), nullable=True)  # 股票名称（缓存）
    quantity = Column(Integer, nullable=False)  # 持仓数量
    cost_price = Column(Numeric(15, 4), nullable=False)  # 成本价
    account_name = Column(String(100), default="默认账户")  # 券商账户名称
    currency = Column(String(10), default="CNY")  # 货币: CNY/HKD/USD
    notes = Column(Text, nullable=True)  # 备注
    extra_data = Column("metadata", JSON, nullable=True)  # 扩展数据
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_stock_positions_market_symbol', 'market', 'symbol'),
    )

    def __repr__(self):
        return f"<StockPosition(id={self.id}, symbol={self.symbol}, market={self.market}, quantity={self.quantity})>"


class StockWatchlist(Base):
    """自选股表 - 用户关注的股票列表"""
    __tablename__ = "stock_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)  # 股票代码
    market = Column(String(20), nullable=False)  # 市场
    name = Column(String(100), nullable=True)  # 股票名称
    notes = Column(Text, nullable=True)  # 备注
    alert_price_high = Column(Numeric(15, 4), nullable=True)  # 价格上限提醒
    alert_price_low = Column(Numeric(15, 4), nullable=True)  # 价格下限提醒
    alert_volume_ratio = Column(Numeric(5, 2), nullable=True)  # 放量提醒阈值
    is_active = Column(Boolean, default=True)  # 是否启用
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_watchlist_market_symbol', 'market', 'symbol', unique=True),
    )

    def __repr__(self):
        return f"<StockWatchlist(id={self.id}, symbol={self.symbol}, market={self.market})>"


class StockQuoteCache(Base):
    """股票行情缓存表 - 减少 API 调用"""
    __tablename__ = "stock_quote_cache"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)  # 股票代码
    market = Column(String(20), nullable=False)  # 市场
    name = Column(String(100), nullable=True)  # 股票名称
    current_price = Column(Numeric(15, 4), nullable=True)  # 当前价格
    change = Column(Numeric(15, 4), nullable=True)  # 涨跌额
    change_percent = Column(Numeric(10, 4), nullable=True)  # 涨跌幅
    open_price = Column(Numeric(15, 4), nullable=True)  # 开盘价
    high = Column(Numeric(15, 4), nullable=True)  # 最高价
    low = Column(Numeric(15, 4), nullable=True)  # 最低价
    volume = Column(Numeric(20, 0), nullable=True)  # 成交量
    amount = Column(Numeric(20, 2), nullable=True)  # 成交额
    pe_ratio = Column(Numeric(10, 2), nullable=True)  # 市盈率
    pb_ratio = Column(Numeric(10, 2), nullable=True)  # 市净率
    market_cap = Column(Numeric(20, 2), nullable=True)  # 总市值
    quote_data = Column(JSON, nullable=True)  # 完整行情数据
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_quote_cache_market_symbol', 'market', 'symbol', unique=True),
    )

    def __repr__(self):
        return f"<StockQuoteCache(symbol={self.symbol}, market={self.market}, price={self.current_price})>"
