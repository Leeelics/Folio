import httpx
from typing import Dict, Any, Optional, List
import logging
import os

logger = logging.getLogger(__name__)


class FolioAPIClient:
    """FastAPI 后端客户端"""

    def __init__(self, base_url: str | None = None, timeout_s: float | None = None):
        # Keep Streamlit pages and Home.py consistent: allow overriding via API_URL.
        self.base_url = base_url or os.getenv("API_URL", "http://localhost:8000")
        timeout = timeout_s or float(os.getenv("API_TIMEOUT_S", "60"))
        self.client = httpx.Client(timeout=timeout)

    def _get(self, endpoint: str) -> Dict[str, Any]:
        """GET 请求"""
        try:
            response = self.client.get(f"{self.base_url}{endpoint}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GET {endpoint} failed: {e}")
            raise

    def _post(
        self, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST 请求"""
        try:
            response = self.client.post(f"{self.base_url}{endpoint}", json=data, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"POST {endpoint} failed: {e}")
            raise

    def _put(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """PUT 请求"""
        try:
            response = self.client.put(f"{self.base_url}{endpoint}", json=data or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"PUT {endpoint} failed: {e}")
            raise

    def _delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE 请求"""
        try:
            response = self.client.delete(f"{self.base_url}{endpoint}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"DELETE {endpoint} failed: {e}")
            raise

    # ============ Portfolio APIs ============
    def get_portfolio_status(self) -> Dict[str, Any]:
        """获取资产组合状态"""
        return self._get("/api/v1/portfolio/status")

    def sync_okx_balance(self) -> Dict[str, Any]:
        """同步 OKX 余额"""
        return self._post("/api/v1/portfolio/sync-okx")

    # ============ Agent APIs ============
    def agent_analyze(self, query: str, news_limit: int = 5) -> Dict[str, Any]:
        """触发 AI 分析"""
        return self._post("/api/v1/agent/analyze", {"query": query, "news_limit": news_limit})

    # ============ News APIs ============
    def add_news(self, title: str, content: str, source: Optional[str] = None) -> Dict[str, Any]:
        """添加市场新闻"""
        return self._post(
            "/api/v1/news/add", params={"title": title, "content": content, "source": source}
        )

    def get_latest_news(self, limit: int = 10) -> Dict[str, Any]:
        """获取最新新闻"""
        return self._get(f"/api/v1/news/latest?limit={limit}")

    # ============ Stock Quote APIs ============
    def get_stock_quote(
        self, market: str, symbol: str, mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取股票实时行情"""
        params = f"?mode={mode}" if mode else ""
        return self._get(f"/api/v1/stocks/quote/{market}/{symbol}{params}")

    def get_stock_kline(
        self,
        market: str,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取股票K线数据"""
        params = f"?period={period}"
        if start_date:
            params += f"&start_date={start_date}"
        if end_date:
            params += f"&end_date={end_date}"
        return self._get(f"/api/v1/stocks/kline/{market}/{symbol}{params}")

    def get_market_overview(self, market: str) -> Dict[str, Any]:
        """获取市场概览（涨跌家数）"""
        return self._get(f"/api/v1/stocks/market-overview/{market}")

    def get_volume_surge_stocks(self, market: str, threshold: float = 2.0) -> List[Dict[str, Any]]:
        """获取放量股票列表"""
        return self._get(f"/api/v1/stocks/volume-surge/{market}?threshold={threshold}")

    def get_financial_data(self, market: str, symbol: str) -> Dict[str, Any]:
        """获取股票财务数据"""
        return self._get(f"/api/v1/stocks/financial/{market}/{symbol}")

    def search_stocks(self, keyword: str, market: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索股票"""
        params = f"?keyword={keyword}"
        if market:
            params += f"&market={market}"
        return self._get(f"/api/v1/stocks/search{params}")

    # ============ Stock Position APIs ============
    def get_positions(self) -> Dict[str, Any]:
        """获取所有股票持仓"""
        return self._get("/api/v1/stocks/positions")

    def add_position(
        self,
        symbol: str,
        market: str,
        quantity: int,
        cost_price: float,
        account_name: str = "默认账户",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """添加股票持仓"""
        return self._post(
            "/api/v1/stocks/positions",
            {
                "symbol": symbol,
                "market": market,
                "quantity": quantity,
                "cost_price": cost_price,
                "account_name": account_name,
                "notes": notes,
            },
        )

    def update_position(
        self,
        position_id: int,
        quantity: Optional[int] = None,
        cost_price: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新股票持仓"""
        data = {}
        if quantity is not None:
            data["quantity"] = quantity
        if cost_price is not None:
            data["cost_price"] = cost_price
        if notes is not None:
            data["notes"] = notes
        return self._put(f"/api/v1/stocks/positions/{position_id}", data)

    def delete_position(self, position_id: int) -> Dict[str, Any]:
        """删除股票持仓"""
        return self._delete(f"/api/v1/stocks/positions/{position_id}")

    def get_position_pnl(self, position_id: int) -> Dict[str, Any]:
        """获取单个持仓的盈亏详情"""
        return self._get(f"/api/v1/stocks/positions/{position_id}/pnl")

    def get_positions_summary(self) -> Dict[str, Any]:
        """获取持仓汇总（总市值、总盈亏）"""
        return self._get("/api/v1/stocks/positions/summary")

    # ============ Watchlist APIs ============
    def get_watchlist(self) -> Dict[str, Any]:
        """获取自选股列表"""
        return self._get("/api/v1/stocks/watchlist")

    def add_to_watchlist(
        self,
        symbol: str,
        market: str,
        notes: Optional[str] = None,
        alert_price_high: Optional[float] = None,
        alert_price_low: Optional[float] = None,
    ) -> Dict[str, Any]:
        """添加自选股"""
        return self._post(
            "/api/v1/stocks/watchlist",
            {
                "symbol": symbol,
                "market": market,
                "notes": notes,
                "alert_price_high": alert_price_high,
                "alert_price_low": alert_price_low,
            },
        )

    def remove_from_watchlist(self, watchlist_id: int) -> Dict[str, Any]:
        """从自选股移除"""
        return self._delete(f"/api/v1/stocks/watchlist/{watchlist_id}")

    # ============ Health Check ============
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return self._get("/health")

    # ============ Investment Transaction APIs ============
    def create_transaction(
        self,
        asset_type: str,
        symbol: str,
        transaction_type: str,
        quantity: float,
        price: float,
        transaction_date: str,
        name: Optional[str] = None,
        market: Optional[str] = None,
        fees: float = 0,
        currency: str = "CNY",
        account_name: str = "默认账户",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建交易记录"""
        return self._post(
            "/api/v1/investments/transactions",
            {
                "asset_type": asset_type,
                "symbol": symbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "price": price,
                "transaction_date": transaction_date,
                "name": name,
                "market": market,
                "fees": fees,
                "currency": currency,
                "account_name": account_name,
                "notes": notes,
            },
        )

    def get_transactions(
        self,
        asset_type: Optional[str] = None,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        account_name: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取交易记录列表"""
        params = f"?limit={limit}&offset={offset}"
        if asset_type:
            params += f"&asset_type={asset_type}"
        if symbol:
            params += f"&symbol={symbol}"
        if market:
            params += f"&market={market}"
        if account_name:
            params += f"&account_name={account_name}"
        if transaction_type:
            params += f"&transaction_type={transaction_type}"
        if start_date:
            params += f"&start_date={start_date}"
        if end_date:
            params += f"&end_date={end_date}"
        return self._get(f"/api/v1/investments/transactions{params}")

    def get_transaction(self, transaction_id: int) -> Dict[str, Any]:
        """获取单条交易记录"""
        return self._get(f"/api/v1/investments/transactions/{transaction_id}")

    def update_transaction(
        self,
        transaction_id: int,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        transaction_date: Optional[str] = None,
        fees: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新交易记录"""
        data = {}
        if quantity is not None:
            data["quantity"] = quantity
        if price is not None:
            data["price"] = price
        if transaction_date is not None:
            data["transaction_date"] = transaction_date
        if fees is not None:
            data["fees"] = fees
        if notes is not None:
            data["notes"] = notes
        return self._put(f"/api/v1/investments/transactions/{transaction_id}", data)

    def delete_transaction(self, transaction_id: int) -> Dict[str, Any]:
        """删除交易记录"""
        return self._delete(f"/api/v1/investments/transactions/{transaction_id}")

    # ============ Investment Holdings APIs ============
    def get_investment_holdings(
        self,
        asset_type: Optional[str] = None,
        account_name: Optional[str] = None,
        include_zero: bool = False,
    ) -> List[Dict[str, Any]]:
        """获取投资持仓汇总"""
        params = f"?include_zero={str(include_zero).lower()}"
        if asset_type:
            params += f"&asset_type={asset_type}"
        if account_name:
            params += f"&account_name={account_name}"
        return self._get(f"/api/v1/investments/holdings{params}")

    def get_holding_history(
        self,
        symbol: str,
        account_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取单个资产的交易历史"""
        params = ""
        if account_name:
            params = f"?account_name={account_name}"
        return self._get(f"/api/v1/investments/holdings/{symbol}/history{params}")

    def get_investment_summary(
        self,
        account_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取投资组合汇总"""
        params = ""
        if account_name:
            params = f"?account_name={account_name}"
        return self._get(f"/api/v1/investments/holdings/summary{params}")

    # ============ Fund Product APIs ============
    def create_fund_product(
        self,
        product_type: str,
        symbol: str,
        name: str,
        issuer: Optional[str] = None,
        risk_level: Optional[str] = None,
        expected_return: Optional[float] = None,
        nav: Optional[float] = None,
        currency: str = "CNY",
    ) -> Dict[str, Any]:
        """创建基金/理财产品"""
        return self._post(
            "/api/v1/investments/funds",
            {
                "product_type": product_type,
                "symbol": symbol,
                "name": name,
                "issuer": issuer,
                "risk_level": risk_level,
                "expected_return": expected_return,
                "nav": nav,
                "currency": currency,
            },
        )

    def get_fund_products(
        self,
        product_type: Optional[str] = None,
        is_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """获取基金/理财产品列表"""
        params = f"?is_active={str(is_active).lower()}"
        if product_type:
            params += f"&product_type={product_type}"
        return self._get(f"/api/v1/investments/funds{params}")

    def get_fund_product(self, symbol: str) -> Dict[str, Any]:
        """获取单个基金/理财产品"""
        return self._get(f"/api/v1/investments/funds/{symbol}")

    def update_fund_nav(
        self,
        symbol: str,
        nav: float,
        nav_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新基金净值"""
        data = {"nav": nav}
        if nav_date:
            data["nav_date"] = nav_date
        return self._put(f"/api/v1/investments/funds/{symbol}/nav", data)

    # ============ Brokerage Account APIs (新平台账户系统) ============

    def get_brokerage_accounts(
        self, platform_type: Optional[str] = None, is_active: bool = True
    ) -> List[Dict[str, Any]]:
        """获取所有平台账户列表"""
        params = f"?is_active={str(is_active).lower()}"
        if platform_type:
            params += f"&platform_type={platform_type}"
        return self._get(f"/api/v1/brokerage/accounts{params}")

    def create_brokerage_account(
        self,
        name: str,
        platform_type: str,
        institution: Optional[str] = None,
        account_number: Optional[str] = None,
        base_currency: str = "CNY",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建平台账户"""
        return self._post(
            "/api/v1/brokerage/accounts",
            {
                "name": name,
                "platform_type": platform_type,
                "institution": institution,
                "account_number": account_number,
                "base_currency": base_currency,
                "notes": notes,
            },
        )

    def get_brokerage_account(self, account_id: int) -> Dict[str, Any]:
        """获取单个账户详情"""
        return self._get(f"/api/v1/brokerage/accounts/{account_id}")

    def update_brokerage_account(
        self,
        account_id: int,
        name: Optional[str] = None,
        institution: Optional[str] = None,
        account_number: Optional[str] = None,
        base_currency: Optional[str] = None,
        is_active: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新账户信息"""
        data = {}
        if name is not None:
            data["name"] = name
        if institution is not None:
            data["institution"] = institution
        if account_number is not None:
            data["account_number"] = account_number
        if base_currency is not None:
            data["base_currency"] = base_currency
        if is_active is not None:
            data["is_active"] = is_active
        if notes is not None:
            data["notes"] = notes
        return self._put(f"/api/v1/brokerage/accounts/{account_id}", data)

    def delete_brokerage_account(self, account_id: int) -> Dict[str, Any]:
        """删除账户"""
        return self._delete(f"/api/v1/brokerage/accounts/{account_id}")

    # ============ Cash Balance APIs ============

    def get_cash_balances(self, account_id: int) -> List[Dict[str, Any]]:
        """获取账户现金余额"""
        return self._get(f"/api/v1/brokerage/accounts/{account_id}/cash")

    def set_cash_balance(
        self,
        account_id: int,
        currency: str,
        amount: float,
        balance_type: str = "available",
    ) -> Dict[str, Any]:
        """设置现金余额"""
        return self._post(
            f"/api/v1/brokerage/accounts/{account_id}/cash",
            params={
                "currency": currency,
                "amount": amount,
                "balance_type": balance_type,
            },
        )

    def adjust_cash_balance(
        self,
        account_id: int,
        currency: str,
        delta: float,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """调整现金余额"""
        params = {
            "currency": currency,
            "delta": delta,
        }
        if description:
            params["description"] = description
        return self._post(
            f"/api/v1/brokerage/accounts/{account_id}/cash/adjust",
            params=params,
        )

    # ============ Account Holdings & Transactions APIs ============

    def get_account_holdings(
        self,
        account_id: int,
        asset_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取账户持仓列表"""
        params = ""
        if asset_type:
            params = f"?asset_type={asset_type}"
        return self._get(f"/api/v1/brokerage/accounts/{account_id}/holdings{params}")

    def create_account_transaction(
        self,
        account_id: int,
        asset_type: str,
        symbol: str,
        transaction_type: str,
        quantity: float,
        price: float,
        trade_date: str,
        market: Optional[str] = None,
        name: Optional[str] = None,
        fees: float = 0,
        trade_currency: str = "CNY",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """录入交易（自动联动更新现金和持仓）"""
        return self._post(
            f"/api/v1/brokerage/accounts/{account_id}/transactions",
            {
                "asset_type": asset_type,
                "symbol": symbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "price": price,
                "trade_date": trade_date,
                "market": market,
                "name": name,
                "fees": fees,
                "trade_currency": trade_currency,
                "notes": notes,
            },
        )

    # ============ Unified View & Summary APIs ============

    def get_account_unified_view(
        self,
        account_id: int,
        base_currency: str = "CNY",
    ) -> Dict[str, Any]:
        """获取统一账户视图（现金 + 持仓）"""
        return self._get(
            f"/api/v1/brokerage/accounts/{account_id}/view?base_currency={base_currency}"
        )

    def get_brokerage_summary(
        self,
        base_currency: str = "CNY",
    ) -> Dict[str, Any]:
        """获取资产组合汇总（所有账户）"""
        return self._get(f"/api/v1/brokerage/summary?base_currency={base_currency}")

    def get_brokerage_allocation(self, base_currency: str = "CNY") -> Dict[str, Any]:
        """获取资产分配统计"""
        return self._get(f"/api/v1/brokerage/allocation?base_currency={base_currency}")

    # ============ Exchange Rate APIs ============

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Dict[str, Any]:
        """获取汇率"""
        return self._get(
            f"/api/v1/brokerage/exchange-rate?from_currency={from_currency}&to_currency={to_currency}"
        )

    def refresh_exchange_rates(self) -> Dict[str, Any]:
        """刷新所有汇率"""
        return self._post("/api/v1/brokerage/exchange-rate/refresh")

    # ============ Phase 2.1: Core Account APIs ============

    def get_accounts(
        self, account_type: Optional[str] = None, is_active: bool = True
    ) -> List[Dict[str, Any]]:
        """获取账户列表"""
        params = (
            f"?account_type={account_type}&is_active={is_active}"
            if account_type
            else f"?is_active={is_active}"
        )
        return self._get(f"/api/v1/core/accounts{params}")

    def get_account(self, account_id: int) -> Dict[str, Any]:
        """获取单个账户详情"""
        return self._get(f"/api/v1/core/accounts/{account_id}")

    def create_account(
        self,
        name: str,
        account_type: str,
        institution: Optional[str] = None,
        initial_balance: float = 0.0,
        currency: str = "CNY",
    ) -> Dict[str, Any]:
        """创建账户"""
        return self._post(
            "/api/v1/core/accounts",
            {
                "name": name,
                "account_type": account_type,
                "institution": institution,
                "initial_balance": str(initial_balance),
                "currency": currency,
            },
        )

    def update_account(
        self, account_id: int, name: Optional[str] = None, notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新账户"""
        data = {}
        if name:
            data["name"] = name
        if notes:
            data["notes"] = notes
        return self._put(f"/api/v1/core/accounts/{account_id}", data)

    def delete_account(self, account_id: int) -> Dict[str, Any]:
        """删除账户"""
        return self._delete(f"/api/v1/core/accounts/{account_id}")

    # ============ Phase 2.1: Holdings APIs ============

    def get_holdings(
        self, account_id: Optional[int] = None, is_active: bool = True
    ) -> List[Dict[str, Any]]:
        """获取持仓列表"""
        params = (
            f"?account_id={account_id}&is_active={is_active}"
            if account_id
            else f"?is_active={is_active}"
        )
        return self._get(f"/api/v1/core/holdings{params}")

    def create_holding(
        self,
        account_id: int,
        symbol: str,
        name: str,
        asset_type: str,
        quantity: float,
        avg_cost: float,
        current_price: Optional[float] = None,
        current_value: Optional[float] = None,
        is_liquid: bool = False,
    ) -> Dict[str, Any]:
        """添加持仓"""
        return self._post(
            "/api/v1/core/holdings",
            {
                "account_id": account_id,
                "symbol": symbol,
                "name": name,
                "asset_type": asset_type,
                "quantity": str(quantity),
                "avg_cost": str(avg_cost),
                "current_price": str(current_price) if current_price else None,
                "current_value": str(current_value) if current_value else None,
                "is_liquid": is_liquid,
            },
        )

    def update_holding(
        self,
        holding_id: int,
        quantity: Optional[float] = None,
        current_price: Optional[float] = None,
        current_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """更新持仓"""
        data = {}
        if quantity is not None:
            data["quantity"] = str(quantity)
        if current_price is not None:
            data["current_price"] = str(current_price)
        if current_value is not None:
            data["current_value"] = str(current_value)
        return self._put(f"/api/v1/core/holdings/{holding_id}", data)

    def delete_holding(self, holding_id: int) -> Dict[str, Any]:
        """删除持仓"""
        return self._delete(f"/api/v1/core/holdings/{holding_id}")

    def sync_holdings_value(self) -> Dict[str, Any]:
        """同步持仓市值"""
        return self._post("/api/v1/core/holdings/sync")

    # ============ Phase 2.1: Transfer APIs ============

    def create_transfer(
        self, from_account_id: int, to_account_id: int, amount: float, notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建转账"""
        data = {
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": str(amount),
        }
        if notes:
            data["notes"] = notes
        return self._post("/api/v1/core/transfers", data)

    def get_transfers(
        self,
        from_account_id: Optional[int] = None,
        to_account_id: Optional[int] = None,
        transfer_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取转账记录"""
        params = []
        if from_account_id:
            params.append(f"from_account_id={from_account_id}")
        if to_account_id:
            params.append(f"to_account_id={to_account_id}")
        if transfer_type:
            params.append(f"transfer_type={transfer_type}")
        params.append(f"limit={limit}")
        return self._get(f"/api/v1/core/transfers?{'&'.join(params)}")

    # ============ Phase 2.1: Expense APIs ============

    def create_expense(
        self,
        account_id: int,
        amount: float,
        expense_date: str,
        category: str,
        subcategory: Optional[str] = None,
        budget_id: Optional[int] = None,
        merchant: Optional[str] = None,
        payment_method: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建支出"""
        data = {
            "account_id": account_id,
            "amount": str(amount),
            "expense_date": expense_date,
            "category": category,
            "subcategory": subcategory,
            "merchant": merchant,
            "payment_method": payment_method,
            "notes": notes,
        }
        if budget_id:
            data["budget_id"] = budget_id
        return self._post("/api/v1/core/expenses", data)

    def get_expenses(
        self, account_id: Optional[int] = None, budget_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取支出列表"""
        params = []
        if account_id:
            params.append(f"account_id={account_id}")
        if budget_id:
            params.append(f"budget_id={budget_id}")
        param_str = f"?{'&'.join(params)}" if params else ""
        return self._get(f"/api/v1/core/expenses{param_str}")

    # ============ Phase 2.1: Budget APIs ============

    def get_budgets(
        self, budget_type: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取预算列表"""
        params = []
        if budget_type:
            params.append(f"budget_type={budget_type}")
        if status:
            params.append(f"status={status}")
        param_str = f"?{'&'.join(params)}" if params else ""
        return self._get(f"/api/v1/core/budgets{param_str}")

    def get_budget(self, budget_id: int) -> Dict[str, Any]:
        """获取单个预算"""
        return self._get(f"/api/v1/core/budgets/{budget_id}")

    def create_budget(
        self,
        name: str,
        budget_type: str,
        amount: float,
        period_start: str,
        period_end: str,
        associated_account_ids: Optional[List[int]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建预算"""
        data = {
            "name": name,
            "budget_type": budget_type,
            "amount": str(amount),
            "period_start": period_start,
            "period_end": period_end,
        }
        if associated_account_ids:
            data["associated_account_ids"] = associated_account_ids
        if notes:
            data["notes"] = notes
        return self._post("/api/v1/core/budgets", data)

    def complete_budget(self, budget_id: int) -> Dict[str, Any]:
        """完成预算"""
        return self._post(f"/api/v1/core/budgets/{budget_id}/complete")

    def get_budget_available_funds(self, budget_id: int) -> Dict[str, Any]:
        """获取预算关联账户的可用资金"""
        return self._get(f"/api/v1/core/budgets/{budget_id}/available-funds")

    # ============ Phase 2.1: Category APIs ============

    def get_categories(self) -> List[Dict[str, Any]]:
        """获取支出分类列表"""
        return self._get("/api/v1/core/categories")

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """获取所有分类（含已停用）"""
        return self._get("/api/v1/core/categories/all")

    def create_category(self, category: str, subcategory: str) -> Dict[str, Any]:
        """创建分类"""
        return self._post("/api/v1/core/categories", {
            "category": category,
            "subcategory": subcategory,
        })

    def update_category(self, category_id: int, is_active: bool) -> Dict[str, Any]:
        """更新分类（启用/停用）"""
        return self._put(f"/api/v1/core/categories/{category_id}", {
            "is_active": is_active,
        })

    # ============ Phase 2.1: Dashboard APIs ============

    def get_dashboard(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        return self._get("/api/v1/core/dashboard")

    # ============ Phase 2.2: Liability APIs ============

    def get_liabilities(self, liability_type: Optional[str] = None, is_active: bool = True) -> List[Dict[str, Any]]:
        """获取负债列表"""
        params = [f"is_active={is_active}"]
        if liability_type:
            params.append(f"liability_type={liability_type}")
        return self._get(f"/api/v1/core/liabilities?{'&'.join(params)}")

    def get_liability(self, liability_id: int) -> Dict[str, Any]:
        """获取单个负债"""
        return self._get(f"/api/v1/core/liabilities/{liability_id}")

    def create_liability(self, name: str, liability_type: str, original_amount: float, remaining_amount: float, institution: Optional[str] = None, monthly_payment: Optional[float] = None, interest_rate: Optional[float] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, payment_day: Optional[int] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        """创建负债"""
        data = {"name": name, "liability_type": liability_type, "original_amount": str(original_amount), "remaining_amount": str(remaining_amount)}
        if institution: data["institution"] = institution
        if monthly_payment is not None: data["monthly_payment"] = str(monthly_payment)
        if interest_rate is not None: data["interest_rate"] = str(interest_rate)
        if start_date: data["start_date"] = start_date
        if end_date: data["end_date"] = end_date
        if payment_day is not None: data["payment_day"] = payment_day
        if notes: data["notes"] = notes
        return self._post("/api/v1/core/liabilities", data)

    def update_liability(self, liability_id: int, **kwargs) -> Dict[str, Any]:
        """更新负债"""
        data = {k: v for k, v in kwargs.items() if v is not None}
        return self._put(f"/api/v1/core/liabilities/{liability_id}", data)

    def delete_liability(self, liability_id: int) -> Dict[str, Any]:
        """删除负债"""
        return self._delete(f"/api/v1/core/liabilities/{liability_id}")

    def create_liability_payment(self, liability_id: int, amount: float, payment_date: str, account_id: Optional[int] = None, principal: Optional[float] = None, interest: Optional[float] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        """记录还款"""
        data = {"amount": str(amount), "payment_date": payment_date}
        if account_id: data["account_id"] = account_id
        if principal is not None: data["principal"] = str(principal)
        if interest is not None: data["interest"] = str(interest)
        if notes: data["notes"] = notes
        return self._post(f"/api/v1/core/liabilities/{liability_id}/payment", data)

    # ============ Phase 2.2: Budget Lifecycle APIs ============

    def update_budget(self, budget_id: int, **kwargs) -> Dict[str, Any]:
        """更新预算"""
        data = {k: v for k, v in kwargs.items() if v is not None}
        return self._put(f"/api/v1/core/budgets/{budget_id}", data)

    def delete_budget(self, budget_id: int) -> Dict[str, Any]:
        """删除预算"""
        return self._delete(f"/api/v1/core/budgets/{budget_id}")

    def cancel_budget(self, budget_id: int) -> Dict[str, Any]:
        """取消预算"""
        return self._post(f"/api/v1/core/budgets/{budget_id}/cancel")

    # ============ Phase 2.2: Expense Delete API ============

    def delete_expense(self, expense_id: int) -> Dict[str, Any]:
        """删除支出"""
        return self._delete(f"/api/v1/core/expenses/{expense_id}")

    # ============ Phase 3: Portfolio & PnL APIs ============

    def get_portfolio(self) -> Dict[str, Any]:
        """获取投资组合汇总（持仓列表、总市值、分配比例）"""
        return self._get("/api/v1/investments/portfolio")

    def get_pnl_analysis(self) -> Dict[str, Any]:
        """获取盈亏分析（成本、现价、盈亏额、盈亏率）"""
        return self._get("/api/v1/investments/pnl-analysis")
