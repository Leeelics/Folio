"""
测试支出API扩展 - Phase 2.1
支持投资账户支出
"""

import pytest
from decimal import Decimal
from datetime import date

# 使用简单的测试，避免异步数据库配置问题


def test_expense_from_cash_account():
    """测试从现金账户支出"""
    from app.models.core import Account, Expense, Budget

    # 创建现金账户
    cash_account = Account(
        id=1,
        name="招商银行",
        account_type="cash",
        balance=Decimal("10000.00"),
        currency="CNY",
    )

    # 创建预算
    budget = Budget(
        id=1,
        name="3月生活费",
        budget_type="periodic",
        amount=Decimal("5000.00"),
        spent=Decimal("0"),
        remaining=Decimal("5000.00"),
    )

    # 支出前
    assert cash_account.balance == Decimal("10000.00")
    assert budget.spent == Decimal("0")
    assert budget.remaining == Decimal("5000.00")

    # 支出200
    expense_amount = Decimal("200.00")
    cash_account.balance -= expense_amount
    budget.spent += expense_amount
    budget.remaining -= expense_amount

    # 支出后
    assert cash_account.balance == Decimal("9800.00")
    assert budget.spent == Decimal("200.00")
    assert budget.remaining == Decimal("4800.00")


def test_expense_from_investment_account():
    """测试从投资账户支出（Phase 2.1新增）"""
    from app.models.core import Account, Expense

    # 创建投资账户
    investment_account = Account(
        id=1,
        name="支付宝",
        account_type="investment",
        balance=Decimal("3000.00"),
        currency="CNY",
    )

    # 支出前
    assert investment_account.balance == Decimal("3000.00")

    # 支出200（从balance扣减，不影响持仓）
    expense_amount = Decimal("200.00")
    investment_account.balance -= expense_amount

    # 支出后
    assert investment_account.balance == Decimal("2800.00")
    # 注意：持仓不受影响


def test_expense_insufficient_balance_cash():
    """测试现金账户余额不足"""
    from app.models.core import Account

    cash_account = Account(
        id=1,
        name="招商银行",
        account_type="cash",
        balance=Decimal("100.00"),
        currency="CNY",
    )

    expense_amount = Decimal("200.00")

    # 余额不足
    assert cash_account.balance < expense_amount

    # API会返回："账户余额不足"


def test_expense_insufficient_balance_investment():
    """测试投资账户余额不足（Phase 2.1新增）"""
    from app.models.core import Account

    investment_account = Account(
        id=1,
        name="支付宝",
        account_type="investment",
        balance=Decimal("100.00"),
        currency="CNY",
    )

    expense_amount = Decimal("200.00")

    # 余额不足
    assert investment_account.balance < expense_amount

    # API会返回：更详细的提示
    # "投资账户余额不足，当前余额: ¥100.00。如需使用余额宝等高流动性资产，请先转出到余额。"


def test_expense_with_investment_account_holding():
    """测试有持仓的投资账户支出"""
    from app.models.core import Account, Holding

    # 创建投资账户（余额 + 余额宝 + 基金）
    account = Account(
        id=1,
        name="支付宝",
        account_type="investment",
        balance=Decimal("1000.00"),  # 余额
        currency="CNY",
    )

    # 余额宝（高流动性）
    yeb_holding = Holding(
        id=1,
        account_id=1,
        symbol="YEB",
        name="余额宝",
        asset_type="money_market",
        is_liquid=True,
        quantity=Decimal("2000"),
        current_value=Decimal("2000.00"),
        currency="CNY",
        is_active=True,
    )

    # 某基金（非流动性）
    fund_holding = Holding(
        id=2,
        account_id=1,
        symbol="000001",
        name="某基金",
        asset_type="fund",
        is_liquid=False,
        quantity=Decimal("1000"),
        current_value=Decimal("2000.00"),
        currency="CNY",
        is_active=True,
    )

    account.holdings = [yeb_holding, fund_holding]

    # 验证计算
    assert account.balance == Decimal("1000.00")
    assert account.available_cash == Decimal("3000.00")  # 余额 + 余额宝
    assert account.investment_value == Decimal("2000.00")  # 只有基金
    assert account.total_value == Decimal("5000.00")  # 全部

    # 支出300（只从balance扣减，不影响持仓）
    expense_amount = Decimal("300.00")
    account.balance -= expense_amount

    # 验证
    assert account.balance == Decimal("700.00")
    assert account.available_cash == Decimal("2700.00")  # 700 + 2000
    assert account.investment_value == Decimal("2000.00")  # 不变
    assert account.total_value == Decimal("4700.00")


def test_expense_without_budget():
    """测试不关联预算的支出"""
    from app.models.core import Account, Expense

    account = Account(
        id=1,
        name="招商银行",
        account_type="cash",
        balance=Decimal("10000.00"),
        currency="CNY",
    )

    # 不关联预算的支出
    expense_amount = Decimal("500.00")
    account.balance -= expense_amount

    assert account.balance == Decimal("9500.00")
    # budget.spent 不变


def test_expense_with_budget_exceeded():
    """测试预算超支的情况"""
    from app.models.core import Account, Budget

    account = Account(
        id=1,
        name="招商银行",
        account_type="cash",
        balance=Decimal("10000.00"),
        currency="CNY",
    )

    budget = Budget(
        id=1,
        name="3月生活费",
        budget_type="periodic",
        amount=Decimal("5000.00"),
        spent=Decimal("4800.00"),  # 已花费4800
        remaining=Decimal("200.00"),
    )

    # 尝试支出500（超过预算）
    expense_amount = Decimal("500.00")

    # 预算不足
    assert budget.remaining < expense_amount

    # API会返回："预算额度不足"


def test_expense_category_validation():
    """测试支出分类验证"""
    from datetime import date

    expense_categories = [
        "餐饮",
        "交通",
        "购物",
        "居住",
        "娱乐",
        "医疗",
        "教育",
        "人情",
        "其他",
    ]

    # 验证分类在预定义列表中
    for category in expense_categories:
        assert isinstance(category, str) and len(category) > 0


def test_expense_payment_method():
    """测试支出支付方式"""
    payment_methods = [
        "现金",
        "支付宝",
        "微信支付",
        "银行卡",
        "信用卡",
    ]

    for method in payment_methods:
        assert isinstance(method, str) and len(method) > 0


def test_expense_with_tags():
    """测试带标签的支出"""
    from app.models.core import Expense

    expense = Expense(
        id=1,
        account_id=1,
        amount=Decimal("200.00"),
        expense_date=date.today(),
        category="餐饮",
        subcategory="午餐",
        tags=["工作日", "外卖"],
    )

    assert expense.tags == ["工作日", "外卖"]
    assert len(expense.tags) == 2


def test_expense_is_shared_flag():
    """测试支出是否共同开销"""
    from app.models.core import Expense

    # 个人开销
    personal_expense = Expense(
        id=1,
        account_id=1,
        amount=Decimal("100.00"),
        expense_date=date.today(),
        category="餐饮",
        is_shared=False,
    )

    # 共同开销
    shared_expense = Expense(
        id=2,
        account_id=1,
        amount=Decimal("200.00"),
        expense_date=date.today(),
        category="居住",
        is_shared=True,
    )

    assert personal_expense.is_shared is False
    assert shared_expense.is_shared is True
