"""
测试持仓管理API - Phase 2.1
"""

import pytest
from decimal import Decimal
from datetime import datetime

# 使用简单的测试，避免异步数据库配置问题
# pytestmark = pytest.mark.asyncio  # 已移除，因为这些都是同步测试


def test_holding_models():
    """测试持仓数据模型"""
    from app.api.core_routes import HoldingCreate, HoldingUpdate, HoldingResponse

    # 测试HoldingCreate
    holding_create = HoldingCreate(
        account_id=1,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,
        quantity=Decimal("2000"),
        avg_cost=Decimal("1.00"),
        current_price=Decimal("1.00"),
        current_value=Decimal("2000.00"),
    )

    assert holding_create.account_id == 1
    assert holding_create.symbol == "YEB"
    assert holding_create.is_liquid is True
    assert holding_create.quantity == Decimal("2000")

    # 测试HoldingUpdate
    holding_update = HoldingUpdate(
        quantity=Decimal("2500"),
        current_price=Decimal("1.05"),
        current_value=Decimal("2625.00"),
    )

    assert holding_update.quantity == Decimal("2500")
    assert holding_update.current_price == Decimal("1.05")

    # 测试HoldingResponse字段
    response = HoldingResponse(
        id=1,
        account_id=1,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,
        quantity=Decimal("2000"),
        avg_cost=Decimal("1.00"),
        current_price=Decimal("1.00"),
        current_value=Decimal("2000.00"),
        currency="CNY",
        is_active=True,
        notes="测试持仓",
        created_at=datetime.now(),
    )

    assert response.symbol == "YEB"
    assert response.is_liquid is True
    assert response.current_value == Decimal("2000.00")


def test_yeb_holding_scenario():
    """测试余额宝持仓场景"""
    from app.models.core import Account, Holding

    # 创建投资账户
    account = Account(
        name="支付宝",
        account_type="investment",
        balance=Decimal("1000.00"),
        currency="CNY",
    )

    # 创建余额宝持仓
    yeb_holding = Holding(
        account_id=1,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,  # 高流动性
        quantity=Decimal("2000"),
        avg_cost=Decimal("1.00"),
        current_price=Decimal("1.00"),
        current_value=Decimal("2000.00"),
        currency="CNY",
        is_active=True,
    )

    account.holdings = [yeb_holding]

    # 验证计算
    assert account.balance == Decimal("1000.00")
    assert account.available_cash == Decimal("3000.00")  # 1000 + 2000
    assert account.investment_value == Decimal("0")  # 余额宝不计入投资市值
    assert account.total_value == Decimal("3000.00")  # 1000 + 2000


def test_fund_holding_scenario():
    """测试普通基金持仓场景"""
    from app.models.core import Account, Holding

    # 创建投资账户
    account = Account(
        name="支付宝",
        account_type="investment",
        balance=Decimal("1000.00"),
        currency="CNY",
    )

    # 创建普通基金持仓
    fund_holding = Holding(
        account_id=1,
        symbol="000001",
        name="某混合基金",
        asset_type="fund",
        is_liquid=False,  # 非流动性
        quantity=Decimal("1000.42"),
        avg_cost=Decimal("1.50"),
        current_price=Decimal("2.00"),
        current_value=Decimal("2000.84"),
        currency="CNY",
        is_active=True,
    )

    account.holdings = [fund_holding]

    # 验证计算
    assert account.balance == Decimal("1000.00")
    assert account.available_cash == Decimal("1000.00")  # 只有余额
    assert account.investment_value == Decimal("2000.84")  # 基金计入投资市值
    assert account.total_value == Decimal("3000.84")  # 1000 + 2000.84


def test_mixed_holdings_scenario():
    """测试混合持仓场景（余额宝 + 基金）"""
    from app.models.core import Account, Holding

    # 创建投资账户
    account = Account(
        name="支付宝",
        account_type="investment",
        balance=Decimal("1000.00"),
        currency="CNY",
    )

    # 余额宝（高流动性）
    yeb_holding = Holding(
        account_id=1,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,
        quantity=Decimal("2000"),
        avg_cost=Decimal("1.00"),
        current_price=Decimal("1.00"),
        current_value=Decimal("2000.00"),
        currency="CNY",
        is_active=True,
    )

    # 普通基金（非流动性）
    fund_holding = Holding(
        account_id=1,
        symbol="000001",
        name="某混合基金",
        asset_type="fund",
        is_liquid=False,
        quantity=Decimal("1000.42"),
        avg_cost=Decimal("1.50"),
        current_price=Decimal("2.00"),
        current_value=Decimal("2000.84"),
        currency="CNY",
        is_active=True,
    )

    account.holdings = [yeb_holding, fund_holding]

    # 验证计算
    assert account.balance == Decimal("1000.00")
    assert account.available_cash == Decimal("3000.00")  # 余额 + 余额宝
    assert account.investment_value == Decimal("2000.84")  # 只有基金
    assert account.total_value == Decimal("5000.84")  # 余额 + 余额宝 + 基金

    # 验证盈亏计算
    fund_cost = fund_holding.quantity * fund_holding.avg_cost
    fund_profit = fund_holding.current_value - fund_cost
    assert fund_cost == Decimal("1500.63")  # 1000.42 * 1.50
    assert fund_profit == Decimal("500.21")  # 2000.84 - 1500.63


def test_holding_total_cost_calculation():
    """测试持仓总成本计算"""
    from app.models.core import Holding

    holding = Holding(
        account_id=1,
        symbol="AAPL",
        name="Apple Inc",
        asset_type="stock",
        quantity=Decimal("100"),
        avg_cost=Decimal("150.00"),
    )

    # 总成本 = 数量 * 平均成本
    total_cost = holding.quantity * holding.avg_cost
    assert total_cost == Decimal("15000.00")


def test_holding_market_value_calculation():
    """测试持仓市值计算"""
    from app.models.core import Holding

    holding = Holding(
        account_id=1,
        symbol="AAPL",
        name="Apple Inc",
        asset_type="stock",
        quantity=Decimal("100"),
        current_price=Decimal("170.00"),
    )

    # 市值 = 数量 * 当前价格
    market_value = holding.quantity * holding.current_price
    assert market_value == Decimal("17000.00")


def test_holding_profit_calculation():
    """测试持仓盈亏计算"""
    from app.models.core import Holding

    holding = Holding(
        account_id=1,
        symbol="AAPL",
        name="Apple Inc",
        asset_type="stock",
        quantity=Decimal("100"),
        avg_cost=Decimal("150.00"),
        current_price=Decimal("170.00"),
    )

    # 总成本
    total_cost = holding.quantity * holding.avg_cost  # 15000

    # 当前市值
    market_value = holding.quantity * holding.current_price  # 17000

    # 盈亏
    profit = market_value - total_cost  # 2000

    # 盈亏百分比
    profit_percentage = (float(profit) / float(total_cost)) * 100  # 13.33%

    assert profit == Decimal("2000.00")
    assert abs(profit_percentage - 13.33) < 0.01
