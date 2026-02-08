import logging
from typing import Dict, List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.schemas import MarketNews

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorStoreManager:
    """向量数据库管理 - 封装 pgvector 的增删改查逻辑"""

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_embedding(self, text: str) -> List[float]:
        """使用 OpenAI 生成文本 Embedding"""
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def add_news(
        self,
        db: AsyncSession,
        title: str,
        content: str,
        source: Optional[str] = None,
        published_at: Optional[str] = None
    ) -> MarketNews:
        """添加新闻并生成 Embedding"""
        # 生成 embedding（使用标题+内容）
        combined_text = f"{title}\n{content}"
        embedding = await self.generate_embedding(combined_text)

        # 创建新闻记录
        news = MarketNews(
            title=title,
            content=content,
            source=source,
            published_at=published_at,
            embedding=embedding
        )

        db.add(news)
        await db.commit()
        await db.refresh(news)

        return news

    async def search_similar_news(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 5
    ) -> List[Dict]:
        """向量相似度搜索"""
        # 生成查询 embedding
        query_embedding = await self.generate_embedding(query)

        # 使用 pgvector 的余弦相似度搜索
        # 注意：pgvector 使用 <=> 操作符表示余弦距离（越小越相似）
        stmt = text("""
            SELECT
                id,
                title,
                content,
                source,
                published_at,
                1 - (embedding <=> :query_embedding) as similarity
            FROM market_news
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_embedding
            LIMIT :limit
        """)

        result = await db.execute(
            stmt,
            {
                "query_embedding": str(query_embedding),
                "limit": limit
            }
        )

        rows = result.fetchall()
        return [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "source": row[3],
                "published_at": row[4],
                "similarity": float(row[5])
            }
            for row in rows
        ]

    async def get_latest_news(
        self,
        db: AsyncSession,
        limit: int = 10
    ) -> List[MarketNews]:
        """获取最新新闻"""
        stmt = select(MarketNews).order_by(
            MarketNews.created_at.desc()
        ).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def delete_news(self, db: AsyncSession, news_id: int) -> bool:
        """删除新闻"""
        stmt = select(MarketNews).where(MarketNews.id == news_id)
        result = await db.execute(stmt)
        news = result.scalar_one_or_none()

        if news:
            await db.delete(news)
            await db.commit()
            return True
        return False

    async def update_news_embedding(
        self,
        db: AsyncSession,
        news_id: int
    ) -> Optional[MarketNews]:
        """重新生成新闻的 Embedding"""
        stmt = select(MarketNews).where(MarketNews.id == news_id)
        result = await db.execute(stmt)
        news = result.scalar_one_or_none()

        if news:
            combined_text = f"{news.title}\n{news.content}"
            embedding = await self.generate_embedding(combined_text)
            news.embedding = embedding
            await db.commit()
            await db.refresh(news)
            return news

        return None
