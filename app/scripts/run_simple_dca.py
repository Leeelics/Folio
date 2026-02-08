import asyncio
import logging

from app.database import get_db_session
from app.services.strategy_engine import StrategyEngine
from app.services.trade_executor import TradeExecutor

logger = logging.getLogger(__name__)


async def _run_once(strategy_name: str = "simple_dca", dry_run: bool = False) -> None:
    async_session_factory = get_db_session()
    async with async_session_factory() as session:  # type: AsyncSession
        engine = StrategyEngine()
        executor = TradeExecutor()

        instructions = await engine.run_simple_dca(session, strategy_name=strategy_name)
        if not instructions:
            logger.info("No instructions generated for strategy %s", strategy_name)
            return

        trades = await executor.execute_instructions(
            session,
            instructions,
            dry_run=dry_run,
        )
        logger.info("Executed %d trades for strategy %s", len(trades), strategy_name)


def main(strategy_name: str = "simple_dca", dry_run: bool = False) -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_once(strategy_name=strategy_name, dry_run=dry_run))


if __name__ == "__main__":
    # For direct CLI execution:
    # uv run python -m app.scripts.run_simple_dca
    main()

