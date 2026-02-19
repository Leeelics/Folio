"""
测试API端点 - 账户管理
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.main import app
from app.database import get_db, Base
from app.models.core import Account, Holding, Budget, Expense
import tempfile
import os

# 使用文件SQLite数据库进行测试，避免内存数据库连接问题
temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{temp_db_file.name}"

# 创建测试引擎 - 使用StaticPool确保连接复用
test_engine = create_async_engine(
    TEST_DATABASE_URL, poolclass=StaticPool, connect_args={"check_same_thread": False}
)
test_async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    """覆盖数据库依赖，使用测试数据库"""
    async with test_async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """设置测试数据库 - 整个测试会话只创建一次"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 清理
    await test_engine.dispose()
    try:
        os.unlink(temp_db_file.name)
    except:
        pass


@pytest_asyncio.fixture(scope="function")
async def client():
    """创建测试客户端"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """提供数据库会话用于测试数据准备"""
    async with test_async_session() as session:
        yield session


pytestmark = pytest.mark.asyncio


class TestAccountAPI:
    """测试账户API端点"""

    async def test_create_cash_account(self, client):
        """测试创建现金账户"""
        response = await client.post(
            "/api/v1/core/accounts",
            json={
                "name": "测试现金账户",
                "account_type": "cash",
                "institution": "招商银行",
                "initial_balance": "10000.00",
                "currency": "CNY",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "测试现金账户"
        assert data["account_type"] == "cash"
        assert data["balance"] == "10000.0000"
        assert data["total_value"] == "10000.0000"
        assert data["holdings_value"] is None  # 现金账户无持仓

    async def test_create_investment_account(self, client):
        """测试创建投资账户"""
        response = await client.post(
            "/api/v1/core/accounts",
            json={
                "name": "测试证券账户",
                "account_type": "investment",
                "institution": "富途",
                "initial_balance": "50000.00",
                "currency": "HKD",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "测试证券账户"
        assert data["account_type"] == "investment"
        assert data["balance"] == "50000.0000"  # 可用现金
        assert data["total_value"] == "50000.0000"  # 无持仓时等于balance
        assert data["holdings_value"] == "0"  # 初始持仓为0

    async def test_get_account_with_holdings(self, client, db_session):
        """测试获取包含持仓的投资账户"""
        # 先创建投资账户
        create_response = await client.post(
            "/api/v1/core/accounts",
            json={
                "name": "富途证券",
                "account_type": "investment",
                "institution": "富途",
                "initial_balance": "50000.00",
                "currency": "HKD",
            },
        )
        account_id = create_response.json()["id"]

        # 手动添加持仓（通过数据库直接操作，因为还没有持仓API）
        holding = Holding(
            account_id=account_id,
            symbol="00700.HK",
            name="腾讯控股",
            asset_type="stock",
            quantity=Decimal("100"),
            avg_cost=Decimal("300.00"),
            current_price=Decimal("400.00"),
            current_value=Decimal("40000.00"),
            currency="HKD",
            is_active=True,
        )
        db_session.add(holding)
        await db_session.commit()

        # 获取账户详情
        response = await client.get(f"/api/v1/core/accounts/{account_id}")
        assert response.status_code == 200
        data = response.json()

        # 验证计算字段
        assert data["balance"] == "50000.0000"  # 可用现金
        assert data["holdings_value"] == "40000.0000"  # 持仓市值
        assert data["total_value"] == "90000.0000"  # 总资产

    async def test_list_accounts_mixed_types(self, client):
        """测试获取混合类型账户列表"""
        # 创建现金账户
        await client.post(
            "/api/v1/core/accounts",
            json={
                "name": "招商银行",
                "account_type": "cash",
                "initial_balance": "10000.00",
                "currency": "CNY",
            },
        )

        # 创建投资账户
        await client.post(
            "/api/v1/core/accounts",
            json={
                "name": "富途证券",
                "account_type": "investment",
                "initial_balance": "50000.00",
                "currency": "HKD",
            },
        )

        # 获取账户列表
        response = await client.get("/api/v1/core/accounts")
        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 2

        # 验证现金账户
        cash_accounts = [acc for acc in data if acc["account_type"] == "cash"]
        assert len(cash_accounts) > 0
        assert cash_accounts[0]["total_value"] is not None
        assert cash_accounts[0]["holdings_value"] is None

        # 验证投资账户
        inv_accounts = [acc for acc in data if acc["account_type"] == "investment"]
        assert len(inv_accounts) > 0
        assert inv_accounts[0]["total_value"] is not None
        assert inv_accounts[0]["holdings_value"] is not None


class TestDashboardAPI:
    """测试仪表盘API"""

    async def test_dashboard_with_mixed_accounts(self, client):
        """测试包含现金和投资账户的仪表盘"""
        # 创建现金账户
        cash_response = await client.post(
            "/api/v1/core/accounts",
            json={
                "name": "招商银行",
                "account_type": "cash",
                "initial_balance": "50000.00",
                "currency": "CNY",
            },
        )
        assert cash_response.status_code == 200

        # 创建投资账户
        inv_response = await client.post(
            "/api/v1/core/accounts",
            json={
                "name": "富途证券",
                "account_type": "investment",
                "initial_balance": "30000.00",
                "currency": "HKD",
            },
        )
        assert inv_response.status_code == 200

        # 创建预算
        budget_response = await client.post(
            "/api/v1/core/budgets",
            json={
                "name": "3月生活费",
                "budget_type": "periodic",
                "amount": "10000.00",
                "period_start": str(date.today()),
                "period_end": str(date.today()),
            },
        )
        assert budget_response.status_code == 200

        # 获取仪表盘数据
        response = await client.get("/api/v1/core/dashboard")
        assert response.status_code == 200
        data = response.json()

        # 验证仪表盘返回正确的字段类型和结构
        assert "total_assets" in data
        assert "cash_balance" in data
        assert "investment_value" in data
        assert "active_budgets" in data

        # 验证数值是字符串格式
        assert isinstance(data["total_assets"], str)
        assert isinstance(data["cash_balance"], str)
        assert isinstance(data["investment_value"], str)

        # 验证预算已创建
        assert len(data["active_budgets"]) >= 1
        budget_names = [b["name"] for b in data["active_budgets"]]
        assert "3月生活费" in budget_names
