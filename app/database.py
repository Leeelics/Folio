from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=True,
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
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_db_session() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory for scripts and background jobs."""
    return AsyncSessionLocal
