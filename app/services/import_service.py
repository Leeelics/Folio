"""CSV 导入服务 - Phase 4"""

import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Expense, ExpenseCategory
from app.services.investment_manager import InvestmentManager

logger = logging.getLogger(__name__)


class ImportError:
    """导入错误记录"""

    def __init__(self, row: int, field: str, message: str):
        self.row = row
        self.field = field
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row,
            "field": self.field,
            "message": self.message,
        }


class ImportResult:
    """导入结果"""

    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.errors: List[ImportError] = []

    def add_success(self):
        self.success_count += 1

    def add_error(self, row: int, field: str, message: str):
        self.error_count += 1
        self.errors.append(ImportError(row, field, message))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success_count": self.success_count,
            "error_count": self.error_count,
            "errors": [err.to_dict() for err in self.errors],
        }


class ImportService:
    """CSV 导入服务"""

    def __init__(self):
        self.investment_manager = InvestmentManager()

    async def import_transactions_csv(
        self,
        db: AsyncSession,
        csv_content: str,
        account_name: str,
    ) -> Dict[str, Any]:
        """导入交易记录 CSV"""
        result = ImportResult()

        try:
            # 解析 CSV
            df = pd.read_csv(io.StringIO(csv_content))

            # 验证必填列
            required_columns = ["date", "symbol", "type", "quantity", "price"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                result.add_error(0, "columns", f"缺少必填列: {', '.join(missing_columns)}")
                return result.to_dict()

            # 逐行处理
            for idx, row in df.iterrows():
                row_num = idx + 2  # CSV 行号（从1开始，加上表头）

                try:
                    # 验证必填字段
                    if pd.isna(row["date"]) or not row["date"]:
                        result.add_error(row_num, "date", "日期不能为空")
                        continue

                    if pd.isna(row["symbol"]) or not row["symbol"]:
                        result.add_error(row_num, "symbol", "股票代码不能为空")
                        continue

                    if pd.isna(row["type"]) or not row["type"]:
                        result.add_error(row_num, "type", "交易类型不能为空")
                        continue

                    if pd.isna(row["quantity"]):
                        result.add_error(row_num, "quantity", "数量不能为空")
                        continue

                    if pd.isna(row["price"]):
                        result.add_error(row_num, "price", "价格不能为空")
                        continue

                    # 解析日期
                    try:
                        transaction_date = pd.to_datetime(row["date"]).to_pydatetime()
                    except Exception:
                        result.add_error(row_num, "date", "日期格式无效")
                        continue

                    # 验证交易类型
                    transaction_type = str(row["type"]).lower()
                    valid_types = ["buy", "sell", "dividend", "split", "interest"]
                    if transaction_type not in valid_types:
                        result.add_error(
                            row_num,
                            "type",
                            f"交易类型无效，必须是: {', '.join(valid_types)}",
                        )
                        continue

                    # 解析数量和价格
                    try:
                        quantity = Decimal(str(row["quantity"]))
                        price = Decimal(str(row["price"]))
                    except (InvalidOperation, ValueError):
                        result.add_error(row_num, "quantity/price", "数量或价格格式无效")
                        continue

                    # 验证正数
                    if quantity <= 0:
                        result.add_error(row_num, "quantity", "数量必须大于0")
                        continue

                    if price < 0:
                        result.add_error(row_num, "price", "价格不能为负数")
                        continue

                    # 解析可选字段
                    name = str(row.get("name", "")) if not pd.isna(row.get("name")) else None
                    asset_type = (
                        str(row.get("asset_type", "stock"))
                        if not pd.isna(row.get("asset_type"))
                        else "stock"
                    )
                    fees = (
                        Decimal(str(row["fees"]))
                        if not pd.isna(row.get("fees"))
                        else Decimal("0")
                    )
                    currency = (
                        str(row.get("currency", "CNY"))
                        if not pd.isna(row.get("currency"))
                        else "CNY"
                    )
                    notes = str(row.get("notes", "")) if not pd.isna(row.get("notes")) else None

                    # 验证资产类型
                    valid_asset_types = [
                        "stock",
                        "fund",
                        "bond",
                        "bank_product",
                        "crypto",
                    ]
                    if asset_type not in valid_asset_types:
                        result.add_error(
                            row_num,
                            "asset_type",
                            f"资产类型无效，必须是: {', '.join(valid_asset_types)}",
                        )
                        continue

                    # 创建交易记录
                    await self.investment_manager.add_transaction(
                        db=db,
                        asset_type=asset_type,
                        symbol=str(row["symbol"]),
                        transaction_type=transaction_type,
                        quantity=quantity,
                        price=price,
                        transaction_date=transaction_date,
                        name=name,
                        fees=fees,
                        currency=currency,
                        account_name=account_name,
                        notes=notes,
                    )

                    result.add_success()

                except Exception as e:
                    logger.error(f"导入第 {row_num} 行失败: {e}")
                    result.add_error(row_num, "general", str(e))

        except Exception as e:
            logger.error(f"解析 CSV 失败: {e}")
            result.add_error(0, "csv", f"CSV 解析失败: {str(e)}")

        return result.to_dict()

    async def import_expenses_csv(
        self,
        db: AsyncSession,
        csv_content: str,
        account_id: int,
    ) -> Dict[str, Any]:
        """导入支出记录 CSV"""
        result = ImportResult()

        try:
            # 解析 CSV
            df = pd.read_csv(io.StringIO(csv_content))

            # 验证必填列
            required_columns = ["date", "amount", "category"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                result.add_error(0, "columns", f"缺少必填列: {', '.join(missing_columns)}")
                return result.to_dict()

            # 逐行处理
            for idx, row in df.iterrows():
                row_num = idx + 2

                try:
                    # 验证必填字段
                    if pd.isna(row["date"]) or not row["date"]:
                        result.add_error(row_num, "date", "日期不能为空")
                        continue

                    if pd.isna(row["amount"]):
                        result.add_error(row_num, "amount", "金额不能为空")
                        continue

                    if pd.isna(row["category"]) or not row["category"]:
                        result.add_error(row_num, "category", "分类不能为空")
                        continue

                    # 解析日期
                    try:
                        expense_date = pd.to_datetime(row["date"]).date()
                    except Exception:
                        result.add_error(row_num, "date", "日期格式无效")
                        continue

                    # 解析金额
                    try:
                        amount = Decimal(str(row["amount"]))
                    except (InvalidOperation, ValueError):
                        result.add_error(row_num, "amount", "金额格式无效")
                        continue

                    if amount <= 0:
                        result.add_error(row_num, "amount", "金额必须大于0")
                        continue

                    # 解析可选字段
                    category = str(row["category"])
                    subcategory = (
                        str(row.get("subcategory", ""))
                        if not pd.isna(row.get("subcategory"))
                        else None
                    )
                    merchant = (
                        str(row.get("merchant", ""))
                        if not pd.isna(row.get("merchant"))
                        else None
                    )
                    payment_method = (
                        str(row.get("payment_method", ""))
                        if not pd.isna(row.get("payment_method"))
                        else None
                    )
                    is_shared = bool(row.get("is_shared", False))
                    notes = str(row.get("notes", "")) if not pd.isna(row.get("notes")) else None

                    # 创建支出记录
                    expense = Expense(
                        account_id=account_id,
                        amount=amount,
                        expense_date=expense_date,
                        category=category,
                        subcategory=subcategory,
                        merchant=merchant,
                        payment_method=payment_method,
                        is_shared=is_shared,
                        notes=notes,
                    )

                    db.add(expense)
                    result.add_success()

                except Exception as e:
                    logger.error(f"导入第 {row_num} 行失败: {e}")
                    result.add_error(row_num, "general", str(e))

            # 提交所有成功的记录
            if result.success_count > 0:
                await db.commit()

        except Exception as e:
            logger.error(f"解析 CSV 失败: {e}")
            result.add_error(0, "csv", f"CSV 解析失败: {str(e)}")
            await db.rollback()

        return result.to_dict()

    async def import_brokerage_statement_csv(
        self,
        db: AsyncSession,
        csv_content: str,
        broker: str,
        account_name: str,
    ) -> Dict[str, Any]:
        """导入券商对账单 CSV（通用格式）"""
        result = ImportResult()

        try:
            # 解析 CSV
            df = pd.read_csv(io.StringIO(csv_content))

            # 验证必填列
            required_columns = ["date", "symbol", "type", "quantity", "price"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                result.add_error(0, "columns", f"缺少必填列: {', '.join(missing_columns)}")
                return result.to_dict()

            # 逐行处理（复用交易导入逻辑）
            for idx, row in df.iterrows():
                row_num = idx + 2

                try:
                    # 验证必填字段
                    if pd.isna(row["date"]) or not row["date"]:
                        result.add_error(row_num, "date", "日期不能为空")
                        continue

                    if pd.isna(row["symbol"]) or not row["symbol"]:
                        result.add_error(row_num, "symbol", "股票代码不能为空")
                        continue

                    if pd.isna(row["type"]) or not row["type"]:
                        result.add_error(row_num, "type", "交易类型不能为空")
                        continue

                    if pd.isna(row["quantity"]):
                        result.add_error(row_num, "quantity", "数量不能为空")
                        continue

                    if pd.isna(row["price"]):
                        result.add_error(row_num, "price", "价格不能为空")
                        continue

                    # 解析日期
                    try:
                        transaction_date = pd.to_datetime(row["date"]).to_pydatetime()
                    except Exception:
                        result.add_error(row_num, "date", "日期格式无效")
                        continue

                    # 验证交易类型
                    transaction_type = str(row["type"]).lower()
                    valid_types = ["buy", "sell", "dividend", "split", "interest"]
                    if transaction_type not in valid_types:
                        result.add_error(
                            row_num,
                            "type",
                            f"交易类型无效，必须是: {', '.join(valid_types)}",
                        )
                        continue

                    # 解析数量和价格
                    try:
                        quantity = Decimal(str(row["quantity"]))
                        price = Decimal(str(row["price"]))
                    except (InvalidOperation, ValueError):
                        result.add_error(row_num, "quantity/price", "数量或价格格式无效")
                        continue

                    if quantity <= 0:
                        result.add_error(row_num, "quantity", "数量必须大于0")
                        continue

                    if price < 0:
                        result.add_error(row_num, "price", "价格不能为负数")
                        continue

                    # 解析可选字段
                    name = str(row.get("name", "")) if not pd.isna(row.get("name")) else None
                    fees = (
                        Decimal(str(row["fees"]))
                        if not pd.isna(row.get("fees"))
                        else Decimal("0")
                    )
                    currency = (
                        str(row.get("currency", "CNY"))
                        if not pd.isna(row.get("currency"))
                        else "CNY"
                    )

                    # 创建交易记录
                    await self.investment_manager.add_transaction(
                        db=db,
                        asset_type="stock",  # 券商对账单默认为股票
                        symbol=str(row["symbol"]),
                        transaction_type=transaction_type,
                        quantity=quantity,
                        price=price,
                        transaction_date=transaction_date,
                        name=name,
                        fees=fees,
                        currency=currency,
                        account_name=account_name,
                        notes=f"从 {broker} 对账单导入",
                    )

                    result.add_success()

                except Exception as e:
                    logger.error(f"导入第 {row_num} 行失败: {e}")
                    result.add_error(row_num, "general", str(e))

        except Exception as e:
            logger.error(f"解析 CSV 失败: {e}")
            result.add_error(0, "csv", f"CSV 解析失败: {str(e)}")

        return result.to_dict()
