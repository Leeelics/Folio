# Services Layer - AGENTS.md

> **Domain Logic & External Integrations** | 15 service modules

## Service Organization

```
app/services/
├── asset_manager.py          # OKX integration, exchange rates, total assets
├── investment_manager.py     # Portfolio CRUD, P&L calculations
├── brokerage_account_service.py  # Unified account view (cash + holdings)
├── stock_client.py           # Market data: Tushare + AkShare
├── stock_position_manager.py # Stock position tracking
├── okx_client.py             # OKX API wrapper (CCXT)
├── exchange_rate_service.py  # Currency conversion
├── risk_controller.py        # Portfolio risk metrics
├── strategy_engine.py        # AI analysis & recommendations
├── trade_executor.py         # Order execution logic
├── vector_store.py           # pgvector embeddings
├── import_service.py         # CSV/data import
├── export_service.py         # Report generation
└── report_service.py         # Analytics & summaries
```

## Key Services

### AssetManager
- Fetches OKX balances via CCXT
- Calculates total assets (CNY converted)
- Computes asset distribution for charts

### InvestmentManager
- Transaction CRUD with automatic holding updates
- Moving weighted average cost calculation
- Fund product management

### BrokerageAccountService
- Unified cash + holding views
- Transaction cascade updates
- Multi-currency support

## External API Integration Patterns

### Market Data (StockClient)
```python
# Tushare primary (A/H shares), AkShare fallback
# Rate limit: ~0.1s/query
# Cache: 30s TTL with async locks
```

### Crypto (OKX via CCXT)
```python
# CCXT async client
# Always close connections in finally block
# Log errors, return empty dict on failure
```

### Error Handling
```python
try:
    data = await fetch_external()
except Exception as e:
    logger.error(f"Provider failed: {e}")
    return fallback_or_empty()
```

## Currency Conversion

```python
# Hardcoded rates (simplified)
EXCHANGE_RATES = {
    "CNY": Decimal("1.0"),
    "HKD": Decimal("0.92"),
    "USD": Decimal("7.2"),
    "USDT": Decimal("7.2"),
}
```

## Conventions

- All services use `AsyncSession` for DB operations
- Methods are `async` when calling external APIs
- Domain errors logged, not raised to API layer
- Dataclasses for view models (e.g., `UnifiedAccountView`)
