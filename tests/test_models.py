"""
测试核心模型功能 - 更新版（支持高流动性资产）
"""

import pytest
from decimal import Decimal
from datetime import datetime
from app.models.core import Account, Holding


class TestAccountModel:
    """测试Account模型的计算功能"""

    def test_cash_account_total_value(self):
        """测试现金账户的总资产计算"""
        account = Account(
            name="测试现金账户", account_type="cash", balance=Decimal("10000.00"), currency="CNY"
        )

        # 现金账户：total_value = balance
        assert account.total_value == Decimal("10000.00")
        assert account.holdings_value is None

    def test_investment_account_with_no_holdings(self):
        """测试没有持仓的投资账户"""
        account = Account(
            name="测试证券账户",
            account_type="investment",
            balance=Decimal("50000.00"),  # 可用现金
            holdings_value=Decimal("0"),
            currency="CNY",
        )
        account.holdings = []  # 空持仓列表

        # total_value = balance（没有持仓时）
        assert account.total_value == Decimal("50000.00")
        # available_cash = balance（没有高流动性资产时）
        assert account.available_cash == Decimal("50000.00")
        assert account.calculate_holdings_value() == Decimal("0")

    def test_investment_account_with_stock_holdings(self):
        """测试有股票持仓的投资账户（非流动性资产）"""
        account = Account(
            name="富途证券",
            account_type="investment",
            balance=Decimal("50000.00"),  # 可用现金
            currency="HKD",
        )

        # 创建股票持仓（非流动性）
        stock_holding = Holding(
            symbol="00700.HK",
            name="腾讯控股",
            asset_type="stock",
            quantity=Decimal("100"),
            avg_cost=Decimal("300.00"),
            current_price=Decimal("400.00"),
            current_value=Decimal("40000.00"),
            is_liquid=False,  # 股票是非流动性资产
            is_active=True,
        )

        account.holdings = [stock_holding]

        # 计算持仓市值（只计算非流动性资产）
        holdings_value = account.calculate_holdings_value()
        assert holdings_value == Decimal("40000.00")

        # 更新缓存并检查
        account.update_holdings_value()
        assert account.holdings_value == Decimal("40000.00")

        # total_value = balance + 非流动性持仓 = 50000 + 40000
        assert account.total_value == Decimal("90000.00")
        # available_cash = balance（因为没有高流动性资产）
        assert account.available_cash == Decimal("50000.00")

    def test_investment_account_with_mixed_holdings(self):
        """测试同时有流动性和非流动性资产的投资账户（支付宝场景）"""
        account = Account(
            name="支付宝",
            account_type="investment",
            balance=Decimal("1000.00"),  # 余额
            currency="CNY",
        )

        # 余额宝（高流动性，T+0货币基金）
        yeb_holding = Holding(
            symbol="YEB",
            name="余额宝",
            asset_type="money_market",
            quantity=Decimal("2000"),
            avg_cost=Decimal("1.00"),
            current_price=Decimal("1.00"),
            current_value=Decimal("2000.00"),
            is_liquid=True,  # 高流动性资产
            is_active=True,
        )

        # 某基金（普通基金，非流动性）
        fund_holding = Holding(
            symbol="000001",
            name="某混合基金",
            asset_type="fund",
            quantity=Decimal("1000.42"),
            avg_cost=Decimal("1.50"),
            current_price=Decimal("2.00"),
            current_value=Decimal("2000.84"),
            is_liquid=False,  # 普通基金不是高流动性资产
            is_active=True,
        )

        account.holdings = [yeb_holding, fund_holding]

        # 计算持仓市值（只计算非流动性资产）
        holdings_value = account.calculate_holdings_value()
        assert holdings_value == Decimal("2000.84")  # 只有基金

        # total_value = balance + 所有持仓 = 1000 + 2000 + 2000.84
        assert account.total_value == Decimal("5000.84")
        # available_cash = balance + 高流动性持仓 = 1000 + 2000
        assert account.available_cash == Decimal("3000.00")
        # investment_value = 非流动性持仓 = 2000.84
        assert account.investment_value == Decimal("2000.84")

    def test_investment_account_with_inactive_holdings(self):
        """测试有非活跃持仓的投资账户"""
        account = Account(
            name="测试账户", account_type="investment", balance=Decimal("10000.00"), currency="CNY"
        )

        # 活跃持仓
        active_holding = Holding(
            symbol="AAPL",
            asset_type="stock",
            quantity=Decimal("10"),
            current_value=Decimal("5000.00"),
            is_liquid=False,
            is_active=True,
        )

        # 非活跃持仓（已清仓）
        inactive_holding = Holding(
            symbol="TSLA",
            asset_type="stock",
            quantity=Decimal("0"),
            current_value=Decimal("0.00"),
            is_liquid=False,
            is_active=False,
        )

        account.holdings = [active_holding, inactive_holding]

        # 只计算活跃的非流动性持仓
        assert account.calculate_holdings_value() == Decimal("5000.00")
        assert account.total_value == Decimal("15000.00")


class TestLiquidityConcept:
    """测试高流动性资产概念"""

    def test_yeb_as_liquid_asset(self):
        """测试余额宝作为高流动性资产的展示"""
        account = Account(
            name="支付宝",
            account_type="investment",
            institution="蚂蚁集团",
            balance=Decimal("1000.00"),  # 余额
            currency="CNY",
        )

        # 添加余额宝持仓
        yeb = Holding(
            symbol="YEB",
            name="余额宝",
            asset_type="money_market",
            quantity=Decimal("2000"),
            current_value=Decimal("2000.00"),
            is_liquid=True,  # 高流动性
            is_active=True,
        )

        account.holdings = [yeb]

        # 展示效果：
        # - 可用现金: ¥3,000（余额1000 + 余额宝2000）
        # - 持仓市值: ¥0（余额宝是流动性资产，不计入持仓市值）
        # - 总资产: ¥3,000
        assert account.balance == Decimal("1000.00")
        assert account.available_cash == Decimal("3000.00")  # 1000 + 2000
        assert account.calculate_holdings_value() == Decimal("0")  # 余额宝不计入
        assert account.total_value == Decimal("3000.00")

    def test_complete_alipay_scenario(self):
        """测试完整的支付宝账户场景"""
        account = Account(
            name="支付宝",
            account_type="investment",
            balance=Decimal("1000.00"),  # 余额
            currency="CNY",
        )

        # 余额宝
        yeb = Holding(
            symbol="YEB",
            name="余额宝",
            asset_type="money_market",
            quantity=Decimal("2000"),
            avg_cost=Decimal("1.00"),
            current_value=Decimal("2000.00"),
            is_liquid=True,
            is_active=True,
        )

        # 某基金
        fund = Holding(
            symbol="000001",
            name="某混合基金",
            asset_type="fund",
            quantity=Decimal("1000.42"),
            avg_cost=Decimal("1.50"),
            current_price=Decimal("2.00"),
            current_value=Decimal("2000.84"),
            is_liquid=False,
            is_active=True,
        )

        account.holdings = [yeb, fund]

        # 预期展示：
        # 支付宝账户
        # ├── 余额: ¥1,000
        # ├── 余额宝: ¥2,000（T+0货币基金，随时可取）
        # ├── 某基金: ¥2,000.84（1000.42份，成本¥1,500.63，盈亏+¥500.21）
        # ├── 可用现金: ¥3,000（余额+余额宝）
        # ├── 持仓市值: ¥2,000.84（仅基金，不包括余额宝）
        # └── 总资产: ¥3,000.84（余额+基金市值，余额宝不计入总资产）

        assert account.balance == Decimal("1000.00")
        assert account.available_cash == Decimal("3000.00")  # 1000 + 2000
        assert account.calculate_holdings_value() == Decimal("2000.84")  # 仅基金
        assert account.total_value == Decimal("5000.84")  # 1000 + 2000 + 2000.84
        assert account.investment_value == Decimal("2000.84")  # 仅基金

        # 成本计算
        fund_cost = fund.quantity * fund.avg_cost
        fund_profit = fund.current_value - fund_cost
        assert fund_cost == Decimal("1500.63")  # 1000.42 * 1.50
        assert fund_profit == Decimal("500.21")  # 2000.84 - 1500.63


class TestUpdateHoldingsValue:
    """测试更新持仓市值功能"""

    def test_update_only_for_investment(self):
        """测试update_holdings_value只对投资账户生效"""
        cash_account = Account(
            name="现金账户", account_type="cash", balance=Decimal("10000.00"), currency="CNY"
        )

        # 现金账户调用update_holdings_value不应改变任何值
        cash_account.update_holdings_value()
        assert cash_account.holdings_value is None

    def test_update_excludes_liquid_assets(self):
        """测试update_holdings_value排除高流动性资产"""
        account = Account(
            name="支付宝",
            account_type="investment",
            balance=Decimal("1000.00"),
            currency="CNY",
        )

        # 余额宝（流动性）
        yeb = Holding(
            symbol="YEB",
            name="余额宝",
            asset_type="money_market",
            current_value=Decimal("2000.00"),
            is_liquid=True,
            is_active=True,
        )

        # 基金（非流动性）
        fund = Holding(
            symbol="FUND",
            name="某基金",
            asset_type="fund",
            current_value=Decimal("5000.00"),
            is_liquid=False,
            is_active=True,
        )

        account.holdings = [yeb, fund]
        account.update_holdings_value()

        # 缓存所有持仓市值（包括流动性和非流动性）
        assert account.holdings_value == Decimal("7000.00")  # 2000 + 5000
