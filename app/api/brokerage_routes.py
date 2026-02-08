"""
平台账户 API 路由
提供账户管理、交易录入、统一视图查询等功能
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.brokerage_account_service import BrokerageAccountService
from app.services.exchange_rate_service import ExchangeRateService

router = APIRouter(prefix="/brokerage", tags=["平台账户"])


# ============ 请求/响应模型 ============


class AccountCreateRequest(BaseModel):
    """创建账户请求"""

    name: str = Field(..., description="账户名称，如'富途证券'")
    platform_type: str = Field(..., description="平台类型: bank/securities/fund/crypto")
    institution: Optional[str] = Field(None, description="机构名称，如'富途'")
    account_number: Optional[str] = Field(None, description="账号")
    base_currency: str = Field("CNY", description="本位币")
    notes: Optional[str] = Field(None, description="备注")


class AccountUpdateRequest(BaseModel):
    """更新账户请求"""

    name: Optional[str] = None
    institution: Optional[str] = None
    account_number: Optional[str] = None
    base_currency: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class AccountResponse(BaseModel):
    """账户响应"""

    id: int
    name: str
    platform_type: str
    institution: Optional[str]
    account_number: Optional[str]
    base_currency: str
    is_active: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CashBalanceResponse(BaseModel):
    """现金余额响应"""

    currency: str
    available: float
    frozen: float
    total: float


class HoldingResponse(BaseModel):
    """持仓响应"""

    id: int
    asset_type: str
    symbol: str
    name: str
    market: str
    quantity: float
    avg_cost: float
    total_cost: float
    currency: str


class TransactionCreateRequest(BaseModel):
    """创建交易请求"""

    asset_type: str = Field(..., description="资产类型: stock/fund/bond/crypto")
    symbol: str = Field(..., description="代码，如'600000'")
    transaction_type: str = Field(
        ..., description="交易类型: buy/sell/dividend/transfer_in/transfer_out/interest"
    )
    quantity: float = Field(..., gt=0, description="数量")
    price: float = Field(..., ge=0, description="价格")
    trade_date: datetime = Field(..., description="交易日期")
    market: Optional[str] = Field(None, description="市场: A股/港股/美股")
    name: Optional[str] = Field(None, description="资产名称")
    fees: float = Field(0, ge=0, description="手续费")
    trade_currency: str = Field("CNY", description="交易币种")
    notes: Optional[str] = Field(None, description="备注")


class TransactionResponse(BaseModel):
    """交易响应"""

    id: int
    asset_type: str
    symbol: str
    transaction_type: str
    quantity: float
    price: float
    amount: float
    fees: float
    trade_date: datetime
    trade_currency: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UnifiedAccountViewResponse(BaseModel):
    """统一账户视图响应"""

    account_id: int
    account_name: str
    platform_type: str
    institution: str
    base_currency: str

    cash_balances: List[CashBalanceResponse]
    holdings: List[HoldingResponse]

    total_cash: float
    total_holdings: float
    total_assets: float

    class Config:
        from_attributes = True


class PortfolioSummaryResponse(BaseModel):
    """资产组合汇总响应"""

    total_assets_cny: float
    total_cash_cny: float
    total_holdings_cny: float
    accounts: List[dict]


# ============ 账户管理 API ============


@router.post("/accounts", response_model=AccountResponse)
async def create_account(request: AccountCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建平台账户"""
    service = BrokerageAccountService()

    account = await service.create_account(
        db=db,
        name=request.name,
        platform_type=request.platform_type,
        institution=request.institution,
        account_number=request.account_number,
        base_currency=request.base_currency,
        notes=request.notes,
    )

    return account


@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    platform_type: Optional[str] = Query(None, description="按平台类型筛选"),
    is_active: bool = Query(True, description="是否只显示活跃账户"),
    db: AsyncSession = Depends(get_db),
):
    """获取所有平台账户列表"""
    service = BrokerageAccountService()
    accounts = await service.get_all_accounts(db, platform_type, is_active)
    return accounts


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个账户详情"""
    service = BrokerageAccountService()
    account = await service.get_account(db, account_id)

    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    return account


@router.put("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int, request: AccountUpdateRequest, db: AsyncSession = Depends(get_db)
):
    """更新账户信息"""
    service = BrokerageAccountService()

    account = await service.update_account(db, account_id, **request.model_dump(exclude_unset=True))

    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    return account


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """删除账户（级联删除所有关联数据）"""
    service = BrokerageAccountService()

    success = await service.delete_account(db, account_id)

    if not success:
        raise HTTPException(status_code=404, detail="账户不存在")

    return {"message": "账户已删除", "account_id": account_id}


# ============ 现金管理 API ============


@router.get("/accounts/{account_id}/cash", response_model=List[CashBalanceResponse])
async def get_cash_balances(account_id: int, db: AsyncSession = Depends(get_db)):
    """获取账户的现金余额"""
    service = BrokerageAccountService()

    # 检查账户是否存在
    account = await service.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    balances = await service.get_all_cash_balances(db, account_id)

    # 按币种合并 available 和 frozen
    merged = {}
    for balance in balances:
        currency = balance.currency
        if currency not in merged:
            merged[currency] = {"available": 0.0, "frozen": 0.0}

        if balance.balance_type == "available":
            merged[currency]["available"] = float(balance.amount)
        elif balance.balance_type == "frozen":
            merged[currency]["frozen"] = float(balance.amount)

    # 构建响应
    response = []
    for currency, amounts in merged.items():
        response.append(
            CashBalanceResponse(
                currency=currency,
                available=amounts["available"],
                frozen=amounts["frozen"],
                total=amounts["available"] + amounts["frozen"],
            )
        )

    return response


@router.post("/accounts/{account_id}/cash")
async def set_cash_balance(
    account_id: int,
    currency: str = Query(..., description="币种"),
    amount: float = Query(..., description="金额"),
    balance_type: str = Query("available", description="余额类型: available/frozen"),
    db: AsyncSession = Depends(get_db),
):
    """设置现金余额（创建或更新）"""
    service = BrokerageAccountService()

    # 检查账户是否存在
    account = await service.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    balance = await service.set_cash_balance(
        db, account_id, currency, Decimal(str(amount)), balance_type
    )

    return {
        "message": "余额已更新",
        "account_id": account_id,
        "currency": currency,
        "amount": float(balance.amount),
        "balance_type": balance_type,
    }


@router.post("/accounts/{account_id}/cash/adjust")
async def adjust_cash_balance(
    account_id: int,
    currency: str = Query(..., description="币种"),
    delta: float = Query(..., description="变动金额（正数增加，负数减少）"),
    description: str = Query(None, description="变动说明"),
    db: AsyncSession = Depends(get_db),
):
    """调整现金余额（增加或减少）"""
    service = BrokerageAccountService()

    # 检查账户是否存在
    account = await service.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    balance = await service.adjust_cash_balance(
        db, account_id, currency, Decimal(str(delta)), "available", description
    )

    return {
        "message": "余额已调整",
        "account_id": account_id,
        "currency": currency,
        "new_balance": float(balance.amount),
        "delta": delta,
    }


# ============ 持仓查询 API ============


@router.get("/accounts/{account_id}/holdings", response_model=List[HoldingResponse])
async def get_holdings(
    account_id: int,
    asset_type: Optional[str] = Query(None, description="按资产类型筛选"),
    db: AsyncSession = Depends(get_db),
):
    """获取账户的持仓列表"""
    service = BrokerageAccountService()

    # 检查账户是否存在
    account = await service.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    holdings = await service.get_all_holdings(db, account_id, asset_type)

    return [
        HoldingResponse(
            id=h.id,
            asset_type=h.asset_type,
            symbol=h.symbol,
            name=h.name or h.symbol,
            market=h.market or "",
            quantity=float(h.quantity),
            avg_cost=float(h.avg_cost),
            total_cost=float(h.total_cost),
            currency=h.currency,
        )
        for h in holdings
    ]


# ============ 交易录入 API ============


@router.post("/accounts/{account_id}/transactions", response_model=TransactionResponse)
async def create_transaction(
    account_id: int, request: TransactionCreateRequest, db: AsyncSession = Depends(get_db)
):
    """
    录入交易（自动联动更新现金和持仓）

    支持的交易类型：
    - buy: 买入（扣减现金，增加持仓）
    - sell: 卖出（增加现金，减少持仓）
    - dividend: 分红（增加现金）
    - transfer_in: 转入（增加持仓，不扣现金）
    - transfer_out: 转出（减少持仓，不加现金）
    - interest: 利息（增加现金）
    """
    service = BrokerageAccountService()

    # 检查账户是否存在
    account = await service.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    try:
        transaction = await service.add_transaction(
            db=db,
            account_id=account_id,
            asset_type=request.asset_type,
            symbol=request.symbol,
            transaction_type=request.transaction_type,
            quantity=Decimal(str(request.quantity)),
            price=Decimal(str(request.price)),
            trade_date=request.trade_date,
            market=request.market,
            name=request.name,
            fees=Decimal(str(request.fees)),
            trade_currency=request.trade_currency,
            notes=request.notes,
        )

        return transaction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"交易录入失败: {str(e)}")


@router.get("/accounts/{account_id}/transactions", response_model=List[TransactionResponse])
async def list_transactions(account_id: int, db: AsyncSession = Depends(get_db)):
    """获取账户的交易记录"""
    # TODO: 实现交易记录查询
    return []


# ============ 统一视图 API ============


@router.get("/accounts/{account_id}/view", response_model=UnifiedAccountViewResponse)
async def get_account_view(
    account_id: int,
    base_currency: str = Query("CNY", description="折算基准币种"),
    db: AsyncSession = Depends(get_db),
):
    """获取统一账户视图（现金 + 持仓）"""
    service = BrokerageAccountService()

    view = await service.get_unified_account_view(db, account_id, base_currency)

    if not view:
        raise HTTPException(status_code=404, detail="账户不存在")

    return UnifiedAccountViewResponse(
        account_id=view.account_id,
        account_name=view.account_name,
        platform_type=view.platform_type,
        institution=view.institution,
        base_currency=view.base_currency,
        cash_balances=[
            CashBalanceResponse(
                currency=c.currency,
                available=float(c.available),
                frozen=float(c.frozen),
                total=float(c.total),
            )
            for c in view.cash_balances
        ],
        holdings=[
            HoldingResponse(
                id=h.id,
                asset_type=h.asset_type,
                symbol=h.symbol,
                name=h.name,
                market=h.market,
                quantity=float(h.quantity),
                avg_cost=float(h.avg_cost),
                total_cost=float(h.total_cost),
                currency=h.currency,
            )
            for h in view.holdings
        ],
        total_cash=float(view.total_cash),
        total_holdings=float(view.total_holdings),
        total_assets=float(view.total_assets),
    )


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    base_currency: str = Query("CNY", description="折算基准币种"),
    db: AsyncSession = Depends(get_db),
):
    """获取资产组合汇总（所有账户）"""
    service = BrokerageAccountService()

    summary = await service.get_all_accounts_summary(db, base_currency)

    return PortfolioSummaryResponse(
        total_assets_cny=float(summary["total_assets_cny"]),
        total_cash_cny=float(summary["total_cash_cny"]),
        total_holdings_cny=float(summary["total_holdings_cny"]),
        accounts=summary["accounts"],
    )


@router.get("/allocation")
async def get_portfolio_allocation(
    base_currency: str = Query("CNY", description="折算基准币种"),
    db: AsyncSession = Depends(get_db),
):
    """获取资产分配统计（用于饼图）"""
    service = BrokerageAccountService()

    allocation = await service.get_portfolio_allocation(db, base_currency)

    return {
        "by_platform_type": {k: float(v) for k, v in allocation["by_platform_type"].items()},
        "by_currency": {k: float(v) for k, v in allocation["by_currency"].items()},
        "by_asset_type": {k: float(v) for k, v in allocation["by_asset_type"].items()},
    }


# ============ 汇率 API ============


@router.get("/exchange-rate")
async def get_exchange_rate(
    from_currency: str = Query(..., description="源币种"),
    to_currency: str = Query(..., description="目标币种"),
    db: AsyncSession = Depends(get_db),
):
    """获取汇率"""
    service = ExchangeRateService()

    try:
        rate = await service.get_rate(db, from_currency, to_currency)
        return {
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "rate": float(rate),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取汇率失败: {str(e)}")


@router.post("/exchange-rate/refresh")
async def refresh_exchange_rates(db: AsyncSession = Depends(get_db)):
    """刷新所有汇率"""
    service = ExchangeRateService()

    try:
        rates = await service.get_all_rates_for_base(db, "CNY")
        return {
            "message": "汇率已刷新",
            "rates": {k: float(v) for k, v in rates.items()},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新汇率失败: {str(e)}")
