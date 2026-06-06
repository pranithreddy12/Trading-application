import asyncio
import pandas as pd
import json
import re
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.sql import text
from atlas.core.agent_base import BaseAgent
from atlas.data.storage.timescale_client import TimescaleClient

class PaperStrategyRunner(BaseAgent):
    """
    PaperStrategyRunner — Runs promoted strategies against live features.
    
    Subscribes to feature updates, evaluates strategies, and emits trade signals.
    """
    name = "PaperStrategyRunner"
    agent_type = "strategy_runner"
    layer = "L3"

    def __init__(self, redis_client: Redis, db_client: TimescaleClient):
        super().__init__(name=self.name, agent_type=self.agent_type, layer=self.layer, redis_client=redis_client)
        self.db = db_client

    async def run(self):
        logger.info(f"{self.name} starting up.")
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("strategy_signals")

        try:
            while self.status == "running":
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        # Feature update signal from FeatureEngine
                        if "feature_count" in data and "symbol" in data:
                            symbol = data["symbol"]
                            await self._evaluate_all_active_strategies(symbol)
                    except Exception as e:
                        logger.error(f"Error in {self.name} loop: {e}")
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe()

    async def _evaluate_all_active_strategies(self, symbol: str):
        logger.debug(f"{self.name}: Evaluating strategies for {symbol}")
        async with self.db.engine.connect() as conn:
            res = await conn.execute(
                text("""
                    SELECT id, code, parameters, deployment_mode FROM (
                        SELECT DISTINCT ON (s.id) s.id, s.code, s.parameters, s.deployment_mode, b.composite_fitness_score
                        FROM strategies s
                        JOIN backtest_results b ON b.strategy_id = s.id
                        WHERE s.deployment_mode IN ('paper', 'live', 'shadow')
                        ORDER BY s.id, b.composite_fitness_score DESC NULLS LAST
                    ) top_strats
                    ORDER BY composite_fitness_score DESC NULLS LAST
                    LIMIT 50
                """)
            )
            strategies = res.fetchall()

            if not strategies:
                logger.debug(f"{self.name}: No active strategies found for evaluation")
                return

            df = await self._get_recent_data(conn, symbol)
            if df.empty:
                logger.debug(f"{self.name}: No data found for {symbol}")
                return
            if len(df) < 20:
                logger.debug(f"{self.name}: Insufficient data for {symbol} ({len(df)} bars)")
                return

            logger.debug(f"{self.name}: Evaluating {len(strategies)} strategies for {symbol} with {len(df)} bars")
            for strat in strategies:
                sid, code, params, status = strat
                try:
                    signal = await self._run_strategy_code(code, df)
                    if signal in (1, -1):
                        side = "buy" if signal == 1 else "sell"
                        logger.info(f"PAPER SIGNAL: {sid} | {symbol} | {side}")
                        
                        # Publish trade signal for ExecutionGateway
                        await self._redis.publish("strategy_signals", json.dumps({
                            "type": "signal",
                            "strategy_id": str(sid),
                            "symbol": symbol,
                            "side": side,
                            "qty": 10.0,
                            "mode": status,
                            "feature_snapshot_id": None
                        }))
                except Exception as e:
                    logger.debug(f"Eval failed for {sid}: {e}")

    async def _get_recent_data(self, conn, symbol: str):
        """Fetch last 100 bars and merge with wide features."""
        # 1. Get bars
        res = await conn.execute(
            text("""
                SELECT time, open, high, low, close, volume
                FROM market_data_l1
                WHERE symbol = :sym
                ORDER BY time DESC
                LIMIT 100
            """),
            {"sym": symbol}
        )
        rows = res.fetchall()
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
        df = df.sort_values("time")
        
        # 2. Get wide features
        feat_res = await conn.execute(
            text("""
                SELECT * FROM features_wide
                WHERE symbol = :sym
                ORDER BY time DESC
                LIMIT 100
            """),
            {"sym": symbol}
        )
        feat_rows = feat_res.fetchall()
        if feat_rows:
            cols = feat_res.keys()
            feat_df = pd.DataFrame(feat_rows, columns=cols)
            if "symbol" in feat_df.columns:
                feat_df = feat_df.drop(columns=["symbol"])
            df = df.merge(feat_df, on="time", how="left")
            df = df.sort_values("time").ffill().bfill()
        
        return df

    async def _run_strategy_code(self, code: str, df: pd.DataFrame) -> int:
        """Safely execute strategy code and return latest signal."""
        try:
            # Prepare namespace
            namespace = {"pd": pd, "np": __import__("numpy")}
            exec(code, namespace)
            
            # Find Strategy class
            strat_class = None
            for item in namespace.values():
                if isinstance(item, type) and hasattr(item, "generate_signals"):
                    strat_class = item
                    break
            
            if not strat_class:
                return 0
                
            instance = strat_class()
            # FUTURE LEAKAGE GUARD: deep copy without time column
            _bt_df = df.drop(columns=["time"], errors="ignore").copy()
            signals = instance.generate_signals(_bt_df)
            
            if isinstance(signals, pd.Series) and not signals.empty:
                last_val = signals.iloc[-1]
                if last_val >= 1: return 1
                if last_val <= -1: return -1
                
            return 0
        except Exception as e:
            raise Exception(f"Code exec error: {e}")

if __name__ == "__main__":
    # For standalone testing
    import sys
    from atlas.config.settings import get_settings
    
    async def main():
        settings = get_settings()
        db = TimescaleClient(settings.database_url)
        redis = Redis.from_url(settings.redis_url)
        runner = PaperStrategyRunner(redis, db)
        await runner.start()
        await asyncio.Event().wait()
        
    asyncio.run(main())
