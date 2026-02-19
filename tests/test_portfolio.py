"""
Phase 3 单元测试 - Portfolio 和 PnL Analysis 端点
使用 SQLite mock 数据库，验证端点响应结构和计算逻辑
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models.core import Account, Holding
from app.models.investment import InvestmentHolding, InvestmentTransaction
import tempfile
import os

# 独立测试数据库
_temp_db = tempfile.NamedTemporaryFile(suffix="_portfolio.db", delete=False)
_DB_URL = f"sqlite+aiosqlite:///{_temp_db.name}"

_engine = create_async_engine(
    _DB_URL, poolclass=StaticPool, connect_args={"check_same_thread": False}
)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_portfolio_db():
    """创建表结构，设置 DB override，测试结束后恢复"""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    # 恢复原始 override，避免影响其他测试模块
    if _prev is not None:
        app.dependency_overrides[get_db] = _prev
    else:
        app.dependency_overrides.pop(get_db, None)
    await _engine.dispose()
    try:
        os.unlink(_temp_db.name)
    except OSError:
        pass


@pytest_asyncio.fixture(scope="function")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with _session_factory() as session:
        yield session


pytestmark = pytest.mark.asyncio


# ============ Helpers ============

async def _create_inv_account(client: AsyncClient, name: str) -> dict:
    resp = await client.post("/api/v1/core/accounts", json={
        "name": name,
        "account_type": "investment",
        "institution": "测试券商",
        "initial_balance": "100000.00",
        "currency": "CNY",
    })
    assert resp.status_code == 200
    return resp.json()


async def _seed_core_holdings(db: AsyncSession, account_id: int):
    """插入 core holdings（Holding 表）"""
    for h_data in [
        {"symbol": "600519.SH", "name": "贵州茅台", "asset_type": "stock",
         "quantity": Decimal("100"), "avg_cost": Decimal("1800"),
         "total_cost": Decimal("180000"), "current_price": Decimal("2000"),
         "current_value": Decimal("200000"), "is_liquid": False},
        {"symbol": "000858.SZ", "name": "五粮液", "asset_type": "stock",
         "quantity": Decimal("200"), "avg_cost": Decimal("150"),
         "total_cost": Decimal("30000"), "current_price": Decimal("160"),
         "current_value": Decimal("32000"), "is_liquid": False},
    ]:
        db.add(Holding(account_id=account_id, currency="CNY", is_active=True, **h_data))
    await db.commit()


async def _seed_investment_holdings(db: AsyncSession):
    """插入 investment_holdings 表数据"""
    for data in [
        {"symbol": "600519.SH", "name": "贵州茅台", "market": "A股",
         "quantity": Decimal("100"), "avg_cost": Decimal("1800"),
         "total_cost": Decimal("180000"), "account_name": "Portfolio单测账户"},
        {"symbol": "000858.SZ", "name": "五粮液", "market": "A股",
         "quantity": Decimal("200"), "avg_cost": Decimal("150"),
         "total_cost": Decimal("30000"), "account_name": "Portfolio单测账户"},
    ]:
        db.add(InvestmentHolding(asset_type="stock", currency="CNY", **data))
    await db.commit()


async def _seed_investment_transactions(db: AsyncSession):
    """插入 investment_transactions 表数据"""
    for data in [
        {"symbol": "600519.SH", "name": "贵州茅台", "transaction_type": "buy",
         "quantity": Decimal("100"), "price": Decimal("1800"),
         "amount": Decimal("180000"), "fees": Decimal("90"),
         "transaction_date": datetime(2025, 1, 15)},
        {"symbol": "000858.SZ", "name": "五粮液", "transaction_type": "buy",
         "quantity": Decimal("200"), "price": Decimal("150"),
         "amount": Decimal("30000"), "fees": Decimal("15"),
         "transaction_date": datetime(2025, 3, 20)},
    ]:
        db.add(InvestmentTransaction(
            asset_type="stock", market="A股", currency="CNY",
            account_name="Portfolio单测账户", **data,
        ))
    await db.commit()


# ============ Portfolio 端点测试 ============

class TestPortfolioEndpoint:
    """测试 GET /api/v1/investments/portfolio"""

    async def test_portfolio_returns_200(self, client):
        """端点可达且返回 200"""
        resp = await client.get("/api/v1/investments/portfolio")
        if resp.status_code == 404:
            pytest.skip("Portfolio endpoint not yet implemented")
        assert resp.status_code == 200

    async def test_portfolio_response_structure(self, client):
        """响应包含必要的顶层字段"""
        resp = await client.get("/api/v1/investments/portfolio")
        if resp.status_code == 404:
            pytest.skip("Portfolio endpoint not yet implemented")
        data = resp.json()
        assert "total_value" in data
        assert "holdings" in data
        assert isinstance(data["holdings"], list)

    async def test_portfolio_holding_fields(self, client, db_session):
        """每个持仓包含必要字段"""
        account = await _create_inv_account(client, "Portfolio单测账户")
        await _seed_core_holdings(db_session, account["id"])
        await _seed_investment_holdings(db_session)

        resp = await client.get("/api/v1/investments/portfolio")
        if resp.status_code == 404:
            pytest.skip("Portfolio endpoint not yet implemented")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["holdings"]) > 0

        required_fields = {"symbol", "name", "quantity", "current_price", "market_value", "allocation_pct"}
        for h in data["holdings"]:
            missing = required_fields - set(h.keys())
            assert not missing, f"Holding {h.get('symbol')} missing fields: {missing}"

    async def test_portfolio_allocation_sums_to_100(self, client):
        """分配比例之和应接近 100%（仅当有非零市值持仓时）"""
        resp = await client.get("/api/v1/investments/portfolio")
        if resp.status_code == 404:
            pytest.skip("Portfolio endpoint not yet implemented")
        data = resp.json()
        nonzero = [h for h in data["holdings"] if h["market_value"] > 0]
        if nonzero:
            total_pct = sum(h["allocation_pct"] for h in nonzero)
            assert abs(total_pct - 100.0) < 0.5, f"Allocation sum {total_pct} != ~100%"

    async def test_portfolio_total_value_matches_holdings_sum(self, client):
        """total_value 应等于所有持仓 market_value 之和"""
        resp = await client.get("/api/v1/investments/portfolio")
        if resp.status_code == 404:
            pytest.skip("Portfolio endpoint not yet implemented")
        data = resp.json()
        if data["holdings"]:
            holdings_sum = sum(h["market_value"] for h in data["holdings"])
            assert abs(data["total_value"] - holdings_sum) < 0.01, \
                f"total_value {data['total_value']} != sum {holdings_sum}"

    async def test_portfolio_market_value_positive(self, client):
        """有持仓时 market_value >= 0"""
        resp = await client.get("/api/v1/investments/portfolio")
        if resp.status_code == 404:
            pytest.skip("Portfolio endpoint not yet implemented")
        data = resp.json()
        for h in data["holdings"]:
            assert h["market_value"] >= 0, f"{h['symbol']} has negative market_value"


# ============ PnL Analysis 端点测试 ============

class TestPnLAnalysisEndpoint:
    """测试 GET /api/v1/investments/pnl-analysis"""

    async def test_pnl_returns_200(self, client):
        """端点可达且返回 200"""
        resp = await client.get("/api/v1/investments/pnl-analysis")
        if resp.status_code == 404:
            pytest.skip("PnL analysis endpoint not yet implemented")
        assert resp.status_code == 200

    async def test_pnl_response_structure(self, client):
        """响应包含必要的顶层字段"""
        resp = await client.get("/api/v1/investments/pnl-analysis")
        if resp.status_code == 404:
            pytest.skip("PnL analysis endpoint not yet implemented")
        data = resp.json()
        for field in ("total_cost", "total_value", "total_pnl", "total_pnl_pct", "holdings"):
            assert field in data, f"Missing field: {field}"
        assert isinstance(data["holdings"], list)

    async def test_pnl_holding_fields(self, client, db_session):
        """每个持仓包含盈亏相关字段"""
        # 确保有数据（可能已被前面的测试 seed）
        await _seed_investment_transactions(db_session)

        resp = await client.get("/api/v1/investments/pnl-analysis")
        if resp.status_code == 404:
            pytest.skip("PnL analysis endpoint not yet implemented")
        data = resp.json()

        if data["holdings"]:
            required_fields = {"symbol", "name", "cost_basis", "current_value", "pnl", "pnl_pct"}
            for h in data["holdings"]:
                missing = required_fields - set(h.keys())
                assert not missing, f"Holding {h.get('symbol')} missing fields: {missing}"

    async def test_pnl_total_consistency(self, client):
        """total_pnl = total_value - total_cost"""
        resp = await client.get("/api/v1/investments/pnl-analysis")
        if resp.status_code == 404:
            pytest.skip("PnL analysis endpoint not yet implemented")
        data = resp.json()
        expected_pnl = data["total_value"] - data["total_cost"]
        assert abs(data["total_pnl"] - expected_pnl) < 0.01, \
            f"total_pnl {data['total_pnl']} != {expected_pnl}"

    async def test_pnl_pct_calculation(self, client):
        """total_pnl_pct = total_pnl / total_cost * 100（当 total_cost > 0）"""
        resp = await client.get("/api/v1/investments/pnl-analysis")
        if resp.status_code == 404:
            pytest.skip("PnL analysis endpoint not yet implemented")
        data = resp.json()
        if data["total_cost"] > 0:
            expected_pct = data["total_pnl"] / data["total_cost"] * 100
            assert abs(data["total_pnl_pct"] - expected_pct) < 0.5, \
                f"total_pnl_pct {data['total_pnl_pct']} != {expected_pct}"

    async def test_pnl_holdings_sum_equals_total(self, client):
        """各持仓 pnl 之和应等于 total_pnl"""
        resp = await client.get("/api/v1/investments/pnl-analysis")
        if resp.status_code == 404:
            pytest.skip("PnL analysis endpoint not yet implemented")
        data = resp.json()
        if data["holdings"]:
            holdings_pnl = sum(h["pnl"] for h in data["holdings"])
            assert abs(data["total_pnl"] - holdings_pnl) < 0.01, \
                f"Sum of holdings pnl {holdings_pnl} != total_pnl {data['total_pnl']}"

    async def test_pnl_cost_basis_positive(self, client):
        """cost_basis 应 >= 0"""
        resp = await client.get("/api/v1/investments/pnl-analysis")
        if resp.status_code == 404:
            pytest.skip("PnL analysis endpoint not yet implemented")
        data = resp.json()
        for h in data["holdings"]:
            assert h["cost_basis"] >= 0, f"{h['symbol']} has negative cost_basis"
