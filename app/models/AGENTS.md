# Domain Models

> **SQLAlchemy 2.0 domain model organization guide**

## Philosophy

Domain-driven split replaces the original single `schemas.py`. Each file owns one bounded context.

## File Organization

| File | Domain | Key Entities |
|------|--------|--------------|
| `core.py` | Core entities | Account, Holding, Budget, Expense, Liability |
| `investment.py` | Investment operations | InvestmentTransaction, FundProduct, InvestmentHolding, AllocationTarget, RiskAlert |
| `brokerage.py` | Brokerage platform | BrokerageAccount, PortfolioHolding, PortfolioTransaction, CashFlow |
| `stock.py` | Stock data | StockPosition, StockWatchlist, StockQuoteCache |
| `trading.py` | Trading execution | StrategyConfig, Trade |
| `schemas.py` | Legacy models | Asset, Transaction, MarketNews (original) |

## SQLAlchemy 2.0 Pattern

```python
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Account(Base):
    __tablename__ = "accounts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
```

## Key Relationships

```python
# Account has many Holdings
class Account(Base):
    holdings: Mapped[List["Holding"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

class Holding(Base):
    account: Mapped["Account"] = relationship(back_populates="holdings")
```

## Base Class

All models inherit from `Base` defined in `app/database.py`:

```python
from app.database import Base
```

## Type Patterns

- Primary keys: `Mapped[int] = mapped_column(primary_key=True, index=True)`
- Required strings: `Mapped[str] = mapped_column(String(100), nullable=False)`
- Optional fields: `Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)`
- Timestamps: `Mapped[datetime] = mapped_column(DateTime, server_default=func.now())`
- JSON data: `Mapped[Optional[list]] = mapped_column(JSON, nullable=True)`

## Migration Note

Table DDL lives in `init.sql`. Models define ORM mapping only, not schema.
