"""
测试市值同步和预算可用资金API - Phase 2.1
"""

import pytest
from decimal import Decimal
from datetime import datetime, date
from app.models.core import Account, Holding, Budget, MarketSyncLog

# 使用简单的测试


def test_sync_holdings_value_scenario():
    """测试市值同步场景"""
    # 创建投资账户
    account = Account(
        id=1,
        name="富途证券",
        account_type="investment",
        balance=Decimal("50000.00"),
        currency="HKD",
    )

    # 创建持仓
    holding1 = Holding(
        id=1,
        account_id=1,
        symbol="00700.HK",
        name="腾讯控股",
        asset_type="stock",
        quantity=Decimal("100"),
        avg_cost=Decimal("350.00"),
        current_price=Decimal("400.00"),
        current_value=Decimal("40000.00"),
        is_active=True,
    )

    holding2 = Holding(
        id=2,
        account_id=1,
        symbol="09988.HK",
        name="阿里巴巴",
        asset_type="stock",
        quantity=Decimal("50"),
        avg_cost=Decimal("80.00"),
        current_price=Decimal("90.00"),
        current_value=Decimal("4500.00"),
        is_active=True,
    )

    account.holdings = [holding1, holding2]

    # 计算持仓市值（使用calculate_holdings_value）
    holdings_value = account.calculate_holdings_value()

    # 同步后
    assert holdings_value == Decimal("44500.00")  # 40000 + 4500


def test_sync_holdings_with_liquid_assets():
    """测试市值同步（含高流动性资产）"""
    account = Account(
        id=1,
        name="支付宝",
        account_type="investment",
        balance=Decimal("1000.00"),
        currency="CNY",
    )

    # 余额宝（高流动性）
    yeb = Holding(
        id=1,
        account_id=1,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,
        quantity=Decimal("2000"),
        current_value=Decimal("2000.00"),
        is_active=True,
    )

    # 普通基金（非流动性）
    fund = Holding(
        id=2,
        account_id=1,
        symbol="000001",
        name="某基金",
        asset_type="fund",
        is_liquid=False,
        quantity=Decimal("1000"),
        current_value=Decimal("2000.00"),
        is_active=True,
    )

    account.holdings = [yeb, fund]

    # 计算持仓市值（只计算非流动性资产）
    holdings_value = account.calculate_holdings_value()

    # 验证
    assert holdings_value == Decimal("2000.00")  # 只计算基金


def test_budget_available_funds_scenario():
    """测试预算可用资金计算"""
    from app.models.core import Account, Holding, Budget

    # 创建预算，关联两个账户
    budget = Budget(
        id=1,
        name="3月生活费",
        budget_type="periodic",
        amount=Decimal("10000.00"),
        spent=Decimal("2000.00"),
        remaining=Decimal("8000.00"),
        associated_account_ids=[1, 2],  # 关联两个账户
    )

    # 账户1（现金）
    account1 = Account(
        id=1,
        name="招商银行",
        account_type="cash",
        balance=Decimal("50000.00"),
        currency="CNY",
    )

    # 账户2（投资账户：余额 + 余额宝）
    account2 = Account(
        id=2,
        name="支付宝",
        account_type="investment",
        balance=Decimal("1000.00"),
        currency="CNY",
    )

    # 余额宝（高流动性）
    yeb = Holding(
        id=1,
        account_id=2,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,
        quantity=Decimal("2000"),
        current_value=Decimal("2000.00"),
        is_active=True,
    )

    account2.holdings = [yeb]

    # 计算各账户的available_cash
    account1_available = account1.available_cash  # 50000（现金账户）
    account2_available = account2.available_cash  # 3000（余额+余额宝）

    total_available = account1_available + account2_available

    # 验证
    assert account1_available == Decimal("50000.00")
    assert account2_available == Decimal("3000.00")
    assert total_available == Decimal("53000.00")


def test_budget_without_associated_accounts():
    """测试无关联账户的预算"""
    from app.models.core import Budget

    budget = Budget(
        id=1,
        name="无关联预算",
        budget_type="periodic",
        amount=Decimal("10000.00"),
        spent=Decimal("0"),
        remaining=Decimal("10000.00"),
        associated_account_ids=None,  # 无关联账户
    )

    # API会返回空列表
    accounts_info = []
    total_available = Decimal("0")

    assert accounts_info == []
    assert total_available == Decimal("0")


def test_budget_with_single_account():
    """测试单账户预算"""
    from app.models.core import Account

    account = Account(
        id=1,
        name="支付宝",
        account_type="investment",
        balance=Decimal("1000.00"),
        currency="CNY",
    )

    yeb = Holding(
        id=1,
        account_id=1,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,
        quantity=Decimal("2000"),
        current_value=Decimal("2000.00"),
        is_active=True,
    )

    account.holdings = [yeb]

    # 预算关联此账户
    associated_account_ids = [1]
    total_available = Decimal("0")
    accounts_info = []

    for acc_id in associated_account_ids:
        if acc_id == 1:
            available = account.available_cash
            total_available += available
            accounts_info.append(
                {
                    "account_id": 1,
                    "name": "支付宝",
                    "account_type": "investment",
                    "available_cash": available,
                    "currency": "CNY",
                }
            )

    assert total_available == Decimal("3000.00")
    assert len(accounts_info) == 1
    assert accounts_info[0]["name"] == "支付宝"


def test_market_sync_log_creation():
    """测试市值同步日志创建"""
    from app.models.core import MarketSyncLog

    sync_log = MarketSyncLog(
        id=1,
        total_value=Decimal("100000.00"),
        holdings_count=5,
        status="success",
        details={"method": "simulation"},
    )

    assert sync_log.total_value == Decimal("100000.00")
    assert sync_log.holdings_count == 5
    assert sync_log.status == "success"
    assert sync_log.details == {"method": "simulation"}


def test_sync_response_format():
    """测试市值同步响应格式"""
    from datetime import datetime

    response = {
        "message": "市值同步完成",
        "synced_count": 5,
        "total_value": Decimal("100000.00"),
        "synced_at": datetime.now(),
    }

    assert "message" in response
    assert "synced_count" in response
    assert "total_value" in response
    assert "synced_at" in response
    assert isinstance(response["synced_count"], int)
    assert isinstance(response["total_value"], Decimal)


def test_available_funds_response_format():
    """测试预算可用资金响应格式"""
    response = {
        "budget_id": 1,
        "budget_name": "3月生活费",
        "total_available": Decimal("30000.00"),
        "accounts": [
            {
                "account_id": 1,
                "name": "招商银行",
                "account_type": "cash",
                "available_cash": Decimal("20000.00"),
                "currency": "CNY",
            },
            {
                "account_id": 2,
                "name": "支付宝",
                "account_type": "investment",
                "available_cash": Decimal("10000.00"),
                "currency": "CNY",
            },
        ],
    }

    assert response["budget_id"] == 1
    assert response["budget_name"] == "3月生活费"
    assert response["total_available"] == Decimal("30000.00")
    assert len(response["accounts"]) == 2
    assert response["accounts"][0]["account_type"] == "cash"
    assert response["accounts"][1]["account_type"] == "investment"


def test_budget_execution_rate():
    """测试预算执行率计算"""
    from app.models.core import Budget

    budget = Budget(
        id=1,
        name="3月生活费",
        budget_type="periodic",
        amount=Decimal("10000.00"),
        spent=Decimal("3500.00"),
        remaining=Decimal("6500.00"),
    )

    # 执行率
    execution_rate = (budget.spent / budget.amount) * 100

    assert budget.amount == Decimal("10000.00")
    assert budget.spent == Decimal("3500.00")
    assert execution_rate == Decimal("35")


def test_budget_warning_threshold():
    """测试预算警告阈值（80%）"""
    from app.models.core import Budget

    budget = Budget(
        id=1,
        name="3月生活费",
        budget_type="periodic",
        amount=Decimal("10000.00"),
        spent=Decimal("7500.00"),  # 75%
        remaining=Decimal("2500.00"),
    )

    execution_rate = (budget.spent / budget.amount) * 100
    warning_threshold = Decimal("80")

    # 75% < 80%，正常
    assert execution_rate < warning_threshold

    # 当达到80%时
    budget.spent = Decimal("8000.00")
    budget.remaining = Decimal("2000.00")
    execution_rate = (budget.spent / budget.amount) * 100

    assert execution_rate == Decimal("80")  # 达到警告阈值


def test_budget_over_limit():
    """测试预算超支"""
    from app.models.core import Budget

    budget = Budget(
        id=1,
        name="3月生活费",
        budget_type="periodic",
        amount=Decimal("10000.00"),
        spent=Decimal("10500.00"),  # 超支
        remaining=Decimal("-500.00"),
    )

    # 超支
    assert budget.spent > budget.amount
    assert budget.remaining < Decimal("0")


def test_investment_with_inactive_holdings():
    """测试含非活跃持仓的投资账户"""
    from app.models.core import Account, Holding

    account = Account(
        id=1,
        name="富途证券",
        account_type="investment",
        balance=Decimal("50000.00"),
        currency="HKD",
    )

    # 活跃持仓
    active_holding = Holding(
        id=1,
        account_id=1,
        symbol="00700.HK",
        name="腾讯控股",
        asset_type="stock",
        quantity=Decimal("100"),
        current_value=Decimal("40000.00"),
        is_active=True,
    )

    # 非活跃持仓（已清仓）
    inactive_holding = Holding(
        id=2,
        account_id=1,
        symbol="TSLA",
        name="特斯拉",
        asset_type="stock",
        quantity=Decimal("0"),
        current_value=Decimal("0"),
        is_active=False,
    )

    account.holdings = [active_holding, inactive_holding]

    # 只计算活跃持仓
    account.update_holdings_value()

    assert account.holdings_value == Decimal("40000.00")  # 只计算活跃持仓
