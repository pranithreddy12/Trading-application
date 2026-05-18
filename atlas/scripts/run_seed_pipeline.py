"""
Run full pipeline: backtest -> validate -> report
Works regardless of BacktestRunner __init__ signature.
Run: python atlas/scripts/run_seed_pipeline.py
"""
import asyncio
import inspect
from loguru import logger
from sqlalchemy import text
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l3_backtest.backtest_runner import BacktestRunner
from atlas.agents.l3_backtest.validator_agent import ValidatorAgent
from atlas.config.settings import settings


def make_agent(cls, db):
    sig = inspect.signature(cls.__init__)
    params = [p for p in sig.parameters.keys() if p != "self"]
    if not params:
        agent = cls()
    else:
        first = params[0]
        try:
            agent = cls(**{first: db})
        except TypeError:
            try:
                agent = cls(db)
            except TypeError:
                agent = cls()
    for attr in ("db", "db_client", "timescale_client", "_db"):
        if hasattr(agent, attr) and getattr(agent, attr) is None:
            setattr(agent, attr, db)
    return agent


async def run_backtest(db, runner):
    pending = await db.get_strategies_by_status("pending_backtest")
    logger.info(f"Backtesting {len(pending)} strategies")
    for s in pending:
        name = s.get("name", "unknown")
        try:
            for method in ("_run_for_strategy", "run_for_strategy", "_backtest", "backtest"):
                if hasattr(runner, method):
                    await getattr(runner, method)(s)
                    break
            logger.info(f"  OK: {name}")
        except Exception as e:
            logger.error(f"  FAIL {name}: {type(e).__name__}: {e}")


async def run_validate(db, validator):
    to_val = await db.get_strategies_by_status("pending_validation")
    logger.info(f"Validating {len(to_val)} strategies")
    for s in to_val:
        sid = s["id"]
        name = s.get("name", "unknown")
        try:
            for method in ("_validate_one", "validate_one", "_validate_strategy", "validate"):
                if hasattr(validator, method):
                    m = getattr(validator, method)
                    sig = inspect.signature(m)
                    nparams = len([p for p in sig.parameters if p != "self"])
                    if nparams >= 2:
                        await m(sid, name)
                    else:
                        await m(sid)
                    break
            logger.info(f"  OK: {name}")
        except Exception as e:
            logger.error(f"  FAIL {name}: {type(e).__name__}: {e}")


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()

    runner = make_agent(BacktestRunner, db)
    validator = make_agent(ValidatorAgent, db)
    logger.info(f"Runner: {type(runner).__name__}  Validator: {type(validator).__name__}")

    await run_backtest(db, runner)
    await run_validate(db, validator)

    async with db.engine.connect() as conn:
        r = await conn.execute(text(
            "SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY count DESC"
        ))
        logger.info("=== STRATEGY STATUS ===")
        for row in r.fetchall():
            logger.info(f"  {row[0]}: {row[1]}")

        r2 = await conn.execute(text("SELECT COUNT(*) FROM paper_trades"))
        logger.info(f"=== PAPER TRADES: {r2.scalar()} ===")

        r3 = await conn.execute(text("""
            SELECT name, status FROM strategies
            WHERE status NOT IN ('pending_backtest','pending_code','code_failed','pending_validation')
            LIMIT 10
        """))
        for row in r3.fetchall():
            logger.info(f"  {row.name} -> {row.status}")


if __name__ == "__main__":
    asyncio.run(main())
