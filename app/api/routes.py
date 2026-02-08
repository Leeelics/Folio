import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.trading import Trade
from app.services import (
    AssetManager,
    RiskController,
    StrategyEngine,
    TradeExecutor,
    VectorStoreManager,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for request/response
class PortfolioStatusResponse(BaseModel):
    """资产组合状态响应"""
    total_assets: float
    allocation: Dict
    wedding_finance: Dict
    recommendations: List[str]


class AgentAnalyzeRequest(BaseModel):
    """AI 分析请求"""
    query: str = "分析当前市场情况并给出投资建议"
    news_limit: int = 5


class AgentAnalyzeResponse(BaseModel):
    """AI 分析响应"""
    analysis: str
    relevant_news: List[Dict]
    portfolio_status: Dict
    recommendations: List[str]


class TradeStatusResponse(BaseModel):
    """量化交易执行结果"""

    strategy_name: str
    dry_run: bool
    trade_count: int
    trades: List[Dict]


@router.get("/portfolio/status", response_model=PortfolioStatusResponse)
async def get_portfolio_status(db: AsyncSession = Depends(get_db)):
    """
    获取当前资产组合状态
    返回资产分布饼图数据、婚礼金安全水位等信息
    """
    try:
        risk_controller = RiskController()
        report = await risk_controller.get_risk_report(db)

        return PortfolioStatusResponse(
            total_assets=report["summary"]["total_assets"],
            allocation=report["allocation"],
            wedding_finance=report["wedding_finance"],
            recommendations=report["recommendations"]
        )
    except Exception as e:
        logger.error(f"Failed to get portfolio status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/sync-okx")
async def sync_okx_balance(db: AsyncSession = Depends(get_db)):
    """
    同步 OKX 交易所余额到数据库
    """
    try:
        asset_manager = AssetManager()
        updated_assets = await asset_manager.sync_okx_to_db(db)

        return {
            "status": "success",
            "updated_count": len(updated_assets),
            "assets": [
                {
                    "account_name": asset.account_name,
                    "balance": float(asset.balance),
                    "currency": asset.currency
                }
                for asset in updated_assets
            ]
        }
    except Exception as e:
        logger.error(f"Failed to sync OKX balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/analyze", response_model=AgentAnalyzeResponse)
async def agent_analyze(
    request: AgentAnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    触发 AI 分析逻辑
    检索向量数据库中的相关新闻，结合当前仓位给出止盈止损建议
    """
    try:
        # 初始化服务
        vector_store = VectorStoreManager()
        risk_controller = RiskController()

        # 1. 检索相关新闻
        relevant_news = await vector_store.search_similar_news(
            db,
            query=request.query,
            limit=request.news_limit
        )

        # 2. 获取当前资产状况
        risk_report = await risk_controller.get_risk_report(db)

        # 3. 构建 AI 分析上下文
        context = _build_analysis_context(relevant_news, risk_report)

        # 4. 调用 LangGraph Agent 进行分析
        analysis = await _run_langgraph_agent(context, request.query)

        return AgentAnalyzeResponse(
            analysis=analysis,
            relevant_news=relevant_news,
            portfolio_status=risk_report,
            recommendations=risk_report["recommendations"]
        )
    except Exception as e:
        logger.error(f"Failed to run agent analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/run-simple-dca", response_model=TradeStatusResponse)
async def run_simple_dca_strategy(
    dry_run: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    运行简单定投策略（simple_dca）。

    - 默认 dry_run=True，只记录模拟交易，不真正下单。
    - 配置从 strategy_configs 表中读取（名称 simple_dca）。
    """
    try:
        engine = StrategyEngine()
        executor = TradeExecutor()

        instructions = await engine.run_simple_dca(db, strategy_name="simple_dca")
        if not instructions:
            return TradeStatusResponse(
                strategy_name="simple_dca",
                dry_run=dry_run,
                trade_count=0,
                trades=[],
            )

        trades: List[Trade] = await executor.execute_instructions(
            db,
            instructions,
            dry_run=dry_run,
        )

        return TradeStatusResponse(
            strategy_name="simple_dca",
            dry_run=dry_run,
            trade_count=len(trades),
            trades=[
                {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "order_type": trade.order_type,
                    "amount": float(trade.amount),
                    "price": float(trade.price) if trade.price is not None else None,
                    "status": trade.status,
                    "exchange_order_id": trade.exchange_order_id,
                    "error_message": trade.error_message,
                    "created_at": trade.created_at,
                }
                for trade in trades
            ],
        )
    except Exception as e:
        logger.error(f"Failed to run simple DCA strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/news/add")
async def add_market_news(
    title: str,
    content: str,
    source: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    添加市场新闻并生成 Embedding
    """
    try:
        vector_store = VectorStoreManager()
        news = await vector_store.add_news(
            db,
            title=title,
            content=content,
            source=source
        )

        return {
            "status": "success",
            "news_id": news.id,
            "title": news.title
        }
    except Exception as e:
        logger.error(f"Failed to add news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/latest")
async def get_latest_news(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """
    获取最新市场新闻
    """
    try:
        vector_store = VectorStoreManager()
        news_list = await vector_store.get_latest_news(db, limit=limit)

        return {
            "count": len(news_list),
            "news": [
                {
                    "id": news.id,
                    "title": news.title,
                    "content": news.content[:200] + "..." if len(news.content) > 200 else news.content,
                    "source": news.source,
                    "published_at": news.published_at,
                    "created_at": news.created_at
                }
                for news in news_list
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get latest news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_analysis_context(relevant_news: List[Dict], risk_report: Dict) -> str:
    """构建 AI 分析的上下文"""
    context = "# 当前资产状况\n"
    context += f"总资产: ¥{risk_report['summary']['total_assets']:,.2f}\n"
    context += f"婚礼预算剩余: ¥{risk_report['wedding_finance']['remaining_budget']:,.2f}\n"
    context += f"安全边际: {risk_report['wedding_finance']['margin_percentage']:.2f}%\n"
    context += f"风险等级: {risk_report['wedding_finance']['risk_level']}\n\n"

    context += "# 资产配置\n"
    for account_type, info in risk_report['allocation'].items():
        context += f"- {account_type}: ¥{info['value']:,.2f} ({info['percentage']:.2f}%)\n"

    context += "\n# 相关市场新闻\n"
    for i, news in enumerate(relevant_news, 1):
        context += f"{i}. {news['title']}\n"
        context += f"   相似度: {news['similarity']:.2f}\n"
        context += f"   内容摘要: {news['content'][:150]}...\n\n"

    return context


async def _run_langgraph_agent(context: str, query: str) -> str:
    """
    运行 LangGraph Agent 进行分析
    这里是一个简化的实现，实际应该构建完整的 LangGraph 工作流
    """
    from openai import AsyncOpenAI

    from app.config import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # 构建 prompt
    system_prompt = """你是一位专业的金融分析师和风险管理顾问。
基于用户的资产状况和市场新闻，提供专业的投资建议，包括：
1. 当前市场分析
2. 资产配置建议
3. 止盈止损策略
4. 风险提示

特别注意：用户需要在 2026 年 6 月前保留 30 万婚礼预算，请在建议中考虑这一约束。"""

    user_prompt = f"{context}\n\n用户问题: {query}\n\n请提供详细的分析和建议。"

    try:
        response = await client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )

        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Failed to run LangGraph agent: {e}")
        return f"AI 分析暂时不可用: {str(e)}"
