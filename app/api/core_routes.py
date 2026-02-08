"""
核心API路由 - Phase 1
账户管理、预算管理、支出录入
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from app.database import get_db
from app.models.core import (
    Account,
    Holding,
    CoreInvestmentTransaction,
    Budget,
    Expense,
    ExpenseCategory,
    CoreCashFlow,
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
    # 投资账户需要计算持仓市值
    if account.account_type == "investment":
        # 确保holdings已加载（懒加载问题）
        holdings_value = account.calculate_holdings_value()
        account.holdings_value = holdings_value

    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "institution": account.institution,
        "account_number": account.account_number,
        "balance": account.balance,
        "holdings_value": account.holdings_value if account.account_type == "investment" else None,
        "total_value": account.total_value,
        "available_cash": account.available_cash if account.account_type == "investment" else None,
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
    1. 扣减现金账户余额
    2. 更新预算已支出额度
    3. 创建支出记录
    4. 创建现金流水
    """
    # 1. 检查现金账户
    stmt = select(Account).where(
        and_(Account.id == request.account_id, Account.account_type == "cash")
    )
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="现金账户不存在")

    if account.balance < request.amount:
        raise HTTPException(status_code=400, detail="账户余额不足")

    # 2. 如果有预算，检查并更新预算
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

    # 3. 扣减现金账户余额
    old_balance = account.balance
    account.balance -= request.amount

    # 4. 创建支出记录
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

    # 5. 创建现金流水
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

    return {
        "total_assets": total_assets,
        "cash_balance": cash_balance,
        "investment_value": investment_value,
        "active_budgets": [
            {
                "id": b.id,
                "name": b.name,
                "type": b.budget_type,
                "amount": b.amount,
                "spent": b.spent,
                "remaining": b.remaining,
                "period_end": b.period_end,
            }
            for b in active_budgets
        ],
    }
