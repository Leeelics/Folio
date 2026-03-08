# Folio - Repository Guidelines

> **Personal Financial Management System** | FastAPI + Streamlit + PostgreSQL | Python 3.11+

## Quick Reference

| Action | Command |
|--------|---------|
| Install deps | `uv sync` |
| Run API | `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` |
| Run UI | `uv run streamlit run streamlit_app/Home.py` |
| Run tests | `uv run pytest` |
| Format | `uv run black app/ && uv run ruff check app/` |
| Type check | `uv run mypy app/` |

## Project Structure

```
folio/
├── app/                    # Backend API
│   ├── api/               # API routes (see app/api/AGENTS.md)
│   ├── services/          # Business logic (see app/services/AGENTS.md)
│   ├── models/            # SQLAlchemy models (see app/models/AGENTS.md)
│   ├── main.py            # FastAPI entry point
│   ├── config.py          # Settings (pydantic-settings)
│   └── database.py        # DB connection + init
├── streamlit_app/         # Frontend UI
│   ├── pages/             # Page modules (see streamlit_app/pages/AGENTS.md)
│   ├── Home.py            # Entry point
│   └── api_client.py      # HTTP client (140+ methods)
├── tests/                 # Test suite (see tests/AGENTS.md)
├── scripts/               # Shell helpers (dev.sh, setup.sh)
├── docker-compose.yml     # Postgres + App + Streamlit
├── Dockerfile             # Multi-stage build
├── init.sql               # Database schema
└── pyproject.toml         # uv config
```

## Subdirectory Guides

- [`app/api/`](./app/api/AGENTS.md) - API route organization & patterns
- [`app/services/`](./app/services/AGENTS.md) - Service layer conventions
- [`app/models/`](./app/models/AGENTS.md) - Domain model patterns
- [`streamlit_app/pages/`](./streamlit_app/pages/AGENTS.md) - UI page patterns
- [`tests/`](./tests/AGENTS.md) - Testing patterns & fixtures

## Architecture Patterns

### Backend (FastAPI)
- **Routes**: Feature-based organization (`core_routes.py`, `investment_routes.py`)
- **Services**: Domain logic separation (`asset_manager.py`, `investment_manager.py`)
- **Models**: Domain-driven split (`core.py`, `investment.py`, `brokerage.py`)
- **Dependencies**: `get_db()` for AsyncSession injection

### Frontend (Streamlit)
- **Pages**: Numbered naming (`1_Assets.py` → `7_Reports.py`) for menu ordering
- **API Client**: Centralized in `api_client.py` (auto-generated from OpenAPI)
- **State**: Use `st.session_state` for cross-page data

### Database
- **ORM**: SQLAlchemy 2.0 with asyncpg
- **Tables**: 10 core tables (accounts, holdings, transactions, budgets, expenses, etc.)
- **Vector**: pgvector for market news embeddings

## Conventions

### Code Style
- Python 3.11+, 4-space indentation
- Line length: 100 (Black + Ruff enforced)
- Type hints for public interfaces
- `snake_case` modules/functions, `PascalCase` classes

### File Organization
- New backend modules → `app/services/` or `app/api/`
- New UI pages → `streamlit_app/pages/` (follow numbering)
- API changes → Update `README.md` + affected Streamlit pages

### Environment
- Use `.env` for local dev (copied from `.env.example`)
- Never commit secrets
- Required: `DATABASE_URL`, `TUSHARE_TOKEN`, `OPENAI_API_KEY`

## Testing Strategy

| Test Type | Files | Pattern |
|-----------|-------|---------|
| Unit | `test_models.py`, `test_holdings.py` | Synchronous, no DB |
| Integration | `test_api.py`, `test_portfolio.py` | Async + SQLite test DB |
| E2E | `test_e2e.py` | Playwright + live services |

## Known Issues

1. **Broken CLI entry point**: `pyproject.toml` defines `folio = "app.main:main"` but no `main()` function exists
2. **Archive pollution**: `streamlit_app/pages/_archive/` contains old pages

## Development Workflow

```bash
# First setup
bash scripts/setup.sh

# Daily dev
bash scripts/dev.sh              # Both backend + frontend
bash scripts/dev.sh backend      # API only
bash scripts/dev.sh frontend     # UI only

# Before commit
uv run black app/
uv run ruff check app/
uv run mypy app/
uv run pytest
```

## External APIs

| Service | Usage | Module |
|---------|-------|--------|
| OKX | Crypto balance sync | `app/services/asset_manager.py` |
| Tushare | A-share/HK stock prices | `app/services/stock_client.py` |
| AkShare | Fallback market data | `app/services/stock_client.py` |
| OpenAI | AI analysis | `app/services/strategy_engine.py` |

## Phase Status

- ✅ Phase 1: Core models + API
- ✅ Phase 2: Frontend + budget + expenses
- ✅ Phase 3: Portfolio + Tushare integration
- ✅ Phase 4: Reports + CSV import/export
