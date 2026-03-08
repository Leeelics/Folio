# API Routes - Folio

> Feature-based routing for FastAPI endpoints.

## Route Files (8 total)

| File | Domain | Description |
|------|--------|-------------|
| `core_routes.py` | Core CRUD | Accounts, holdings, budgets, expenses, transfers |
| `investment_routes.py` | Investment | Transactions, portfolio, P&L, fund products |
| `stock_routes.py` | Market Data | Stock quotes, klines, watchlists |
| `brokerage_routes.py` | Brokerage | Platform accounts, unified position view |
| `report_routes.py` | Reports | Asset allocation, period reports |
| `export_routes.py` | Export | CSV export for all data types |
| `import_routes.py` | Import | CSV import, bulk data ingestion |
| `routes.py` | Legacy | Original aggregator routes |

## Router Pattern

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

router = APIRouter(prefix="/core", tags=["核心功能"])

@router.post("/accounts")
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db)
):
    ...
```

## Registration (main.py)

```python
from app.api.core_routes import router as core_router

app.include_router(core_router, prefix="/api/v1")
```

## Dependencies

- `get_db()` - AsyncSession injection with auto-commit/rollback
- All routes use async/await with SQLAlchemy 2.0

## Pydantic Models

Request/response schemas defined inline per route file:

```python
class AccountCreate(BaseModel):
    name: str
    account_type: str
    initial_balance: Decimal = Field(Decimal("0"))
```

## Conventions

- Prefixes group related functionality (`/core`, `/investments`, `/stocks`)
- Tags organize OpenAPI docs
- Use `selectinload` for relationships
- HTTP exceptions: 404 for not found, 400 for bad input
