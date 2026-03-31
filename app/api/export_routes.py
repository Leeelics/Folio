"""导出 API 路由 - Phase 4"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.export_service import ExportService

router = APIRouter(prefix="/api/v1/export", tags=["export"])
export_service = ExportService()


@router.get(
    "/transactions",
    summary="导出交易记录 CSV",
)
async def export_transactions(
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
    asset_type: Optional[str] = Query(None, description="资产类型筛选（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """
    导出交易记录为 CSV 文件

    支持按日期范围和资产类型筛选
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    # 限制日期范围（最多1年）
    days_diff = (end_date - start_date).days
    if days_diff > 365:
        raise HTTPException(status_code=400, detail="日期范围不能超过1年")

    csv_content = await export_service.export_transactions_csv(
        db, start_date, end_date, asset_type
    )

    filename = f"transactions_{start_date}_{end_date}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/expenses",
    summary="导出支出记录 CSV",
)
async def export_expenses(
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
    category: Optional[str] = Query(None, description="分类筛选（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """
    导出支出记录为 CSV 文件

    支持按日期范围和分类筛选
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    # 限制日期范围（最多1年）
    days_diff = (end_date - start_date).days
    if days_diff > 365:
        raise HTTPException(status_code=400, detail="日期范围不能超过1年")

    csv_content = await export_service.export_expenses_csv(
        db, start_date, end_date, category
    )

    filename = f"expenses_{start_date}_{end_date}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/holdings",
    summary="导出持仓快照 CSV",
)
async def export_holdings(
    as_of_date: Optional[date] = Query(None, description="快照日期（默认今天）"),
    db: AsyncSession = Depends(get_db),
):
    """
    导出持仓快照为 CSV 文件

    包含所有活跃持仓的当前状态
    """
    csv_content = await export_service.export_holdings_snapshot_csv(db, as_of_date)

    snapshot_date = as_of_date or date.today()
    filename = f"holdings_snapshot_{snapshot_date}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/accounts",
    summary="导出账户列表 CSV",
)
async def export_accounts(
    db: AsyncSession = Depends(get_db),
):
    """
    导出账户列表为 CSV 文件

    包含所有账户的余额和持仓市值
    """
    csv_content = await export_service.export_accounts_csv(db)

    filename = f"accounts_{date.today()}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
