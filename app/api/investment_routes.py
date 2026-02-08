"""投资 API 路由 - 交易记录、持仓管理、基金产品"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.investment_manager import InvestmentManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/investments", tags=["投资管理"])


# ============ Pydantic 请求/响应模型 ============

class TransactionCreateRequest(BaseModel):
    """创建交易记录请求"""
    asset_type: str = Field(..., description="资产类型: stock/fund/bond/bank_product/crypto")
    symbol: str = Field(..., description="代码: 600000, 000001, BTC")
    transaction_type: str = Field(..., description="交易类型: buy/sell/dividend/split/interest")
    quantity: float = Field(..., gt=0, description="数量")
    price: float = Field(..., ge=0, description="单价")
    transaction_date: datetime = Field(..., description="交易日期")
    name: Optional[str] = Field(None, description="名称")
    market: Optional[str] = Field(None, description="市场: A股/港股/美股/OKX")
    fees: float = Field(0, ge=0, description="手续费")
    currency: str = Field("CNY", description="货币: CNY/HKD/USD/USDT")
    account_name: str = Field("默认账户", description="账户名称")
    settlement_date: Optional[datetime] = Field(None, description="结算日期")
    notes: Optional[str] = Field(None, description="备注")
    extra_data: Optional[Dict] = Field(None, description="扩展数据")


class TransactionUpdateRequest(BaseModel):
    """更新交易记录请求"""
    quantity: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, ge=0)
    transaction_date: Optional[datetime] = None
    name: Optional[str] = None
    fees: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    extra_data: Optional[Dict] = None


class TransactionResponse(BaseModel):
    """交易记录响应"""
    id: int
    asset_type: str
    symbol: str
    name: Optional[str]
    market: Optional[str]
    transaction_type: str
    quantity: float
    price: float
    amount: float
    fees: float
    currency: str
    account_name: str
    transaction_date: datetime
    settlement_date: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class HoldingResponse(BaseModel):
    """持仓响应"""
    id: int
    asset_type: str
    symbol: str
    name: Optional[str]
    market: Optional[str]
    quantity: float
    avg_cost: float
    total_cost: float
    currency: str
    account_name: str
    first_buy_date: Optional[datetime]
    last_transaction_date: Optional[datetime]

    class Config:
        from_attributes = True


class FundProductCreateRequest(BaseModel):
    """创建基金/理财产品请求"""
    product_type: str = Field(..., description="产品类型: fund/bond/bank_product")
    symbol: str = Field(..., description="产品代码")
    name: str = Field(..., description="产品名称")
    issuer: Optional[str] = Field(None, description="发行机构")
    risk_level: Optional[str] = Field(None, description="风险等级: R1-R5")
    expected_return: Optional[float] = Field(None, description="预期年化收益率")
    nav: Optional[float] = Field(None, description="最新净值")
    nav_date: Optional[datetime] = Field(None, description="净值日期")
    currency: str = Field("CNY", description="货币")
    min_investment: Optional[float] = Field(None, description="最低投资金额")
    redemption_days: Optional[int] = Field(None, description="赎回到账天数")
    extra_data: Optional[Dict] = Field(None, description="扩展数据")


class FundProductResponse(BaseModel):
    """基金/理财产品响应"""
    id: int
    product_type: str
    symbol: str
    name: str
    issuer: Optional[str]
    risk_level: Optional[str]
    expected_return: Optional[float]
    nav: Optional[float]
    nav_date: Optional[datetime]
    currency: str
    min_investment: Optional[float]
    redemption_days: Optional[int]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NavUpdateRequest(BaseModel):
    """更新净值请求"""
    nav: float = Field(..., gt=0, description="最新净值")
    nav_date: Optional[datetime] = Field(None, description="净值日期")


class PortfolioSummaryResponse(BaseModel):
    """投资组合汇总响应"""
    total_cost: float
    holdings_count: int
    by_asset_type: Dict
    by_account: Dict


# ============ 交易记录 API ============

@router.post("/transactions", response_model=TransactionResponse)
async def create_transaction(
    request: TransactionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """录入一笔交易记录"""
    manager = InvestmentManager()

    try:
        transaction = await manager.add_transaction(
            db=db,
            asset_type=request.asset_type,
            symbol=request.symbol,
            transaction_type=request.transaction_type,
            quantity=Decimal(str(request.quantity)),
            price=Decimal(str(request.price)),
            transaction_date=request.transaction_date,
            name=request.name,
            market=request.market,
            fees=Decimal(str(request.fees)),
            currency=request.currency,
            account_name=request.account_name,
            settlement_date=request.settlement_date,
            notes=request.notes,
            extra_data=request.extra_data,
        )
        return transaction
    except Exception as e:
        logger.error(f"创建交易记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    asset_type: Optional[str] = Query(None, description="资产类型"),
    symbol: Optional[str] = Query(None, description="代码"),
    market: Optional[str] = Query(None, description="市场"),
    account_name: Optional[str] = Query(None, description="账户名称"),
    transaction_type: Optional[str] = Query(None, description="交易类型"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """查询交易记录"""
    manager = InvestmentManager()

    transactions = await manager.get_transactions(
        db=db,
        asset_type=asset_type,
        symbol=symbol,
        market=market,
        account_name=account_name,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return transactions


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单条交易记录"""
    manager = InvestmentManager()

    transaction = await manager.get_transaction(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    return transaction


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    request: TransactionUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新交易记录"""
    manager = InvestmentManager()

    # 构建更新数据
    update_data = {}
    if request.quantity is not None:
        update_data["quantity"] = Decimal(str(request.quantity))
    if request.price is not None:
        update_data["price"] = Decimal(str(request.price))
    if request.transaction_date is not None:
        update_data["transaction_date"] = request.transaction_date
    if request.name is not None:
        update_data["name"] = request.name
    if request.fees is not None:
        update_data["fees"] = Decimal(str(request.fees))
    if request.notes is not None:
        update_data["notes"] = request.notes
    if request.extra_data is not None:
        update_data["extra_data"] = request.extra_data

    transaction = await manager.update_transaction(db, transaction_id, **update_data)
    if not transaction:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    return transaction


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除交易记录"""
    manager = InvestmentManager()

    success = await manager.delete_transaction(db, transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    return {"message": "删除成功", "id": transaction_id}


# ============ 持仓 API ============

@router.get("/holdings", response_model=List[HoldingResponse])
async def get_holdings(
    asset_type: Optional[str] = Query(None, description="资产类型"),
    account_name: Optional[str] = Query(None, description="账户名称"),
    include_zero: bool = Query(False, description="是否包含零持仓"),
    db: AsyncSession = Depends(get_db),
):
    """获取持仓汇总"""
    manager = InvestmentManager()

    holdings = await manager.get_holdings(
        db=db,
        asset_type=asset_type,
        account_name=account_name,
        include_zero=include_zero,
    )
    return holdings


@router.get("/holdings/{symbol}/history", response_model=List[TransactionResponse])
async def get_holding_history(
    symbol: str,
    account_name: Optional[str] = Query(None, description="账户名称"),
    db: AsyncSession = Depends(get_db),
):
    """获取单个资产的交易历史"""
    manager = InvestmentManager()

    transactions = await manager.get_transaction_history(
        db=db,
        symbol=symbol,
        account_name=account_name,
    )
    return transactions


@router.get("/holdings/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    account_name: Optional[str] = Query(None, description="账户名称"),
    db: AsyncSession = Depends(get_db),
):
    """获取投资组合汇总"""
    manager = InvestmentManager()

    summary = await manager.get_portfolio_summary(db, account_name)
    return summary


# ============ 基金/理财产品 API ============

@router.post("/funds", response_model=FundProductResponse)
async def create_fund_product(
    request: FundProductCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """添加基金/理财产品"""
    manager = InvestmentManager()

    try:
        product = await manager.add_fund_product(
            db=db,
            product_type=request.product_type,
            symbol=request.symbol,
            name=request.name,
            issuer=request.issuer,
            risk_level=request.risk_level,
            expected_return=Decimal(str(request.expected_return)) if request.expected_return else None,
            nav=Decimal(str(request.nav)) if request.nav else None,
            nav_date=request.nav_date,
            currency=request.currency,
            min_investment=Decimal(str(request.min_investment)) if request.min_investment else None,
            redemption_days=request.redemption_days,
            extra_data=request.extra_data,
        )
        return product
    except Exception as e:
        logger.error(f"创建产品失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funds", response_model=List[FundProductResponse])
async def get_fund_products(
    product_type: Optional[str] = Query(None, description="产品类型"),
    is_active: bool = Query(True, description="是否启用"),
    db: AsyncSession = Depends(get_db),
):
    """获取基金/理财产品列表"""
    manager = InvestmentManager()

    products = await manager.get_fund_products(
        db=db,
        product_type=product_type,
        is_active=is_active,
    )
    return products


@router.get("/funds/{symbol}", response_model=FundProductResponse)
async def get_fund_product(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单个基金/理财产品"""
    manager = InvestmentManager()

    product = await manager.get_fund_product(db, symbol)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


@router.put("/funds/{symbol}/nav", response_model=FundProductResponse)
async def update_fund_nav(
    symbol: str,
    request: NavUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新基金净值"""
    manager = InvestmentManager()

    product = await manager.update_fund_nav(
        db=db,
        symbol=symbol,
        nav=Decimal(str(request.nav)),
        nav_date=request.nav_date,
    )
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product
