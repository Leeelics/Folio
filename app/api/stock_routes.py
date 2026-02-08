"""股票 API 路由 - 行情、持仓、自选股管理"""

import logging
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.stock_client import Market, StockClient, StockDataError
from app.services.stock_position_manager import StockPositionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stocks", tags=["股票市场"])


# ============ Pydantic 请求/响应模型 ============

class StockQuoteResponse(BaseModel):
    """实时行情响应"""
    symbol: str
    name: str
    market: str
    current_price: float
    change: float
    change_percent: float
    open_price: float
    high: float
    low: float
    volume: int
    amount: float
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    timestamp: str


class KlineDataItem(BaseModel):
    """K线数据项"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class KlineResponse(BaseModel):
    """K线数据响应"""
    symbol: str
    market: str
    period: str
    data: List[KlineDataItem]


class MarketOverviewResponse(BaseModel):
    """市场概览响应"""
    market: str
    total_stocks: int
    active_stocks: Optional[int] = None
    up_count: int
    down_count: int
    flat_count: int
    up_ratio: float
    limit_up_count: Optional[int] = None
    limit_down_count: Optional[int] = None
    high_volume_count: Optional[int] = None
    timestamp: str


class VolumeSurgeItem(BaseModel):
    """放量股票项"""
    symbol: str
    name: str
    current_price: float
    change_percent: float
    volume: int
    volume_ratio: float
    amount: float


class PositionCreateRequest(BaseModel):
    """创建持仓请求"""
    symbol: str
    market: str  # A股/港股/美股
    quantity: int
    cost_price: float
    account_name: str = "默认账户"
    notes: Optional[str] = None


class PositionUpdateRequest(BaseModel):
    """更新持仓请求"""
    quantity: Optional[int] = None
    cost_price: Optional[float] = None
    notes: Optional[str] = None


class PositionResponse(BaseModel):
    """持仓响应"""
    id: int
    symbol: str
    market: str
    name: Optional[str]
    quantity: int
    cost_price: float
    account_name: str
    currency: str
    notes: Optional[str] = None
    created_at: str


class PositionPnLResponse(BaseModel):
    """持仓盈亏响应"""
    position_id: int
    symbol: str
    name: Optional[str]
    market: str
    quantity: int
    cost_price: float
    current_price: float
    cost_value: float
    current_value: float
    pnl: float
    pnl_percent: float
    currency: str
    cost_value_cny: float
    current_value_cny: float
    pnl_cny: float
    change_today: float
    account_name: str


class WatchlistAddRequest(BaseModel):
    """添加自选股请求"""
    symbol: str
    market: str
    notes: Optional[str] = None
    alert_price_high: Optional[float] = None
    alert_price_low: Optional[float] = None


class SearchResultItem(BaseModel):
    """搜索结果项"""
    symbol: str
    name: str
    market: str
    current_price: float
    change_percent: float


# ============ 行情端点 ============

@router.get("/quote/{market}/{symbol}", response_model=StockQuoteResponse)
async def get_stock_quote(
    market: str,
    symbol: str,
    mode: str = Query("auto", description="数据模式: auto/realtime/daily"),
):
    """获取单只股票实时行情

    - market: A股/港股/美股
    - symbol: 股票代码（如 600000, 00700, AAPL）
    """
    try:
        market_enum = Market(market)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的市场: {market}，支持: A股/港股/美股")

    if mode not in {"auto", "realtime", "daily"}:
        raise HTTPException(status_code=400, detail="mode 必须是 auto/realtime/daily")

    client = StockClient()
    try:
        if mode == "daily":
            quote = await client.fetch_latest_quote_from_history(symbol, market_enum)
        elif mode == "realtime":
            quote = await client.fetch_realtime_quote(symbol, market_enum, strict=True)
        else:
            quote = await client.fetch_realtime_quote(symbol, market_enum, strict=False)
    except StockDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not quote:
        raise HTTPException(status_code=404, detail=f"股票 {symbol} 在 {market} 未找到")

    return StockQuoteResponse(
        symbol=quote.symbol,
        name=quote.name,
        market=quote.market.value,
        current_price=float(quote.current_price),
        change=float(quote.change),
        change_percent=float(quote.change_percent),
        open_price=float(quote.open_price),
        high=float(quote.high),
        low=float(quote.low),
        volume=quote.volume,
        amount=float(quote.amount),
        pe_ratio=float(quote.pe_ratio) if quote.pe_ratio else None,
        pb_ratio=float(quote.pb_ratio) if quote.pb_ratio else None,
        market_cap=float(quote.market_cap) if quote.market_cap else None,
        timestamp=quote.timestamp.isoformat(),
    )


@router.get("/kline/{market}/{symbol}", response_model=KlineResponse)
async def get_stock_kline(
    market: str,
    symbol: str,
    period: str = Query("daily", description="周期: daily/weekly/monthly"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    adjust: str = Query("qfq", description="复权: qfq=前复权, hfq=后复权, 空=不复权"),
):
    """获取股票K线数据"""
    try:
        market_enum = Market(market)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的市场: {market}")

    if period not in ["daily", "weekly", "monthly"]:
        raise HTTPException(status_code=400, detail="period 必须是 daily/weekly/monthly")

    client = StockClient()
    try:
        klines = await client.fetch_kline(
            symbol=symbol,
            market=market_enum,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except StockDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not klines:
        raise HTTPException(status_code=404, detail=f"无法获取 {symbol} 的K线数据")

    return KlineResponse(
        symbol=symbol,
        market=market,
        period=period,
        data=[
            KlineDataItem(
                date=k.date.strftime("%Y-%m-%d"),
                open=float(k.open),
                high=float(k.high),
                low=float(k.low),
                close=float(k.close),
                volume=k.volume,
                amount=float(k.amount),
            )
            for k in klines
        ],
    )


@router.get("/market-overview/{market}", response_model=MarketOverviewResponse)
async def get_market_overview(market: str):
    """获取市场概览（涨跌家数统计）"""
    try:
        market_enum = Market(market)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的市场: {market}")

    client = StockClient()
    try:
        overview = await client.fetch_market_overview(market_enum)
    except StockDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not overview:
        raise HTTPException(status_code=500, detail="获取市场概览失败")

    return MarketOverviewResponse(**overview)


@router.get("/volume-surge/{market}", response_model=List[VolumeSurgeItem])
async def get_volume_surge_stocks(
    market: str,
    threshold: float = Query(2.0, description="放量阈值（相对平均成交量的倍数）"),
    limit: int = Query(20, description="返回数量限制"),
):
    """获取放量股票列表"""
    try:
        market_enum = Market(market)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的市场: {market}")

    client = StockClient()
    try:
        stocks = await client.fetch_volume_surge_stocks(market_enum, threshold, limit)
    except StockDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return [VolumeSurgeItem(**s) for s in stocks]


@router.get("/financial/{market}/{symbol}")
async def get_financial_data(market: str, symbol: str):
    """获取股票财务数据"""
    try:
        market_enum = Market(market)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的市场: {market}")

    client = StockClient()
    try:
        data = await client.fetch_financial_data(symbol, market_enum)
    except StockDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not data:
        raise HTTPException(status_code=404, detail=f"无法获取 {symbol} 的财务数据")

    return data


@router.get("/search", response_model=List[SearchResultItem])
async def search_stocks(
    keyword: str = Query(..., description="搜索关键词（代码或名称）"),
    market: Optional[str] = Query(None, description="限定市场: A股/港股/美股"),
):
    """搜索股票"""
    market_enum = None
    if market:
        try:
            market_enum = Market(market)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的市场: {market}")

    client = StockClient()
    try:
        results = await client.search_stock(keyword, market_enum)
    except StockDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return [SearchResultItem(**r) for r in results]


# ============ 持仓端点 ============

@router.get("/positions")
async def get_all_positions(db: AsyncSession = Depends(get_db)):
    """获取所有股票持仓"""
    manager = StockPositionManager()
    positions = await manager.get_all_positions(db)

    return {
        "count": len(positions),
        "positions": [
            {
                "id": p.id,
                "symbol": p.symbol,
                "market": p.market,
                "name": p.name,
                "quantity": p.quantity,
                "cost_price": float(p.cost_price),
                "account_name": p.account_name,
                "currency": p.currency,
                "notes": p.notes,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in positions
        ],
    }


@router.post("/positions")
async def create_position(
    request: PositionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """添加股票持仓"""
    # 验证市场
    if request.market not in ["A股", "港股", "美股"]:
        raise HTTPException(status_code=400, detail="market 必须是 A股/港股/美股")

    manager = StockPositionManager()
    position = await manager.add_position(
        db=db,
        symbol=request.symbol,
        market=request.market,
        quantity=request.quantity,
        cost_price=Decimal(str(request.cost_price)),
        account_name=request.account_name,
        notes=request.notes,
    )

    return {
        "status": "success",
        "position": {
            "id": position.id,
            "symbol": position.symbol,
            "market": position.market,
            "name": position.name,
            "quantity": position.quantity,
            "cost_price": float(position.cost_price),
        },
    }


@router.put("/positions/{position_id}")
async def update_position(
    position_id: int,
    request: PositionUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新股票持仓"""
    manager = StockPositionManager()
    position = await manager.update_position(
        db=db,
        position_id=position_id,
        quantity=request.quantity,
        cost_price=Decimal(str(request.cost_price)) if request.cost_price else None,
        notes=request.notes,
    )

    if not position:
        raise HTTPException(status_code=404, detail=f"持仓 {position_id} 不存在")

    return {
        "status": "success",
        "position": {
            "id": position.id,
            "symbol": position.symbol,
            "quantity": position.quantity,
            "cost_price": float(position.cost_price),
        },
    }


@router.delete("/positions/{position_id}")
async def delete_position(
    position_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除股票持仓（清仓）"""
    manager = StockPositionManager()
    deleted = await manager.delete_position(db, position_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"持仓 {position_id} 不存在")

    return {"status": "success", "message": f"持仓 {position_id} 已删除"}


@router.get("/positions/{position_id}/pnl")
async def get_position_pnl(
    position_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个持仓的盈亏详情"""
    manager = StockPositionManager()
    pnl = await manager.calculate_position_pnl(db, position_id)

    if "error" in pnl:
        raise HTTPException(status_code=404, detail=pnl["error"])

    return pnl


@router.get("/positions/summary")
async def get_positions_summary(db: AsyncSession = Depends(get_db)):
    """获取持仓汇总（总市值、总盈亏）"""
    manager = StockPositionManager()
    summary = await manager.calculate_total_stock_value(db)
    return summary


# ============ 自选股端点 ============

@router.get("/watchlist")
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    """获取自选股列表（带实时行情）"""
    manager = StockPositionManager()
    watchlist = await manager.get_watchlist(db)
    return {"count": len(watchlist), "watchlist": watchlist}


@router.post("/watchlist")
async def add_to_watchlist(
    request: WatchlistAddRequest,
    db: AsyncSession = Depends(get_db),
):
    """添加自选股"""
    if request.market not in ["A股", "港股", "美股"]:
        raise HTTPException(status_code=400, detail="market 必须是 A股/港股/美股")

    manager = StockPositionManager()
    item = await manager.add_to_watchlist(
        db=db,
        symbol=request.symbol,
        market=request.market,
        notes=request.notes,
        alert_price_high=Decimal(str(request.alert_price_high)) if request.alert_price_high else None,
        alert_price_low=Decimal(str(request.alert_price_low)) if request.alert_price_low else None,
    )

    return {
        "status": "success",
        "watchlist_item": {
            "id": item.id,
            "symbol": item.symbol,
            "market": item.market,
            "name": item.name,
        },
    }


@router.delete("/watchlist/{watchlist_id}")
async def remove_from_watchlist(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
):
    """从自选股移除"""
    manager = StockPositionManager()
    deleted = await manager.remove_from_watchlist(db, watchlist_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"自选股 {watchlist_id} 不存在")

    return {"status": "success", "message": f"自选股 {watchlist_id} 已移除"}
