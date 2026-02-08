
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, Numeric, String, Text
from sqlalchemy.sql import func

# pgvector temporarily disabled - uncomment when pgvector is available
# from pgvector.sqlalchemy import Vector
from app.database import Base


class Asset(Base):
    """资产表 - 存储各类账户余额"""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    account_type = Column(String(50), nullable=False, index=True)  # 银行/A股/港股/OKX/分红险
    account_name = Column(String(100), nullable=False)
    balance = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), default="CNY")
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    extra_data = Column("metadata", JSON, nullable=True)  # renamed to avoid SQLAlchemy reserved word

    def __repr__(self):
        return f"<Asset(id={self.id}, type={self.account_type}, name={self.account_name}, balance={self.balance})>"


class MarketNews(Base):
    """市场新闻表 - 使用 pgvector 存储 Embedding"""
    __tablename__ = "market_news"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(100), nullable=True)
    published_at = Column(DateTime, nullable=True)
    # embedding = Column(Vector(1536), nullable=True)  # pgvector disabled
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<MarketNews(id={self.id}, title={self.title[:50]}, source={self.source})>"


class Transaction(Base):
    """交易流水表 - 记录资金流动，特别标记婚礼支出"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(String(50), nullable=False)  # income/expense/transfer
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), default="CNY")
    from_account = Column(String(100), nullable=True)
    to_account = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True)
    is_wedding_expense = Column(Boolean, default=False, index=True)
    description = Column(Text, nullable=True)
    transaction_date = Column(DateTime, default=func.now(), index=True)
    extra_data = Column("metadata", JSON, nullable=True)  # renamed to avoid SQLAlchemy reserved word

    def __repr__(self):
        wedding_flag = "[婚礼]" if self.is_wedding_expense else ""
        return f"<Transaction(id={self.id}, type={self.transaction_type}, amount={self.amount} {wedding_flag})>"
