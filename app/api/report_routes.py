"""报表 API 路由 - Phase 4"""

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
report_service = ReportService()


# ============ Pydantic 响应模型 ============


class PeriodInfo(BaseModel):
    start_date: str
    end_date: str


class InvestmentPerformanceSummary(BaseModel):
    total_cost: str
    total_market_value: str
    total_pnl: str
    total_pnl_pct: str
    dividend_income: str
    holdings_count: int


class HoldingDetail(BaseModel):
    symbol: str
    name: Optional[str]
    asset_type: str
    quantity: str
    avg_cost: str
    current_price: Optional[str]
    cost: str
    market_value: str
    pnl: str
    pnl_pct: str
    account: str
    currency: str


class InvestmentPerformanceReport(BaseModel):
    period: PeriodInfo
    summary: InvestmentPerformanceSummary
    holdings: List[HoldingDetail]


class ExpenseSummary(BaseModel):
    total_amount: str
    expense_count: int
    daily_avg: str
    category_count: int


class CategoryBreakdown(BaseModel):
    category: str
    count: int
    amount: str
    percentage: str


class DailyTrend(BaseModel):
    date: str
    amount: str


class ExpenseSummaryReport(BaseModel):
    period: PeriodInfo
    summary: ExpenseSummary
    category_breakdown: List[CategoryBreakdown]
    daily_trend: List[DailyTrend]


class AccountSnapshotSummary(BaseModel):
    total_balance: str
    total_holdings_value: str
    total_net_worth: str
    accounts_count: int
    holdings_count: int


class AccountDetail(BaseModel):
    id: int
    name: str
    type: str
    institution: Optional[str]
    balance: str
    holdings_value: str
    net_worth: str
    currency: str
    balance_cny: str
    holdings_value_cny: str
    net_worth_cny: str


class HoldingSnapshot(BaseModel):
    symbol: str
    name: Optional[str]
    asset_type: str
    quantity: str
    avg_cost: str
    current_price: Optional[str]
    market_value: str
    cost: str
    pnl: str
    account_id: int
    currency: str


class AccountSnapshotReport(BaseModel):
    as_of_date: str
    summary: AccountSnapshotSummary
    accounts: List[AccountDetail]
    holdings: List[HoldingSnapshot]


# ============ API 端点 ============


@router.get(
    "/investment-performance",
    response_model=InvestmentPerformanceReport,
    summary="生成投资业绩报表",
)
async def get_investment_performance_report(
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: AsyncSession = Depends(get_db),
):
    """
    生成投资业绩报表

    包含：
    - 总盈亏、盈亏率
    - 分红收入
    - 持仓明细
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    # 限制日期范围（最多1年）
    days_diff = (end_date - start_date).days
    if days_diff > 365:
        raise HTTPException(status_code=400, detail="日期范围不能超过1年")

    report = await report_service.generate_investment_performance_report(
        db, start_date, end_date
    )
    return report


@router.get(
    "/expense-summary",
    response_model=ExpenseSummaryReport,
    summary="生成支出汇总报表",
)
async def get_expense_summary_report(
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
    category: Optional[str] = Query(None, description="分类筛选（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """
    生成支出汇总报表

    包含：
    - 总支出、日均支出
    - 分类明细
    - 每日趋势
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    # 限制日期范围（最多1年）
    days_diff = (end_date - start_date).days
    if days_diff > 365:
        raise HTTPException(status_code=400, detail="日期范围不能超过1年")

    report = await report_service.generate_expense_summary_report(
        db, start_date, end_date, category
    )
    return report


@router.get(
    "/account-snapshot",
    response_model=AccountSnapshotReport,
    summary="生成账户快照报表",
)
async def get_account_snapshot_report(
    as_of_date: Optional[date] = Query(None, description="快照日期（默认今天）"),
    db: AsyncSession = Depends(get_db),
):
    """
    生成账户快照报表

    包含：
    - 净资产汇总
    - 账户明细
    - 持仓明细
    """
    report = await report_service.generate_account_snapshot_report(db, as_of_date)
    return report
