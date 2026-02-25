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

    # Seed expense categories only if table is empty (preserve user customizations)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func as sa_func

        count = await session.scalar(
            select(sa_func.count()).select_from(ExpenseCategory)
        )
        if count == 0:
            seed_categories = {
                "餐饮": ["三餐", "买菜", "饮品", "零食"],
                "交通": ["公交地铁", "打车", "停车费", "油钱", "高速费"],
                "购物": ["日用品", "服饰", "护肤", "数码", "电器", "数字产品", "纪念品"],
                "居家": ["话费", "网费", "房租", "水费", "电费"],
                "社交": ["送礼", "餐饮", "活动"],
                "医疗": ["药品", "治疗", "保险"],
                "娱乐": ["电影", "健身", "游戏", "旅游"],
                "学习": ["书籍", "培训", "网课"],
                "宠物": ["吃喝", "服饰", "医疗"],
                "其他": ["其他支出"],
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
