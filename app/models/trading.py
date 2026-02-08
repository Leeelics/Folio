from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, Numeric, String
from sqlalchemy.sql import func

from app.database import Base


class StrategyConfig(Base):
    """策略配置表 - 管理量化策略及参数"""

    __tablename__ = "strategy_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    is_enabled = Column(Boolean, default=True, index=True)
    mode = Column(String(20), default="live")  # live / paper / backtest
    params = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Trade(Base):
    """交易记录表 - 记录策略下单与执行情况"""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String(100), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)  # e.g. BTC/USDT
    side = Column(String(10), nullable=False)  # buy / sell
    order_type = Column(String(20), default="market")  # market / limit
    amount = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=True)
    status = Column(String(20), default="created")  # created / submitted / filled / cancelled / failed
    exchange_order_id = Column(String(100), nullable=True, index=True)
    error_message = Column(String(255), nullable=True)
    extra_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

