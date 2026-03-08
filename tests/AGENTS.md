# Tests - Testing Patterns

> Testing strategy and conventions for Folio

## Test Files (8 Total)

| File | Type | Purpose |
|------|------|---------|
| `test_models.py` | Unit | Core model calculations |
| `test_holdings.py` | Unit | Holding scenarios, schema validation |
| `test_api.py` | Integration | Async API endpoint tests |
| `test_portfolio.py` | Integration | Portfolio/P&L endpoint tests |
| `test_transfers.py` | Integration | Transfer logic |
| `test_market_sync.py` | Integration | Market sync tests |
| `test_expense_extended.py` | Integration | Expense API scenarios |
| `test_e2e.py` | E2E | Playwright browser tests |

## Two-Tier Testing

**Unit Tests** (Sync, No DB): Pure model logic without database.

**Integration Tests** (Async + SQLite): File-based SQLite with aiosqlite:
```python
temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_engine = create_async_engine(
    f"sqlite+aiosqlite:///{temp_db.name}",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False}
)
```

## Async Test DB Pattern

```python
async def override_get_db():
    async with test_session() as session:
        yield session
app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
```

## Playwright E2E

```python
@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

def test_home_page(page):
    page.goto("http://127.0.0.1:8501")
    page.screenshot(path="tests/screenshots/01_home.png")
```

## Fixture Organization

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `setup_database` | session | One-time DB creation |
| `client` | function | Fresh HTTP client |
| `db_session` | function | Direct DB access |
| `browser` | module | Shared Playwright instance |
| `page` | function | Fresh browser context |

## Conventions

- `pytestmark = pytest.mark.asyncio` for async files
- Use `NamedTemporaryFile`, not `:memory:`
- E2E captures screenshots for visual regression
