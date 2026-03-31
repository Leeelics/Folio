"""导入 API 路由 - Phase 4"""

from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.import_service import ImportService

router = APIRouter(prefix="/api/v1/import", tags=["import"])
import_service = ImportService()


# ============ Pydantic 响应模型 ============


class ImportErrorDetail(BaseModel):
    row: int
    field: str
    message: str


class ImportResult(BaseModel):
    success_count: int
    error_count: int
    errors: List[ImportErrorDetail]


# ============ API 端点 ============


@router.post(
    "/transactions",
    response_model=ImportResult,
    summary="导入交易记录 CSV",
)
async def import_transactions(
    file: UploadFile = File(..., description="CSV 文件"),
    account_name: str = Form(..., description="账户名称"),
    db: AsyncSession = Depends(get_db),
):
    """
    导入交易记录 CSV 文件

    必填列：date, symbol, type, quantity, price
    可选列：name, asset_type, fees, currency, notes

    CSV 模板：
    ```
    date,symbol,name,asset_type,type,quantity,price,fees,currency,notes
    2026-01-15,600000,浦发银行,stock,buy,100,10.50,5.00,CNY,
    ```
    """
    # 验证文件类型
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    # 验证文件大小（5MB）
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    # 解码内容
    try:
        csv_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_content = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件编码无效，请使用 UTF-8 或 GBK")

    # 导入数据
    result = await import_service.import_transactions_csv(db, csv_content, account_name)
    return result


@router.post(
    "/expenses",
    response_model=ImportResult,
    summary="导入支出记录 CSV",
)
async def import_expenses(
    file: UploadFile = File(..., description="CSV 文件"),
    account_id: int = Form(..., description="账户 ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    导入支出记录 CSV 文件

    必填列：date, amount, category
    可选列：subcategory, merchant, payment_method, is_shared, notes

    CSV 模板：
    ```
    date,amount,category,subcategory,merchant,payment_method,is_shared,notes
    2026-01-15,50.00,餐饮,午餐,麦当劳,微信支付,false,
    ```
    """
    # 验证文件类型
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    # 验证文件大小（5MB）
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    # 解码内容
    try:
        csv_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_content = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件编码无效，请使用 UTF-8 或 GBK")

    # 导入数据
    result = await import_service.import_expenses_csv(db, csv_content, account_id)
    return result


@router.post(
    "/brokerage-statement",
    response_model=ImportResult,
    summary="导入券商对账单 CSV",
)
async def import_brokerage_statement(
    file: UploadFile = File(..., description="CSV 文件"),
    broker: str = Form(..., description="券商名称（如：富途、老虎证券）"),
    account_name: str = Form(..., description="账户名称"),
    db: AsyncSession = Depends(get_db),
):
    """
    导入券商对账单 CSV 文件（通用格式）

    必填列：date, symbol, type, quantity, price
    可选列：name, fees, currency

    CSV 模板：
    ```
    date,symbol,name,type,quantity,price,fees,currency
    2026-01-15,600000,浦发银行,buy,100,10.50,5.00,CNY
    ```
    """
    # 验证文件类型
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    # 验证文件大小（5MB）
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    # 解码内容
    try:
        csv_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_content = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件编码无效，请使用 UTF-8 或 GBK")

    # 导入数据
    result = await import_service.import_brokerage_statement_csv(
        db, csv_content, broker, account_name
    )
    return result
