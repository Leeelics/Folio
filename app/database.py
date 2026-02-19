from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    # Import all models to ensure they are registered with Base.metadata
    from app.models import (  # noqa: F401
        AllocationTarget,
        Asset,
        FundProduct,
        InvestmentHolding,
        InvestmentTransaction,
        MarketNews,
        RebalancingAction,
        RiskAlert,
        StockPosition,
        StockQuoteCache,
        StockWatchlist,
        Transaction,
    )

    # Import new brokerage models
    from app.models.brokerage import (  # noqa: F401
        BrokerageAccount,
        AccountCashBalance,
        PortfolioHolding,
        PortfolioTransaction,
        CashFlow,
        ExchangeRate,
    )

    # Import Phase 1 core models
    from app.models.core import (  # noqa: F401
        Account,
        Holding,
        CoreInvestmentTransaction,
        Budget,
        Expense,
        ExpenseCategory,
        CoreCashFlow,
        MarketSyncLog,
        Liability,
        LiabilityPayment,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed expense categories if table is empty
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func as sa_func

        count = await session.scalar(
            select(sa_func.count()).select_from(ExpenseCategory)
        )
        if count == 0:
            seed_categories = {
                "餐饮": ["早餐", "午餐", "晚餐", "零食饮料", "外卖", "聚餐"],
                "交通": ["公交地铁", "打车", "共享单车", "加油", "停车费", "高速过路"],
                "购物": ["日用品", "服饰鞋包", "数码电子", "家居家装", "美妆护肤"],
                "居住": ["房租", "物业费", "水电燃气", "网络通讯", "维修保养"],
                "娱乐": ["电影演出", "游戏", "旅行", "运动健身", "书籍"],
                "医疗": ["门诊", "药品", "体检", "保险"],
                "教育": ["课程培训", "书籍资料", "考试报名"],
                "人情": ["礼金红包", "请客送礼", "家庭支出"],
                "其他": ["手续费", "罚款", "捐赠", "其他支出"],
            }
            order = 0
            for cat, subs in seed_categories.items():
                for sub in subs:
                    session.add(
                        ExpenseCategory(
                            category=cat,
                            subcategory=sub,
                            is_active=True,
                            sort_order=order,
                        )
                    )
                    order += 1
            await session.commit()


def get_db_session() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory for scripts and background jobs."""
    return AsyncSessionLocal
