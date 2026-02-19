"""
E2E Tests for Equilibra Phase 1, 2 & 3
Uses Playwright to test Streamlit frontend + FastAPI backend
"""

import pytest
from playwright.sync_api import sync_playwright, expect
import httpx
import os
import time

BASE_URL = "http://127.0.0.1:8501"
API_URL = "http://127.0.0.1:8000/api/v1"
SCREENSHOT_DIR = "tests/screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def page(browser):
    page = browser.new_page()
    page.set_default_timeout(30000)
    yield page
    page.close()


def wait_for_streamlit(page):
    """Wait for Streamlit app to fully load (spinner gone)."""
    page.wait_for_load_state("networkidle")
    # Wait for Streamlit's main content to appear
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=15000)
    # Wait for any running spinner to disappear
    try:
        page.wait_for_selector("[data-testid='stStatusWidget']", state="hidden", timeout=10000)
    except Exception:
        pass


def navigate_via_sidebar(page, link_text):
    """Navigate to a page by clicking its sidebar link."""
    page.goto(BASE_URL)
    wait_for_streamlit(page)
    # Click the sidebar nav link matching the text
    link = page.locator(f"[data-testid='stSidebarNav'] a", has_text=link_text)
    link.click()
    wait_for_streamlit(page)


def assert_no_streamlit_error(page):
    """Assert that no Streamlit exception/error is displayed on the page."""
    error_elements = page.query_selector_all("[data-testid='stException']")
    if error_elements:
        error_text = error_elements[0].text_content()
        pytest.fail(f"Streamlit page has an error: {error_text[:300]}")


# ============ API E2E Tests ============

class TestAPIEndpoints:
    """Test backend API endpoints directly."""

    def test_health(self):
        r = httpx.get("http://127.0.0.1:8000/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_list_accounts(self):
        r = httpx.get(f"{API_URL}/core/accounts")
        assert r.status_code == 200
        accounts = r.json()
        assert isinstance(accounts, list)
        assert len(accounts) >= 1

    def test_create_account(self):
        r = httpx.post(f"{API_URL}/core/accounts", json={
            "name": "Playwright测试账户",
            "account_type": "cash",
            "initial_balance": 10000,
            "currency": "CNY",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Playwright测试账户"
        assert data["account_type"] == "cash"

    def test_list_budgets(self):
        r = httpx.get(f"{API_URL}/core/budgets")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_budget(self):
        r = httpx.post(f"{API_URL}/core/budgets", json={
            "name": "Playwright测试预算",
            "budget_type": "periodic",
            "amount": 3000,
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Playwright测试预算"
        assert data["remaining"] == "3000.0000"

    def test_dashboard(self):
        r = httpx.get(f"{API_URL}/core/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "total_assets" in data
        assert "cash_balance" in data
        assert "active_budgets" in data

    def test_create_expense(self):
        # Get first cash account
        accounts = httpx.get(f"{API_URL}/core/accounts").json()
        cash_account = next(a for a in accounts if a["account_type"] == "cash")

        r = httpx.post(f"{API_URL}/core/expenses", json={
            "account_id": cash_account["id"],
            "amount": 50,
            "expense_date": "2026-02-10",
            "category": "餐饮",
            "merchant": "Playwright测试商家",
        })
        assert r.status_code == 200
        assert r.json()["category"] == "餐饮"

    def test_create_holding(self):
        # Get investment account
        accounts = httpx.get(f"{API_URL}/core/accounts").json()
        inv_account = next(a for a in accounts if a["account_type"] == "investment")

        r = httpx.post(f"{API_URL}/core/holdings", json={
            "account_id": inv_account["id"],
            "symbol": "PW.TEST",
            "name": "Playwright测试持仓",
            "asset_type": "stock",
            "quantity": 50,
            "avg_cost": 100,
        })
        assert r.status_code == 200
        assert r.json()["symbol"] == "PW.TEST"

    def test_transfer(self):
        accounts = httpx.get(f"{API_URL}/core/accounts").json()
        cash_accounts = [a for a in accounts if a["account_type"] == "cash"]
        if len(cash_accounts) >= 2:
            r = httpx.post(f"{API_URL}/core/transfers", json={
                "from_account_id": cash_accounts[0]["id"],
                "to_account_id": cash_accounts[1]["id"],
                "amount": 100,
                "notes": "Playwright E2E转账测试",
            })
            assert r.status_code == 200
            assert r.json()["status"] == "completed"


# ============ Frontend E2E Tests ============

class TestStreamlitPages:
    """Test Streamlit frontend pages with Playwright."""

    def test_home_page(self, page):
        page.goto(BASE_URL)
        wait_for_streamlit(page)
        page.screenshot(path=f"{SCREENSHOT_DIR}/01_home.png", full_page=True)

        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert content is not None
        assert len(content) > 0
        assert "Equilibra" in content
        assert "快速导航" in content

    def test_asset_overview_page(self, page):
        navigate_via_sidebar(page, "资产总览")
        page.screenshot(path=f"{SCREENSHOT_DIR}/02_asset_overview.png", full_page=True)

        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert content is not None
        assert "资产总览" in content
        assert "资产分布" in content or "净资产" in content
        assert "¥" in content

    def test_account_management_page(self, page):
        navigate_via_sidebar(page, "账户管理")
        page.screenshot(path=f"{SCREENSHOT_DIR}/03_account_management.png", full_page=True)

        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert content is not None
        assert "账户管理" in content
        assert "现金账户" in content or "投资账户" in content or "账户统计" in content
        assert "¥" in content

    def test_budget_management_page(self, page):
        navigate_via_sidebar(page, "预算管理")
        page.screenshot(path=f"{SCREENSHOT_DIR}/04_budget_management.png", full_page=True)

        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert content is not None
        assert "预算管理" in content
        assert "进行中" in content or "暂无" in content or "预算使用率" in content or "进行中预算" in content
        assert "¥" in content or "暂无" in content

    def test_expense_entry_page(self, page):
        navigate_via_sidebar(page, "日常记账")
        page.screenshot(path=f"{SCREENSHOT_DIR}/05_expense_entry.png", full_page=True)

        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert content is not None
        assert "日常记账" in content
        assert "支付账户" in content or "支出金额" in content or "记录支出" in content
        assert "¥" in content


# ============ Phase 3 API E2E Tests ============

class TestPhase3APIEndpoints:
    """Test Phase 3 investment portfolio API endpoints."""

    def test_portfolio_endpoint(self):
        r = httpx.get(f"{API_URL}/investments/portfolio")
        assert r.status_code == 200
        data = r.json()
        assert "total_value" in data
        assert "holdings" in data
        assert isinstance(data["holdings"], list)

    def test_pnl_analysis_endpoint(self):
        r = httpx.get(f"{API_URL}/investments/pnl-analysis")
        assert r.status_code == 200
        data = r.json()
        assert "total_cost" in data
        assert "total_value" in data
        assert "total_pnl" in data
        assert "total_pnl_pct" in data
        assert "holdings" in data

    def test_create_investment_transaction(self):
        r = httpx.post(f"{API_URL}/investments/transactions", json={
            "asset_type": "stock",
            "symbol": "E2E.TEST",
            "name": "E2E测试股票",
            "transaction_type": "buy",
            "quantity": 100,
            "price": 25.50,
            "transaction_date": "2026-02-19T00:00:00",
            "market": "A股",
            "fees": 12.75,
            "currency": "CNY",
            "account_name": "E2E测试账户",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "E2E.TEST"
        assert data["transaction_type"] == "buy"
        assert data["quantity"] == 100.0

    def test_list_investment_transactions(self):
        r = httpx.get(f"{API_URL}/investments/transactions")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_portfolio_allocation_consistency(self):
        """Portfolio allocation percentages should sum to ~100%"""
        r = httpx.get(f"{API_URL}/investments/portfolio")
        assert r.status_code == 200
        data = r.json()
        nonzero = [h for h in data["holdings"] if h.get("market_value", 0) > 0]
        if nonzero:
            total_pct = sum(h["allocation_pct"] for h in nonzero)
            assert abs(total_pct - 100.0) < 0.5

    def test_pnl_calculation_consistency(self):
        """total_pnl should equal total_value - total_cost"""
        r = httpx.get(f"{API_URL}/investments/pnl-analysis")
        assert r.status_code == 200
        data = r.json()
        expected = data["total_value"] - data["total_cost"]
        assert abs(data["total_pnl"] - expected) < 0.01


# ============ Phase 3 Frontend E2E Tests ============

class TestPhase3StreamlitPages:
    """Test Phase 3 Streamlit pages with Playwright."""

    def test_investment_portfolio_page(self, page):
        navigate_via_sidebar(page, "投资组合")
        page.screenshot(path=f"{SCREENSHOT_DIR}/06_investment_portfolio.png", full_page=True)

        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert content is not None
        assert "投资组合" in content
        assert "总市值" in content or "总成本" in content or "暂无持仓" in content

    def test_investment_portfolio_has_metrics(self, page):
        navigate_via_sidebar(page, "投资组合")
        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        # Should show key metrics or empty state
        has_metrics = "总盈亏" in content or "持仓数量" in content
        has_empty = "暂无持仓" in content or "暂无" in content
        assert has_metrics or has_empty, "Portfolio page missing metrics or empty state"

    def test_investment_portfolio_sync_button(self, page):
        navigate_via_sidebar(page, "投资组合")
        assert_no_streamlit_error(page)

        # Sidebar should have sync button
        sidebar = page.text_content("[data-testid='stSidebar']")
        assert sidebar is not None
        assert "同步市值" in sidebar

    def test_trading_entry_page(self, page):
        navigate_via_sidebar(page, "交易录入")
        page.screenshot(path=f"{SCREENSHOT_DIR}/07_trading_entry.png", full_page=True)

        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert content is not None
        assert "交易录入" in content
        assert "新增交易" in content or "交易类型" in content

    def test_trading_entry_form_elements(self, page):
        navigate_via_sidebar(page, "交易录入")
        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        # Form should have key elements
        assert "交易类型" in content
        assert "资产类型" in content or "代码" in content
        assert "提交交易" in content or "交易金额" in content

    def test_trading_entry_has_history(self, page):
        navigate_via_sidebar(page, "交易录入")
        assert_no_streamlit_error(page)

        content = page.text_content("[data-testid='stAppViewContainer']")
        assert "交易历史" in content or "暂无交易" in content

    def test_sidebar_has_all_six_pages(self, page):
        """Sidebar should show all 6 pages"""
        page.goto(BASE_URL)
        wait_for_streamlit(page)

        sidebar_nav = page.text_content("[data-testid='stSidebarNav']")
        assert sidebar_nav is not None
        assert "资产总览" in sidebar_nav
        assert "账户管理" in sidebar_nav
        assert "预算管理" in sidebar_nav
        assert "日常记账" in sidebar_nav
        assert "投资组合" in sidebar_nav
        assert "交易录入" in sidebar_nav
