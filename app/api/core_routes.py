"""
核心API路由 - Phase 1
账户管理、预算管理、支出录入
"""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.core import (
    Account,
    Holding,
    CoreInvestmentTransaction,
    Budget,
    Expense,
    ExpenseCategory,
    CoreCashFlow,
    CoreTransfer,
    MarketSyncLog,
    Liability,
    LiabilityPayment,
)

router = APIRouter(prefix="/core", tags=["核心功能"])


# ============ Pydantic Models ============


class AccountCreate(BaseModel):
    name: str = Field(..., description="账户名称")
    account_type: str = Field(..., description="账户类型: cash/investment")
    institution: Optional[str] = Field(None, description="机构名称")
    account_number: Optional[str] = Field(None, description="账号")
    initial_balance: Decimal = Field(Decimal("0"), description="初始余额")
    currency: str = Field("CNY", description="币种")
    notes: Optional[str] = Field(None, description="备注")


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    institution: Optional[str] = None
    account_number: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class AccountResponse(BaseModel):
    id: int
    name: str
    account_type: str
    institution: Optional[str]
    account_number: Optional[str]
    balance: Decimal  # 基础余额（cash账户=余额, 投资账户=可用现金不含高流动性资产）
    holdings_value: Optional[Decimal]  # 仅投资账户有效：持仓市值（不含高流动性资产）
    total_value: Decimal  # 总资产（cash账户=balance, 投资账户=可用现金+持仓市值）
    available_cash: Optional[Decimal]  # 可用现金（仅投资账户：含余额宝等高流动性资产）
    currency: str
    is_active: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ExpenseCreate(BaseModel):
    account_id: int = Field(..., description="现金账户ID")
    budget_id: Optional[int] = Field(None, description="预算ID")
    amount: Decimal = Field(..., gt=0, description="金额")
    expense_date: date = Field(..., description="支出日期")
    category: str = Field(..., description="一级分类")
    subcategory: Optional[str] = Field(None, description="二级分类")
    is_shared: bool = Field(False, description="是否共同开销")
    merchant: Optional[str] = Field(None, description="商家/地点")
    payment_method: Optional[str] = Field(None, description="支付方式")
    participants: Optional[List[str]] = Field(None, description="参与人")
    tags: Optional[List[str]] = Field(None, description="标签")
    notes: Optional[str] = Field(None, description="备注")


class ExpenseResponse(BaseModel):
    id: int
    account_id: int
    budget_id: Optional[int]
    amount: Decimal
    expense_date: date
    category: str
    subcategory: Optional[str]
    is_shared: bool
    merchant: Optional[str]
    payment_method: Optional[str]
    participants: Optional[List[str]]
    tags: Optional[List[str]]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class BudgetCreate(BaseModel):
    name: str = Field(..., description="预算名称")
    budget_type: str = Field(..., description="类型: periodic/project")
    amount: Decimal = Field(..., gt=0, description="预算总额")
    period_start: date = Field(..., description="开始日期")
    period_end: date = Field(..., description="结束日期")
    associated_account_ids: Optional[List[int]] = Field(None, description="关联账户ID列表")
    notes: Optional[str] = Field(None, description="备注")


class BudgetResponse(BaseModel):
    id: int
    name: str
    budget_type: str
    amount: Decimal
    spent: Decimal
    remaining: Decimal
    period_start: date
    period_end: date
    status: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    category: str
    subcategories: List[str]


class HoldingCreate(BaseModel):
    account_id: int = Field(..., description="所属投资账户ID")
    symbol: str = Field(..., max_length=50, description="资产代码")
    name: str = Field(..., max_length=100, description="资产名称")
    asset_type: str = Field(..., description="资产类型: stock/fund/bond/crypto/money_market")
    is_liquid: bool = Field(False, description="是否为高流动性资产(如余额宝)")
    quantity: Decimal = Field(..., gt=0, description="数量")
    avg_cost: Decimal = Field(..., gt=0, description="平均成本")
    current_price: Optional[Decimal] = Field(None, description="当前价格")
    current_value: Optional[Decimal] = Field(None, description="当前市值")
    notes: Optional[str] = Field(None, description="备注")


class HoldingUpdate(BaseModel):
    symbol: Optional[str] = None
    name: Optional[str] = None
    quantity: Optional[Decimal] = Field(None, gt=0)
    avg_cost: Optional[Decimal] = Field(None, gt=0)
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class HoldingResponse(BaseModel):
    id: int
    account_id: int
    symbol: str
    name: str
    asset_type: str
    is_liquid: bool
    quantity: Decimal
    avg_cost: Decimal
    current_price: Optional[Decimal]
    current_value: Optional[Decimal]
    currency: str
    is_active: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TransferCreate(BaseModel):
    from_account_id: int = Field(..., description="转出账户ID")
    to_account_id: int = Field(..., description="转入账户ID")
    amount: Decimal = Field(..., gt=0, description="转账金额")
    notes: Optional[str] = Field(None, description="备注")


class TransferResponse(BaseModel):
    id: int
    from_account_id: int
    to_account_id: int
    amount: Decimal
    transfer_type: str
    status: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True




class LiabilityCreate(BaseModel):
    name: str
    liability_type: str  # mortgage/car_loan/credit_card/other
    institution: Optional[str] = None
    original_amount: Decimal
    remaining_amount: Decimal
    monthly_payment: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    payment_day: Optional[int] = None
    currency: str = "CNY"
    notes: Optional[str] = None


class LiabilityUpdate(BaseModel):
    name: Optional[str] = None
    institution: Optional[str] = None
    remaining_amount: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    end_date: Optional[date] = None
    payment_day: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class LiabilityResponse(BaseModel):
    id: int
    name: str
    liability_type: str
    institution: Optional[str]
    original_amount: Decimal
    remaining_amount: Decimal
    monthly_payment: Optional[Decimal]
    interest_rate: Optional[Decimal]
    start_date: Optional[date]
    end_date: Optional[date]
    payment_day: Optional[int]
    currency: str
    is_active: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class LiabilityPaymentCreate(BaseModel):
    account_id: Optional[int] = None
    amount: Decimal
    principal: Optional[Decimal] = None
    interest: Optional[Decimal] = None
    payment_date: date
    notes: Optional[str] = None


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    associated_account_ids: Optional[List[int]] = None
    notes: Optional[str] = None


# ============ Account APIs ============


@router.post("/accounts", response_model=AccountResponse)
async def create_account(request: AccountCreate, db: AsyncSession = Depends(get_db)):
    """创建账户"""
    account = Account(
        name=request.name,
        account_type=request.account_type,
        institution=request.institution,
        account_number=request.account_number,
        balance=request.initial_balance,
        currency=request.currency,
        notes=request.notes,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    # 如果有初始余额，创建现金流水记录
    if request.initial_balance > 0:
        cash_flow = CoreCashFlow(
            account_id=account.id,
            flow_type="initial",
            amount=request.initial_balance,
            balance_after=request.initial_balance,
            description="初始余额",
        )
        db.add(cash_flow)
        await db.commit()

    return _account_to_response(account)


def _account_to_response(account: Account) -> dict:
    """将Account模型转换为响应字典，包含计算字段"""
    if account.account_type == "investment":
        # 计算持仓市值
        holdings_value = Decimal("0")
        available_cash = account.balance

        # 检查holdings是否已加载
        if (
            hasattr(account, "_sa_instance_state") or True
        ):  # Always try to access if it's an Account
            try:
                if account.holdings:
                    for h in account.holdings:
                        if h.is_active:
                            val = h.current_value if h.current_value else Decimal("0")
                            holdings_value += val
                            if h.is_liquid:
                                available_cash += val
            except Exception:
                # holdings未加载，使用缓存值
                holdings_value = account.holdings_value if account.holdings_value else Decimal("0")

        total_value = account.balance + holdings_value
    else:
        holdings_value = None
        total_value = account.balance
        available_cash = None

    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "institution": account.institution,
        "account_number": account.account_number,
        "balance": str(account.balance),
        "holdings_value": str(holdings_value) if holdings_value is not None else None,
        "total_value": str(total_value),
        "available_cash": str(available_cash) if available_cash is not None else None,
        "currency": account.currency,
        "is_active": account.is_active,
        "notes": account.notes,
        "created_at": account.created_at,
    }


@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    account_type: Optional[str] = Query(None, description="按类型筛选: cash/investment"),
    is_active: bool = Query(True, description="是否只显示活跃账户"),
    db: AsyncSession = Depends(get_db),
):
    """获取账户列表"""
    from sqlalchemy.orm import selectinload

    stmt = select(Account)

    # 投资账户需要加载holdings来计算市值
    if account_type == "investment" or account_type is None:
        stmt = stmt.options(selectinload(Account.holdings))

    if account_type:
        stmt = stmt.where(Account.account_type == account_type)
    if is_active is not None:
        stmt = stmt.where(Account.is_active == is_active)

    stmt = stmt.order_by(Account.account_type, Account.name)
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    # 转换为响应格式
    return [_account_to_response(acc) for acc in accounts]


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个账户"""
    from sqlalchemy.orm import selectinload

    stmt = select(Account).options(selectinload(Account.holdings)).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    return _account_to_response(account)


@router.put("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int, request: AccountUpdate, db: AsyncSession = Depends(get_db)
):
    """更新账户"""
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    update_data = request.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(account, key, value)

    await db.commit()
    await db.refresh(account)
    return _account_to_response(account)


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """删除账户"""
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    await db.delete(account)
    await db.commit()

    return {"message": "账户已删除", "account_id": account_id}


# ============ Expense APIs ============


@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(request: ExpenseCreate, db: AsyncSession = Depends(get_db)):
    """
    录入支出
    1. 验证账户存在（cash或investment）
    2. 检查账户余额充足
    3. 更新预算已支出额度
    4. 扣减账户余额
    5. 创建支出记录
    6. 创建现金流水
    """
    # 1. 检查账户存在
    stmt = select(Account).where(Account.id == request.account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    # 2. 检查余额充足
    if account.balance < request.amount:
        # 如果是投资账户，给更详细的提示
        if account.account_type == "investment":
            raise HTTPException(
                status_code=400,
                detail=f"投资账户余额不足，当前余额: ¥{account.balance}。如需使用余额宝等高流动性资产，请先转出到余额。",
            )
        else:
            raise HTTPException(status_code=400, detail="账户余额不足")

    # 3. 如果有预算，检查并更新预算
    budget = None
    if request.budget_id:
        stmt = select(Budget).where(and_(Budget.id == request.budget_id, Budget.status == "active"))
        result = await db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            raise HTTPException(status_code=404, detail="预算不存在或已结束")

        if budget.remaining < request.amount:
            raise HTTPException(status_code=400, detail="预算额度不足")

        # 更新预算
        budget.spent += request.amount
        budget.remaining -= request.amount

    # 4. 扣减账户余额
    # 注意：对于投资账户，这里扣减的是balance（基础余额），不影响持仓
    old_balance = account.balance
    account.balance -= request.amount

    # 5. 创建支出记录
    expense = Expense(
        account_id=request.account_id,
        budget_id=request.budget_id,
        amount=request.amount,
        expense_date=request.expense_date,
        category=request.category,
        subcategory=request.subcategory,
        is_shared=request.is_shared,
        merchant=request.merchant,
        payment_method=request.payment_method,
        participants=request.participants,
        tags=request.tags,
        notes=request.notes,
    )
    db.add(expense)
    await db.flush()  # 获取expense.id

    # 6. 创建现金流水
    cash_flow = CoreCashFlow(
        account_id=request.account_id,
        flow_type="expense",
        amount=-request.amount,  # 负数表示支出
        balance_after=account.balance,
        expense_id=expense.id,
        description=f"支出: {request.category}",
    )
    db.add(cash_flow)

    await db.commit()
    await db.refresh(expense)

    return expense


@router.get("/expenses", response_model=List[ExpenseResponse])
async def list_expenses(
    account_id: Optional[int] = Query(None, description="按账户筛选"),
    budget_id: Optional[int] = Query(None, description="按预算筛选"),
    category: Optional[str] = Query(None, description="按分类筛选"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """获取支出列表"""
    stmt = select(Expense).order_by(desc(Expense.expense_date))

    if account_id:
        stmt = stmt.where(Expense.account_id == account_id)
    if budget_id:
        stmt = stmt.where(Expense.budget_id == budget_id)
    if category:
        stmt = stmt.where(Expense.category == category)
    if start_date:
        stmt = stmt.where(Expense.expense_date >= start_date)
    if end_date:
        stmt = stmt.where(Expense.expense_date <= end_date)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    expenses = result.scalars().all()
    return expenses


# ============ Budget APIs ============


@router.post("/budgets", response_model=BudgetResponse)
async def create_budget(request: BudgetCreate, db: AsyncSession = Depends(get_db)):
    """创建预算"""
    budget = Budget(
        name=request.name,
        budget_type=request.budget_type,
        amount=request.amount,
        spent=Decimal("0"),
        remaining=request.amount,
        period_start=request.period_start,
        period_end=request.period_end,
        associated_account_ids=request.associated_account_ids,
        notes=request.notes,
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


@router.get("/budgets", response_model=List[BudgetResponse])
async def list_budgets(
    budget_type: Optional[str] = Query(None, description="按类型筛选: periodic/project"),
    status: Optional[str] = Query(None, description="按状态筛选: active/completed/cancelled"),
    db: AsyncSession = Depends(get_db),
):
    """获取预算列表"""
    stmt = select(Budget).order_by(desc(Budget.period_start))

    if budget_type:
        stmt = stmt.where(Budget.budget_type == budget_type)
    if status:
        stmt = stmt.where(Budget.status == status)

    result = await db.execute(stmt)
    budgets = result.scalars().all()
    return budgets


@router.get("/budgets/{budget_id}", response_model=BudgetResponse)
async def get_budget(budget_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个预算"""
    stmt = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(status_code=404, detail="预算不存在")

    return budget


@router.post("/budgets/{budget_id}/complete")
async def complete_budget(budget_id: int, db: AsyncSession = Depends(get_db)):
    """完成预算（结算）"""
    stmt = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(status_code=404, detail="预算不存在")

    if budget.status != "active":
        raise HTTPException(status_code=400, detail="预算已结束")

    budget.status = "completed"
    await db.commit()

    return {
        "message": "预算已结算",
        "budget_id": budget_id,
        "planned": budget.amount,
        "spent": budget.spent,
        "remaining": budget.remaining,
    }


# ============ Category APIs ============


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """获取支出分类列表"""
    stmt = (
        select(ExpenseCategory)
        .where(ExpenseCategory.is_active == True)
        .order_by(ExpenseCategory.category, ExpenseCategory.sort_order)
    )
    result = await db.execute(stmt)
    categories = result.scalars().all()

    # 组织成层级结构
    category_map = {}
    for cat in categories:
        if cat.category not in category_map:
            category_map[cat.category] = []
        category_map[cat.category].append(cat.subcategory)

    return [
        CategoryResponse(category=cat, subcategories=subs) for cat, subs in category_map.items()
    ]


# ============ Dashboard API ============


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """获取仪表盘数据"""
    # 总资产
    stmt = select(func.sum(Account.balance)).where(Account.is_active == True)
    result = await db.execute(stmt)
    total_assets = result.scalar() or Decimal("0")

    # 现金余额
    stmt = select(func.sum(Account.balance)).where(
        and_(Account.account_type == "cash", Account.is_active == True)
    )
    result = await db.execute(stmt)
    cash_balance = result.scalar() or Decimal("0")

    # 投资市值（简化，实际应该从holdings计算）
    stmt = select(func.sum(Account.balance)).where(
        and_(Account.account_type == "investment", Account.is_active == True)
    )
    result = await db.execute(stmt)
    investment_value = result.scalar() or Decimal("0")

    # 进行中的预算
    stmt = (
        select(Budget)
        .where(and_(Budget.status == "active", Budget.period_end >= date.today()))
        .order_by(Budget.period_end)
    )
    result = await db.execute(stmt)
    active_budgets = result.scalars().all()

    # 负债总额
    stmt = select(func.sum(Liability.remaining_amount)).where(Liability.is_active == True)
    result = await db.execute(stmt)
    total_liability = result.scalar() or Decimal("0")

    # 净资产
    net_worth = total_assets - total_liability

    # 本月支出总额
    today = date.today()
    month_start = today.replace(day=1)
    stmt = select(func.sum(Expense.amount)).where(
        and_(Expense.expense_date >= month_start, Expense.expense_date <= today)
    )
    result = await db.execute(stmt)
    monthly_expense_total = result.scalar() or Decimal("0")

    return {
        "total_assets": str(total_assets),
        "cash_balance": str(cash_balance),
        "investment_value": str(investment_value),
        "total_liability": str(total_liability),
        "net_worth": str(net_worth),
        "monthly_expense_total": str(monthly_expense_total),
        "active_budgets": [
            {
                "id": b.id,
                "name": b.name,
                "type": b.budget_type,
                "amount": str(b.amount),
                "spent": str(b.spent),
                "remaining": str(b.remaining),
                "period_end": b.period_end,
            }
            for b in active_budgets
        ],
    }


# ============ Holding APIs ============


@router.post("/holdings", response_model=HoldingResponse)
async def create_holding(request: HoldingCreate, db: AsyncSession = Depends(get_db)):
    """添加持仓"""
    # 验证账户存在且为投资账户
    stmt = select(Account).where(
        and_(Account.id == request.account_id, Account.account_type == "investment")
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="投资账户不存在")

    # 创建持仓
    holding = Holding(
        account_id=request.account_id,
        symbol=request.symbol,
        name=request.name,
        asset_type=request.asset_type,
        is_liquid=request.is_liquid,
        quantity=request.quantity,
        avg_cost=request.avg_cost,
        total_cost=request.quantity * request.avg_cost,
        current_price=request.current_price,
        current_value=request.current_value,
        currency=account.currency,
        is_active=True,
        notes=request.notes,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)

    # 更新账户的持仓市值缓存
    await db.refresh(account, attribute_names=["holdings"])
    account.update_holdings_value()
    await db.commit()

    return holding


@router.get("/holdings", response_model=List[HoldingResponse])
async def list_holdings(
    account_id: Optional[int] = Query(None, description="按账户筛选"),
    is_liquid: Optional[bool] = Query(None, description="按流动性筛选"),
    is_active: bool = Query(True, description="是否只显示活跃持仓"),
    db: AsyncSession = Depends(get_db),
):
    """获取持仓列表"""
    stmt = select(Holding).where(Holding.is_active == is_active)

    if account_id:
        stmt = stmt.where(Holding.account_id == account_id)
    if is_liquid is not None:
        stmt = stmt.where(Holding.is_liquid == is_liquid)

    stmt = stmt.order_by(Holding.is_liquid.desc(), Holding.symbol)
    result = await db.execute(stmt)
    holdings = result.scalars().all()
    return holdings


@router.get("/holdings/{holding_id}", response_model=HoldingResponse)
async def get_holding(holding_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个持仓"""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()

    if not holding:
        raise HTTPException(status_code=404, detail="持仓不存在")

    return holding


@router.put("/holdings/{holding_id}", response_model=HoldingResponse)
async def update_holding(
    holding_id: int, request: HoldingUpdate, db: AsyncSession = Depends(get_db)
):
    """更新持仓"""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()

    if not holding:
        raise HTTPException(status_code=404, detail="持仓不存在")

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(holding, key, value)

    # 如果更新了数量或成本，重新计算总成本
    if "quantity" in update_data or "avg_cost" in update_data:
        holding.total_cost = holding.quantity * holding.avg_cost

    # 如果更新了数量或价格，重新计算市值
    if "quantity" in update_data or "current_price" in update_data:
        if holding.current_price:
            holding.current_value = holding.quantity * holding.current_price

    await db.commit()
    await db.refresh(holding)

    # 更新账户的持仓市值缓存
    stmt = (
        select(Account)
        .options(selectinload(Account.holdings))
        .where(Account.id == holding.account_id)
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account:
        account.update_holdings_value()
        await db.commit()

    return holding


@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: int, db: AsyncSession = Depends(get_db)):
    """删除持仓（清仓）"""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()

    if not holding:
        raise HTTPException(status_code=404, detail="持仓不存在")

    account_id = holding.account_id
    await db.delete(holding)
    await db.commit()

    # 更新账户的持仓市值缓存
    stmt = select(Account).options(selectinload(Account.holdings)).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account:
        account.update_holdings_value()
        await db.commit()

    return {"message": "持仓已删除", "holding_id": holding_id}


# ============ Transfer APIs ============


def _determine_transfer_type(from_account: Account, to_account: Account) -> str:
    """根据账户类型确定转账类型"""
    if from_account.account_type == "cash" and to_account.account_type == "cash":
        return "cash_to_cash"
    elif from_account.account_type == "cash" and to_account.account_type == "investment":
        return "cash_to_investment"
    elif from_account.account_type == "investment" and to_account.account_type == "cash":
        return "investment_to_cash"
    elif from_account.account_type == "investment" and to_account.account_type == "investment":
        return "investment_to_investment"
    else:
        return "unknown"


@router.post("/transfers", response_model=TransferResponse)
async def create_transfer(request: TransferCreate, db: AsyncSession = Depends(get_db)):
    """创建转账"""
    # 验证两个账户存在
    stmt_from = select(Account).where(Account.id == request.from_account_id)
    stmt_to = select(Account).where(Account.id == request.to_account_id)

    result_from = await db.execute(stmt_from)
    from_account = result_from.scalar_one_or_none()

    result_to = await db.execute(stmt_to)
    to_account = result_to.scalar_one_or_none()

    if not from_account:
        raise HTTPException(status_code=404, detail="转出账户不存在")
    if not to_account:
        raise HTTPException(status_code=404, detail="转入账户不存在")

    if from_account.id == to_account.id:
        raise HTTPException(status_code=400, detail="不能向同一账户转账")

    # 验证余额充足
    if from_account.balance < request.amount:
        raise HTTPException(
            status_code=400, detail=f"账户余额不足，当前余额: {from_account.balance}"
        )

    # 确定转账类型
    transfer_type = _determine_transfer_type(from_account, to_account)

    # 扣减转出账户余额
    from_account.balance -= request.amount
    from_account.updated_at = datetime.now()

    # 增加转入账户余额
    to_account.balance += request.amount
    to_account.updated_at = datetime.now()

    # 创建转账记录
    transfer = CoreTransfer(
        from_account_id=request.from_account_id,
        to_account_id=request.to_account_id,
        amount=request.amount,
        transfer_type=transfer_type,
        notes=request.notes,
        status="completed",
    )
    db.add(transfer)

    # 创建转出账户的现金流水
    cash_flow_from = CoreCashFlow(
        account_id=request.from_account_id,
        flow_type="transfer_out",
        amount=-request.amount,
        balance_after=from_account.balance,
        description=f"转账至 {to_account.name}",
    )
    db.add(cash_flow_from)

    # 创建转入账户的现金流水
    cash_flow_to = CoreCashFlow(
        account_id=request.to_account_id,
        flow_type="transfer_in",
        amount=request.amount,
        balance_after=to_account.balance,
        description=f"转账自 {from_account.name}",
    )
    db.add(cash_flow_to)

    await db.commit()
    await db.refresh(transfer)

    return transfer


@router.get("/transfers", response_model=List[TransferResponse])
async def list_transfers(
    from_account_id: Optional[int] = Query(None, description="按转出账户筛选"),
    to_account_id: Optional[int] = Query(None, description="按转入账户筛选"),
    transfer_type: Optional[str] = Query(None, description="按类型筛选"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取转账记录"""
    stmt = select(CoreTransfer)

    if from_account_id:
        stmt = stmt.where(CoreTransfer.from_account_id == from_account_id)
    if to_account_id:
        stmt = stmt.where(CoreTransfer.to_account_id == to_account_id)
    if transfer_type:
        stmt = stmt.where(CoreTransfer.transfer_type == transfer_type)

    stmt = stmt.order_by(CoreTransfer.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    transfers = result.scalars().all()
    return transfers


# ============ Market Sync API ============


def _resolve_market(holding: Holding) -> "Optional[Market]":
    """根据持仓的 market / asset_type / symbol 推断 StockClient Market 枚举"""
    from app.services.stock_client import Market

    market_str = (holding.market or "").strip()
    # 直接匹配
    mapping = {"A股": Market.A_SHARE, "港股": Market.HK, "美股": Market.US}
    if market_str in mapping:
        return mapping[market_str]

    # 按 asset_type 排除非股票类
    if holding.asset_type in ("money_market", "crypto"):
        return None

    # 根据 symbol 格式猜测
    sym = holding.symbol.strip()
    if sym.isdigit():
        if len(sym) <= 5:
            return Market.HK
        return Market.A_SHARE
    if sym.isalpha():
        return Market.US

    return None


@router.post("/holdings/sync")
async def sync_holdings_value(db: AsyncSession = Depends(get_db)):
    """
    同步所有持仓市值
    Phase 3: 使用 AkShare 真实行情数据
    """
    from app.services.stock_client import StockClient

    client = StockClient()

    # 获取所有活跃持仓
    stmt = select(Holding).where(Holding.is_active == True)
    result = await db.execute(stmt)
    holdings = result.scalars().all()

    synced_count = 0
    failed_count = 0
    total_value = Decimal("0")
    errors = []

    # 分离需要行情的持仓和不需要的持仓
    holdings_to_fetch = []  # (index, holding, market)
    for i, holding in enumerate(holdings):
        market = _resolve_market(holding)
        if market is None:
            # 无法确定市场的持仓（如货币基金、加密货币），保留现有价格
            if holding.current_value:
                total_value += holding.current_value
        else:
            holdings_to_fetch.append((i, holding, market))

    # 并发获取所有行情
    async def _fetch_one(holding, market):
        return await client.fetch_realtime_quote(holding.symbol, market)

    tasks = [_fetch_one(h, m) for _, h, m in holdings_to_fetch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (_, holding, market), result in zip(holdings_to_fetch, results):
        if isinstance(result, Exception):
            if holding.current_value:
                total_value += holding.current_value
            failed_count += 1
            errors.append(f"{holding.symbol}: {str(result)[:100]}")
        elif result and result.current_price > 0:
            holding.current_price = result.current_price
            holding.current_value = (holding.quantity * result.current_price).quantize(Decimal("0.01"))
            holding.last_sync_at = datetime.now()
            holding.updated_at = datetime.now()

            total_value += holding.current_value
            synced_count += 1
        else:
            # 行情未获取到，保留现有价格
            if holding.current_value:
                total_value += holding.current_value
            failed_count += 1
            errors.append(f"{holding.symbol}: 未获取到行情")

    # 更新账户的持仓市值缓存
    account_ids = set(h.account_id for h in holdings)
    for account_id in account_ids:
        stmt = (
            select(Account).options(selectinload(Account.holdings)).where(Account.id == account_id)
        )
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        if account:
            account.update_holdings_value()

    # 记录同步日志
    sync_log = MarketSyncLog(
        total_value=total_value,
        holdings_count=synced_count,
        status="success" if failed_count == 0 else "partial",
        details={"method": "akshare", "failed": failed_count, "errors": errors[:10]},
    )
    db.add(sync_log)
    await db.commit()

    return {
        "message": "市值同步完成",
        "synced_count": synced_count,
        "failed_count": failed_count,
        "total_value": total_value,
        "synced_at": datetime.now(),
    }


# ============ Budget Available Funds API ============


@router.get("/budgets/{budget_id}/available-funds")
async def get_budget_available_funds(budget_id: int, db: AsyncSession = Depends(get_db)):
    """
    获取预算关联账户的可用资金总额
    计算方式：sum(关联账户的available_cash)
    """
    # 获取预算
    stmt = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(status_code=404, detail="预算不存在")

    # 获取关联账户
    accounts_info = []
    total_available = Decimal("0")

    if budget.associated_account_ids:
        for account_id in budget.associated_account_ids:
            stmt = (
                select(Account)
                .options(selectinload(Account.holdings))
                .where(Account.id == account_id)
            )
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()

            if account:
                available = account.available_cash
                total_available += available

                accounts_info.append(
                    {
                        "account_id": account.id,
                        "name": account.name,
                        "account_type": account.account_type,
                        "available_cash": available,
                        "currency": account.currency,
                    }
                )

    return {
        "budget_id": budget_id,
        "budget_name": budget.name,
        "total_available": total_available,
        "accounts": accounts_info,
    }


# ============ Liability APIs ============


@router.post("/liabilities", response_model=LiabilityResponse)
async def create_liability(request: LiabilityCreate, db: AsyncSession = Depends(get_db)):
    """创建负债"""
    if request.liability_type not in ("mortgage", "car_loan", "credit_card", "other"):
        raise HTTPException(status_code=400, detail="负债类型无效，可选: mortgage/car_loan/credit_card/other")

    liability = Liability(**request.model_dump())
    db.add(liability)
    await db.commit()
    await db.refresh(liability)
    return liability


@router.get("/liabilities", response_model=List[LiabilityResponse])
async def list_liabilities(
    liability_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取负债列表"""
    stmt = select(Liability).order_by(desc(Liability.created_at))
    if liability_type:
        stmt = stmt.where(Liability.liability_type == liability_type)
    if is_active is not None:
        stmt = stmt.where(Liability.is_active == is_active)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/liabilities/{liability_id}", response_model=LiabilityResponse)
async def get_liability(liability_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个负债"""
    stmt = select(Liability).where(Liability.id == liability_id)
    result = await db.execute(stmt)
    liability = result.scalar_one_or_none()
    if not liability:
        raise HTTPException(status_code=404, detail="负债不存在")
    return liability


@router.put("/liabilities/{liability_id}", response_model=LiabilityResponse)
async def update_liability(liability_id: int, request: LiabilityUpdate, db: AsyncSession = Depends(get_db)):
    """更新负债"""
    stmt = select(Liability).where(Liability.id == liability_id)
    result = await db.execute(stmt)
    liability = result.scalar_one_or_none()
    if not liability:
        raise HTTPException(status_code=404, detail="负债不存在")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(liability, field, value)

    await db.commit()
    await db.refresh(liability)
    return liability


@router.delete("/liabilities/{liability_id}")
async def delete_liability(
    liability_id: int,
    force: bool = Query(False, description="强制删除（包括还款记录）"),
    db: AsyncSession = Depends(get_db),
):
    """删除负债"""
    stmt = select(Liability).where(Liability.id == liability_id)
    result = await db.execute(stmt)
    liability = result.scalar_one_or_none()
    if not liability:
        raise HTTPException(status_code=404, detail="负债不存在")

    # 检查是否有还款记录
    stmt = select(func.count()).select_from(LiabilityPayment).where(LiabilityPayment.liability_id == liability_id)
    result = await db.execute(stmt)
    payment_count = result.scalar()

    if payment_count > 0 and not force:
        raise HTTPException(status_code=400, detail=f"该负债有 {payment_count} 条还款记录，请使用 force=true 强制删除")

    await db.delete(liability)
    await db.commit()
    return {"message": "负债已删除", "id": liability_id}


@router.post("/liabilities/{liability_id}/payment")
async def create_liability_payment(
    liability_id: int, request: LiabilityPaymentCreate, db: AsyncSession = Depends(get_db)
):
    """记录负债还款"""
    stmt = select(Liability).where(Liability.id == liability_id)
    result = await db.execute(stmt)
    liability = result.scalar_one_or_none()
    if not liability:
        raise HTTPException(status_code=404, detail="负债不存在")

    # 如果指定了账户，扣减余额
    account = None
    if request.account_id:
        stmt = select(Account).where(Account.id == request.account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在")
        if account.balance < request.amount:
            raise HTTPException(status_code=400, detail="账户余额不足")
        account.balance -= request.amount

    # 减少剩余金额
    liability.remaining_amount -= request.amount

    # 创建还款记录
    payment = LiabilityPayment(
        liability_id=liability_id,
        account_id=request.account_id,
        amount=request.amount,
        principal=request.principal,
        interest=request.interest,
        payment_date=request.payment_date,
        notes=request.notes,
    )
    db.add(payment)

    # 如果指定了账户，创建现金流水
    if account:
        cash_flow = CoreCashFlow(
            account_id=account.id,
            flow_type="expense",
            amount=-request.amount,
            balance_after=account.balance,
            description=f"负债还款: {liability.name}",
        )
        db.add(cash_flow)

    await db.commit()
    return {"message": "还款已记录", "liability_id": liability_id, "remaining_amount": str(liability.remaining_amount)}


# ============ Budget Lifecycle APIs ============


@router.put("/budgets/{budget_id}", response_model=BudgetResponse)
async def update_budget(budget_id: int, request: BudgetUpdate, db: AsyncSession = Depends(get_db)):
    """更新预算"""
    stmt = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="预算不存在")

    update_data = request.model_dump(exclude_unset=True)

    # 如果更新了amount，同步更新remaining
    if "amount" in update_data:
        new_amount = update_data["amount"]
        budget.remaining = new_amount - budget.spent
        budget.amount = new_amount
        del update_data["amount"]

    for field, value in update_data.items():
        setattr(budget, field, value)

    await db.commit()
    await db.refresh(budget)
    return budget


@router.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: int, db: AsyncSession = Depends(get_db)):
    """删除预算"""
    stmt = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="预算不存在")

    if budget.status == "active" and budget.spent > 0:
        raise HTTPException(status_code=400, detail="活跃预算已有支出记录，请先取消或结算")

    await db.delete(budget)
    await db.commit()
    return {"message": "预算已删除", "id": budget_id}


@router.post("/budgets/{budget_id}/cancel")
async def cancel_budget(budget_id: int, db: AsyncSession = Depends(get_db)):
    """取消预算"""
    stmt = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="预算不存在")
    if budget.status != "active":
        raise HTTPException(status_code=400, detail="只能取消活跃状态的预算")

    budget.status = "cancelled"
    await db.commit()
    return {"message": "预算已取消", "budget_id": budget_id}


# ============ Expense Delete API ============


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: int, db: AsyncSession = Depends(get_db)):
    """删除支出，回滚账户余额和预算"""
    stmt = select(Expense).where(Expense.id == expense_id)
    result = await db.execute(stmt)
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="支出记录不存在")

    # 回滚账户余额
    stmt = select(Account).where(Account.id == expense.account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account:
        account.balance += expense.amount

    # 回滚预算
    if expense.budget_id:
        stmt = select(Budget).where(Budget.id == expense.budget_id)
        result = await db.execute(stmt)
        budget = result.scalar_one_or_none()
        if budget:
            budget.spent -= expense.amount
            budget.remaining += expense.amount

    await db.delete(expense)
    await db.commit()
    return {"message": "支出已删除并回滚", "id": expense_id}
