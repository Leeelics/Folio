# Repository Guidelines

## Project Structure & Module Organization
- Backend code lives in `app/` (`main.py`, `config.py`, `database.py`, `models/`, `services/`, `api/`).
- Streamlit UI lives in `streamlit_app/` (`Home.py`, `pages/`).
- Infrastructure and data are defined in `docker-compose.yml`, `Dockerfile`, and `init.sql`.
- Keep new backend modules under `app/services/` or `app/api/` and new UIs under `streamlit_app/pages/`.

## Build, Test, and Development Commands
- Install dependencies: `uv sync`
- Run API locally: `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Run Streamlit UI: `uv run streamlit run streamlit_app/Home.py`
- Run tests (when added): `uv run pytest`
- Format / lint / type-check: `uv run black app/`, `uv run ruff check app/`, `uv run mypy app/`

## Coding Style & Naming Conventions
- Python 3.11+, 4-space indentation, line length 100 (enforced by Black and Ruff).
- Prefer type hints for new functions and public interfaces.
- Name modules and packages in `snake_case`; classes in `PascalCase`; functions and variables in `snake_case`.
- Group domain logic in `app/services/` and keep `app/api/routes.py` focused on request/response wiring.

## Testing Guidelines
- Use `pytest` (and `pytest-asyncio` where needed); place tests under `tests/` mirroring the `app/` structure.
- Name test files `test_*.py` and test functions `test_<behavior>` (e.g., `test_calculate_risk_level`).
- Run `uv run pytest` before submitting changes; add tests for new features and bug fixes where practical.

## Commit & Pull Request Guidelines
- Use clear, imperative commit messages (e.g., `Add risk controller for wedding budget`, `Fix asset sync for OKX`).
- For pull requests, include: purpose summary, key changes, how to run or test, and any config/env updates.
- If you change API contracts or database schema, update `README.md`, `init.sql`, and any affected clients.

## Security & Configuration
- Never commit real secrets; use `.env` (see `.env.example`) and Docker/host-level secrets.
- Be cautious with external APIs (OKX, OpenAI, AkShare); handle errors and timeouts explicitly in `app/services/`.

