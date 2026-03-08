# Streamlit Pages Guide

> Personal finance management UI built with Streamlit.

## Page Organization

### Numbered Naming Convention

Prefix controls sidebar menu order:

| File | Purpose |
|------|---------|
| `1_Assets.py` | Asset overview dashboard |
| `2_Accounts.py` | Account management |
| `3_Budgets.py` | Budget tracking |
| `4_Expenses.py` | Expense entry |
| `5_Portfolio.py` | Investment portfolio |
| `6_Trades.py` | Trade recording |
| `7_Reports.py` | Reports and data management |

## Page Structure Template

```python
import streamlit as st
import plotly.express as px
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import FolioAPIClient

st.set_page_config(page_title="Title", page_icon="📊", layout="wide")


@st.cache_resource
def get_api_client():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    return FolioAPIClient(base_url=api_url)


api_client = get_api_client()
```

## Key Patterns

### API Client
- Import `FolioAPIClient` from parent directory
- Use `@st.cache_resource` for singleton pattern
- API base URL from `API_URL` env var, default `localhost:8000`

### Session State
- Use `st.session_state` for cross-page data persistence
- Common keys: `show_create_account`, `show_transfer`, `sync_result`
- Clear cache with `st.cache_data.clear()` after mutations

### Currency Formatting
```python
def format_currency(amount, currency="CNY"):
    symbols = {"CNY": "¥", "USD": "$", "HKD": "HK$"}
    return f"{symbols.get(currency, currency)}{float(amount or 0):,.2f}"
```

### Visualizations
- **plotly**: Charts and graphs (`px.pie`, `px.bar`, `px.line`)
- **pandas**: Data manipulation for charts

## Warnings

### Archive Folder
`_archive/` contains old page versions. Streamlit may still detect Python files here.
Keep or remove - do not leave imports that could conflict.

### Path Imports
All pages must add parent directory to `sys.path` before importing `api_client`:
```python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

## Dependencies

- `streamlit`: UI framework
- `plotly`: Interactive charts
- `pandas`: Data processing
- Custom: `api_client.FolioAPIClient` (140+ API methods)
