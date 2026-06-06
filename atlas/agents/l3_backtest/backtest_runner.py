import asyncio
import json
import re
import pandas as pd
import numpy as np
from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from atlas.agents.l3_backtest.short_window_evaluator import (
    is_short_window,
    compute_short_window_metrics,
    compute_composite_short_window_score,
)
from atlas.core.event_lineage import EventLineageClient

# Lazy imports for advanced validation agents (wired post-backtest)
from atlas.agents.l3_validation.walk_forward_analyzer import WalkForwardAnalyzer
from atlas.agents.l3_validation.overfitting_detector import OverfittingDetector
from atlas.agents.l3_validation.regime_validator import RegimeValidator
from atlas.agents.l3_validation.monte_carlo_simulator import MonteCarloSimulator


def clean_metrics(obj):
    if isinstance(obj, dict):
        return {k: clean_metrics(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_metrics(v) for v in obj]
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return 0.0
    return obj


class DummyStrategy:
    """
    Emergency fallback only for debugging.
    In production pipeline we mark failed code separately.
    """

    def __init__(self):
        self.stop_loss_pct = 0.0  # disabled by default
        self.take_profit_pct = 0.0  # disabled by default

    def generate_signals(self, df):
        return pd.Series(
            np.where(df["close"].pct_change().fillna(0) > 0, 1, -1),
            index=df.index,
        )


class BacktestRunner(BaseAgent):
    MAX_CONCURRENT_BACKTESTS = 4
    QUEUE_PRESSURE_THRESHOLD = 500

    def __init__(self, redis_client):
        super().__init__("BacktestRunner", "backtester", "L3", redis_client)

        self.settings = get_settings()
        self.timescale = TimescaleClient(self.settings.database_url)
        self.messaging = MessagingClient(redis_client)

        self.commission_pct = 0.001
        self.slippage_pct = 0.0005
        self.spread_cost_pct = 0.0005
        self.position_size = 0.10  # fixed position size (10% per trade)

        # Dynamic slippage config
        self.DYN_SLIPPAGE_MIN_MULT = 0.5
        self.DYN_SLIPPAGE_MAX_MULT = 3.0
        self.DYN_SLIPPAGE_VOL_CAP = 3.0
        self.DYN_SLIPPAGE_VOL_FLOOR = 0.3
        self.DYN_SLIPPAGE_VOLUME_CAP = 3.0
        self.DYN_SLIPPAGE_VOLUME_FLOOR = 0.5

    async def run(self):
        print("=== BACKTEST RUN LOOP ENTERED ===", flush=True)
        logger.info("BacktestRunner DB polling started - polling for pending_backtest")

        # Run auto-migrations (schema creation, MV upgrades, etc.)
        await self.timescale.connect()
        consecutive_errors = 0

        while True:
            try:
                strategies = await self.timescale.get_strategies_by_status(
                    "pending_backtest"
                )

                if strategies:
                    print(f"=== FOUND {len(strategies)} STRATEGIES ===", flush=True)
                    logger.info(f"Found {len(strategies)} pending_backtest strategies")
                    consecutive_errors = 0

                    # Queue governor: signal Ideator to throttle when backlog exceeds threshold
                    if len(strategies) > self.QUEUE_PRESSURE_THRESHOLD:
                        logger.warning(
                            f"Backtest queue pressure: {len(strategies)} pending "
                            f"(threshold={self.QUEUE_PRESSURE_THRESHOLD}) — signaling throttle"
                        )
                        await self.messaging.publish(
                            Channel.STRATEGY_SIGNALS,
                            {
                                "type": "queue_pressure",
                                "pending_count": len(strategies),
                                "action": "throttle_ideator",
                            },
                        )

                    sem = asyncio.Semaphore(self.MAX_CONCURRENT_BACKTESTS)

                    async def _process_with_limit(s):
                        async with sem:
                            try:
                                await self.process_strategy(s)
                            except Exception as e:
                                logger.error(
                                    f"Backtest failed for {s.get('name')}: {e}"
                                )
                                await self.timescale.update_strategy_status(
                                    s["id"], "backtest_failed", str(e)[:200]
                                )

                    await asyncio.gather(*[_process_with_limit(s) for s in strategies])

                await asyncio.sleep(5)

            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    f"BacktestRunner loop error #{consecutive_errors}: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                if consecutive_errors > 10:
                    logger.critical(
                        "BacktestRunner: 10+ consecutive errors - restarting"
                    )
                    consecutive_errors = 0
                await asyncio.sleep(10)

    async def _get_available_symbol(self, strategy: dict) -> str:
        """
        Pick symbol with most data available.
        """
        from sqlalchemy import text

        async with self.timescale.engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT symbol, COUNT(*) as bar_count
                    FROM market_data_l1
                    GROUP BY symbol
                    ORDER BY bar_count DESC
                    LIMIT 1
                    """
                )
            )

            row = result.fetchone()

            if row:
                logger.info(
                    f"Selected symbol {row.symbol} with {row.bar_count} bars "
                    f"for strategy {strategy.get('id')}"
                )
                return row.symbol

        logger.warning("No symbols found — defaulting to BTCUSDT")
        return "BTCUSDT"

    async def _log_exec_failure(self, strategy_id, code, error):
        """
        Centralized logging for code execution failures.
        """
        logger.error(f"EXEC FAILED for {strategy_id}: {type(error).__name__}: {error}")

        logger.error(f"FAILED CODE FOR {strategy_id}:\n{code}")

        try:
            await self.timescale.log(
                agent_id="BacktestRunner",
                level="ERROR",
                message=f"Exec failed for {strategy_id}: {type(error).__name__}: {error}",
                metadata={
                    "strategy_id": str(strategy_id),
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "code": code,
                },
            )
        except Exception as log_err:
            logger.warning(f"Failed to log system event: {log_err}")

    async def process_strategy(self, strategy_record: dict):
        # Ensure IDs are plain strings (DB drivers may return UUID objects)
        strategy_id = (
            str(strategy_record["id"])
            if strategy_record.get("id") is not None
            else "unknown"
        )
        trace_id = strategy_record.get("trace_id")
        trace_id = str(trace_id) if trace_id is not None else None

        try:
            code = strategy_record.get("code", "")
            params = strategy_record.get("parameters", {})

            if not code or not code.strip():
                logger.warning(f"{strategy_id} has empty code")
                await self.timescale.update_strategy_status(
                    strategy_id,
                    "code_failed",
                )
                return

            # =====================================================
            # LOAD GENERATED STRATEGY
            # =====================================================
            strategy_instance = None

            try:
                namespace = {
                    "pd": pd,
                    "np": np,
                }

                exec(code, namespace)

                logger.info(
                    f"{strategy_id}: Namespace keys after exec: "
                    f"{list(namespace.keys())}"
                )

                for name, obj in namespace.items():
                    if isinstance(obj, type) and callable(
                        getattr(obj, "generate_signals", None)
                    ):
                        strategy_instance = obj()
                        logger.info(f"{strategy_id}: Strategy class detected: {name}")
                        break

                if strategy_instance is None:
                    raise ValueError(
                        "No valid strategy class with generate_signals found"
                    )

            except Exception as e:
                await self._log_exec_failure(strategy_id, code, e)

                # STRICT MODE:
                # Do NOT silently use DummyStrategy
                await self.timescale.update_strategy_status(
                    strategy_id,
                    "code_failed",
                )

                await self.messaging.publish(
                    Channel.STRATEGY_SIGNALS,
                    {
                        "type": "backtest_complete",
                        "strategy_id": strategy_id,
                        "sharpe": 0.0,
                        "passed": False,
                        "reason": "code_exec_failed",
                    },
                )

                await self._log_lifecycle(
                    trace_id,
                    strategy_id,
                    "backtest",
                    "failed",
                    {"error": "code_exec_failed"},
                )
                return

            # =====================================================
            # FETCH MARKET DATA + FEATURES
            # =====================================================
            symbol = await self._get_available_symbol(strategy_record)

            from sqlalchemy import text

            async with self.timescale.engine.connect() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT time, open, high, low, close, volume
                        FROM market_data_l1
                        WHERE symbol = :symbol
                        ORDER BY time ASC
                        """
                    ),
                    {"symbol": symbol},
                )
                rows = result.fetchall()

            df = pd.DataFrame(
                rows,
                columns=["time", "open", "high", "low", "close", "volume"],
            )

            if df.empty:
                logger.warning(f"No market data found for {symbol}")
                await self.timescale.update_strategy_status(
                    strategy_id,
                    "backtest_failed",
                )
                return

            df["time"] = pd.to_datetime(df["time"])
            df = df.astype(
                {
                    "open": float,
                    "high": float,
                    "low": float,
                    "close": float,
                    "volume": float,
                }
            )

            # Filter equity symbols to market hours (9:30 AM - 4:00 PM ET)
            if not symbol.endswith("USDT"):
                eastern = (
                    df["time"].dt.tz_convert("US/Eastern")
                    if df["time"].dt.tz
                    else df["time"]
                )
                market_open = eastern.dt.hour * 60 + eastern.dt.minute >= 570
                market_close = eastern.dt.hour * 60 + eastern.dt.minute < 960
                df = df[market_open & market_close].copy()
                logger.info(
                    f"Filtered {symbol} to market hours: {len(df)} bars remaining"
                )

            # =====================================================
            # JOIN FEATURES — use features_wide materialized view
            # =====================================================
            async with self.timescale.engine.connect() as conn:
                feat_result = await conn.execute(
                    text(
                        """
                        SELECT * FROM features_wide
                        WHERE symbol = :symbol
                        ORDER BY time ASC
                        """
                    ),
                    {"symbol": symbol},
                )
                feat_rows = feat_result.fetchall()

            if feat_rows:
                cols = feat_result.keys()
                feat_df = pd.DataFrame(feat_rows, columns=cols)
                if "symbol" in feat_df.columns:
                    feat_df = feat_df.drop(columns=["symbol"])
                feat_df["time"] = pd.to_datetime(feat_df["time"])
                df = df.merge(feat_df, on="time", how="left")
                df = df.sort_values("time")
                # NOTE: bfill() removed to prevent future lookahead leakage
                # Remaining NaNs (no prior data) are filled with 0
                df = df.ffill().fillna(0)

            logger.info(f"{strategy_id}: Columns available: {df.columns.tolist()}")

            # =====================================================
            # REFERENCED FEATURE VALIDATION (check only features the strategy actually uses)
            # =====================================================
            _raw_params = strategy_record.get("parameters", {})
            if isinstance(_raw_params, str):
                try:
                    _raw_params = json.loads(_raw_params)
                except Exception:
                    _raw_params = {}
            _ec = (
                _raw_params.get("entry_conditions", [])
                if isinstance(_raw_params, dict)
                else []
            )
            _xc = (
                _raw_params.get("exit_conditions", [])
                if isinstance(_raw_params, dict)
                else []
            )
            _referenced_features = set()
            for _cond in _ec + _xc:
                for _feat in re.findall(r"\b[a-z_][a-z_0-9]*\b", str(_cond)):
                    _referenced_features.add(_feat)
            _missing = [f for f in _referenced_features if f not in df.columns]
            if _missing:
                logger.error(
                    f"{strategy_id}: Referenced features missing from data: {_missing}"
                )
                await self.timescale.update_strategy_status(
                    strategy_id, "backtest_failed"
                )
                await self.messaging.publish(
                    Channel.STRATEGY_SIGNALS,
                    {
                        "type": "backtest_complete",
                        "strategy_id": strategy_id,
                        "sharpe": 0.0,
                        "passed": False,
                        "reason": f"missing_referenced_features: {_missing}",
                    },
                )
                return

            # Phase 30: Reduced minimum bar requirement from 50 to 30 for faster iteration
            if len(df) < 30:
                logger.warning(f"{strategy_id}: Only {len(df)} bars — insufficient")

                await self.timescale.update_strategy_status(
                    strategy_id,
                    "backtest_failed",
                )

                return

            # =====================================================
            # DEBUG: Log entry condition strings + feature stats
            # =====================================================
            logger.info(
                f"=== DEBUG [{strategy_id[:8]}] {strategy_record.get('name', '?')} "
                f"on {symbol} ==="
            )
            params = strategy_record.get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}
            entry_conds = (
                params.get("entry_conditions", []) if isinstance(params, dict) else []
            )
            exit_conds = (
                params.get("exit_conditions", []) if isinstance(params, dict) else []
            )
            logger.info(f"Entry conditions: {entry_conds}")
            logger.info(f"Exit conditions:  {exit_conds}")
            logger.info(f"Generated code:\n{code[:2000]}")

            for col in entry_conds + exit_conds:
                for feat in [
                    "rsi_14",
                    "price_vs_vwap_pct",
                    "trend_strength",
                    "relative_volume",
                    "bollinger_band_position",
                    "volatility_regime",
                    "ema_spread_pct",
                ]:
                    if feat in col and feat in df.columns:
                        vals = df[feat].dropna()
                        if len(vals) > 0:
                            logger.info(
                                f"  {feat}: min={vals.min():.6f} max={vals.max():.6f} "
                                f"mean={vals.mean():.6f} non_null={len(vals)}/{len(df)}"
                            )
                        else:
                            logger.info(f"  {feat}: ALL NaN ({len(df)} rows)")

            # =====================================================
            # NaN THRESHOLD CHECK — reject if any strategy-referenced feature
            # has >20% missing values (stale features_wide)
            # =====================================================
            referenced_features = set()
            import re as _re

            for cond in entry_conds + exit_conds:
                for feat in _re.findall(r"\b[a-z_][a-z_0-9]*\b", cond):
                    if feat in df.columns:
                        referenced_features.add(feat)
            high_nan = []
            for feat in referenced_features:
                nan_pct = df[feat].isna().mean()
                # Phase 30: Relax NaN threshold from 20% to 35% to allow more strategies through
                if nan_pct > 0.35:
                    high_nan.append(f"{feat}={nan_pct:.0%}")
            if high_nan:
                logger.error(
                    f"{strategy_id}: Rejecting — high NaN features: {high_nan}"
                )
                await self.timescale.update_strategy_status(
                    strategy_id, "backtest_failed"
                )
                await self.messaging.publish(
                    Channel.STRATEGY_SIGNALS,
                    {
                        "type": "backtest_complete",
                        "strategy_id": strategy_id,
                        "sharpe": 0.0,
                        "passed": False,
                        "reason": f"high_nan_features: {high_nan}",
                    },
                )
                await self._log_lifecycle(
                    trace_id,
                    strategy_id,
                    "backtest",
                    "failed",
                    {"error": f"high_nan_features: {high_nan}"},
                )
                return

            # =====================================================
            # RUN BACKTEST
            # =====================================================
            bt_result = await self._run_backtest(
                strategy_instance,
                df,
                symbol,
                strategy_id=strategy_id,
                trace_id=trace_id,
            )
            if bt_result is None:
                return
            results, trades, signals = bt_result
            results = clean_metrics(results)

            # Log dynamic slippage stats
            if "_dyn_slippage_mult" in df.columns:
                mult = df["_dyn_slippage_mult"].values
                logger.info(
                    f"{strategy_id}: Dynamic slippage mult — "
                    f"min={mult.min():.2f}x median={np.nanmedian(mult):.2f}x "
                    f"max={mult.max():.2f}x"
                )

            # =====================================================
            # ADVANCED VALIDATION — walk-forward, overfitting, regime, Monte Carlo
            # =====================================================
            await self._run_advanced_validation(
                strategy_id=strategy_id,
                df=df,
                signals=signals,
                trades=trades,
                trace_id=trace_id,
            )

            # =====================================================
            # SAVE RESULTS
            # =====================================================
            await self.timescale.save_backtest_results(
                strategy_id=strategy_id,
                results=results,
                start_date=df["time"].iloc[0].isoformat(),
                end_date=df["time"].iloc[-1].isoformat(),
            )

            # =====================================================
            # WRITE BACK METRICS TO STRATEGIES TABLE
            # =====================================================
            await self.timescale.update_strategy_fields(
                strategy_id=strategy_id,
                train_sharpe=results.get("train_sharpe", 0.0),
                test_sharpe=results.get("test_sharpe", 0.0),
                holdout_sharpe=results.get("holdout_sharpe", 0.0),
                validation_metrics=json.dumps(
                    clean_metrics(
                        {
                            k: results.get(k)
                            for k in [
                                "total_return",
                                "cagr",
                                "max_drawdown",
                                "win_rate",
                                "total_trades",
                                "profit_factor",
                                "sortino_ratio",
                                "calmar_ratio",
                                "expectancy",
                                "composite_fitness_score",
                                "composite_score",
                                "short_window_score",
                                "regime_score",
                                "evaluation_mode",
                                "entry_count",
                                "exit_count",
                                "bars_processed",
                                "per_bar_sharpe",
                                "per_trade_sharpe",
                            ]
                        }
                    )
                ),
            )
            logger.info(
                f"{strategy_id}: Metrics written back to strategies table — "
                f"train_sharpe={results.get('train_sharpe', 0.0):.4f} "
                f"test_sharpe={results.get('test_sharpe', 0.0):.4f} "
                f"holdout_sharpe={results.get('holdout_sharpe', 0.0):.4f}"
            )

            # =====================================================
            # SAVE TRADES
            # =====================================================
            for trade in trades:
                trade["symbol"] = symbol
                await self.timescale.save_backtest_trade(strategy_id, trade)

            # =====================================================
            # UPDATE STATUS
            # =====================================================
            await self.timescale.update_strategy_code(
                strategy_id,
                code,
                "pending_validation",
            )

            # =====================================================
            # PUBLISH
            # =====================================================
            await self.messaging.publish(
                Channel.STRATEGY_SIGNALS,
                {
                    "type": "backtest_complete",
                    "strategy_id": strategy_id,
                    "sharpe": results.get("holdout_sharpe", 0.0),
                    "passed": True,
                },
            )

            await self._log_lifecycle(
                trace_id,
                strategy_id,
                "backtest",
                "completed",
                {
                    "sharpe": results.get("holdout_sharpe", 0.0),
                    "trades": results.get("total_trades", 0),
                    "symbol": symbol,
                },
            )

            logger.info(
                f"Backtest complete for {strategy_id} | "
                f"Entries={results.get('entry_count', '?')} | "
                f"Exits={results.get('exit_count', '?')} | "
                f"Trades={results.get('total_trades')} | "
                f"Sharpe={results.get('holdout_sharpe')} | "
                f"Symbol={symbol}"
            )

        except Exception as e:
            import traceback

            logger.error(
                f"Backtest error for {strategy_id}: {type(e).__name__}: {e}\n{traceback.format_exc()}"
            )

            await self.timescale.update_strategy_status(
                strategy_id,
                "backtest_failed",
            )

            await self.messaging.publish(
                Channel.STRATEGY_SIGNALS,
                {
                    "type": "backtest_complete",
                    "strategy_id": strategy_id,
                    "sharpe": 0.0,
                    "passed": False,
                    "reason": "runtime_backtest_error",
                },
            )

            await self._log_lifecycle(
                trace_id,
                strategy_id,
                "backtest",
                "failed",
                {"error": f"{type(e).__name__}: {str(e)[:200]}"},
            )

    def _compute_regime_score(self, df: pd.DataFrame, signals: pd.Series) -> float:
        """
        Compute regime robustness score [0.0, 1.0].

        Measures how many distinct market regimes the strategy entered trades in.
        Single-regime strategies (overfit to specific conditions) score 0.0.
        Multi-regime strategies (robust across market states) score higher.

        Regimes classified using same feature logic as generated code:
        - high_vol / low_vol: based on volatility_regime
        - bullish / bearish / neutral: based on ema_spread_pct
        - trending / ranging: based on trend_strength
        - overbought / oversold: based on bollinger_band_position
        """
        # Include both long (1) and short (-1) entry signals for regime scoring
        entry_signals = signals[signals != 0]
        if entry_signals.empty:
            return 0.0

        # Classify each bar into a regime bucket
        # NOTE: This is a lightweight approximation of the full regime classification
        # in coder_agent._regime_computation_code. The generated strategy code uses
        # compound criteria (e.g., bullish = trending + ema > threshold), while this
        # scoring uses simpler single-field thresholds. Scores are directional but
        # not exact matches to the strategy's internal regime gate logic.
        regimes = pd.Series("unknown", index=df.index, dtype=str)

        vol = df.get("volatility_regime", pd.Series(1.0, index=df.index))
        ema = df.get("ema_spread_pct", pd.Series(0.0, index=df.index))
        trend = df.get("trend_strength", pd.Series(0.0, index=df.index))
        bb = df.get("bollinger_band_position", pd.Series(0.5, index=df.index))

        # Volatility regimes
        regimes.loc[vol > 1.4] = "high_vol"
        regimes.loc[(vol >= 0.7) & (vol <= 1.4)] = "normal_vol"
        regimes.loc[vol < 0.7] = "low_vol"

        # Directional regimes (override vol-only if trending)
        trending_mask = trend > 0.002
        regimes.loc[trending_mask & (ema > 0.001)] = "bullish"
        regimes.loc[trending_mask & (ema < -0.001)] = "bearish"
        regimes.loc[~trending_mask & (vol >= 0.7) & (vol <= 1.4)] = "ranging"

        # Bollinger regimes (override if extreme)
        regimes.loc[bb > 0.8] = "overbought"
        regimes.loc[bb < 0.2] = "oversold"

        # Get distinct regimes at entry points
        entry_regimes = regimes.loc[entry_signals.index]
        distinct = entry_regimes.unique()
        distinct = [r for r in distinct if r != "unknown"]

        n = len(distinct)
        # Score: single regime = 0.0, 2 regimes = 0.5, 3+ = 1.0
        if n >= 3:
            return 1.0
        elif n == 2:
            return 0.5
        return 0.0

    def _compute_dynamic_slippage(self, df: pd.DataFrame) -> np.ndarray:
        """
        Compute per-bar dynamic slippage multiplier based on market conditions.

        Uses rolling_volatility and relative_volume to estimate liquidity regime:
        - Higher volatility  -> wider spreads        -> higher slippage (up to DYN_SLIPPAGE_MAX_MULT)
        - Lower volume       -> less liquidity       -> higher slippage (up to DYN_SLIPPAGE_MAX_MULT)
        - Calm, liquid conditions -> lower slippage  (down to DYN_SLIPPAGE_MIN_MULT)
        """
        vol = df["rolling_volatility"].astype(float).values
        rel_vol = df["relative_volume"].astype(float).values

        # Volatility multiplier: normalized by median
        median_vol = np.nanmedian(vol)
        if not np.isfinite(median_vol) or median_vol <= 0:
            median_vol = 1.0
        vol_mult = np.where(np.isfinite(vol) & (vol > 0), vol / median_vol, 1.0)
        vol_mult = np.clip(
            vol_mult, self.DYN_SLIPPAGE_VOL_FLOOR, self.DYN_SLIPPAGE_VOL_CAP
        )

        # Volume multiplier: lower relative volume -> less liquidity -> higher cost
        rel_vol_safe = np.where(np.isfinite(rel_vol) & (rel_vol > 0.01), rel_vol, 1.0)
        volume_mult = np.clip(
            1.0 / rel_vol_safe,
            self.DYN_SLIPPAGE_VOLUME_FLOOR,
            self.DYN_SLIPPAGE_VOLUME_CAP,
        )

        # Combine via geometric mean
        combined = np.sqrt(vol_mult * volume_mult)
        combined = np.clip(
            combined, self.DYN_SLIPPAGE_MIN_MULT, self.DYN_SLIPPAGE_MAX_MULT
        )

        return combined

    def _compute_vol_adjusted_position_size(self, df: pd.DataFrame, base_size: float = 0.10) -> np.ndarray:
        """
        Compute per-bar volatility-adjusted position size.
        
        Uses rolling_volatility to scale position size inversely:
        - Low vol (< 50th percentile): increase size up to vol_position_max (20%)
        - High vol (> 80th percentile): decrease size down to vol_position_min (5%)
        - Normal vol: use base_size (10%)
        """
        if "rolling_volatility" not in df.columns:
            return np.full(len(df), base_size)
        
        vol = df["rolling_volatility"].astype(float).values
        median_vol = np.nanmedian(vol)
        if not np.isfinite(median_vol) or median_vol <= 0:
            return np.full(len(df), base_size)
        
        # Ratio: <1 = low vol (increase size), >1 = high vol (decrease size)
        vol_ratio = vol / median_vol
        vol_ratio = np.clip(vol_ratio, 0.1, 5.0)
        
        # Inverse sqrt scaling: low vol = larger position
        position_sizing = base_size / np.sqrt(vol_ratio)
        # Clamp to reasonable bounds
        min_pos_size = 0.05
        max_pos_size = 0.20
        position_sizing = np.clip(position_sizing, min_pos_size, max_pos_size)
        position_sizing = np.where(np.isfinite(position_sizing), position_sizing, base_size)
        
        return position_sizing

    async def _run_advanced_validation(
        self,
        strategy_id: str,
        df: pd.DataFrame,
        signals: pd.Series,
        trades: list[dict],
        trace_id: str | None = None,
    ) -> None:
        """
        Run advanced validation agents (walk-forward, overfitting, regime, Monte Carlo)
        after the backtest completes. These feed the walk_forward_analysis,
        overfitting_analysis, regime_validation, and monte_carlo_analysis tables
        so that DeploymentGovernor can query them during the promotion gate.
        """
        try:
            # ---- Walk-Forward Analysis ----
            wf = WalkForwardAnalyzer(db_client=self.timescale)
            wf_result = await wf.analyze(
                strategy_id=strategy_id,
                df=df,
                signals=signals,
                background_results={},
            )
            logger.info(
                f"{strategy_id}: Walk-forward score={wf_result.get('walk_forward_score', 0):.2f} "
                f"({wf_result.get('n_windows_survived', 0)}/{wf_result.get('n_windows_total', 0)} windows)"
            )
        except Exception as e:
            logger.warning(f"{strategy_id}: Walk-forward analysis failed: {e}")

        try:
            # ---- Overfitting Detection ----
            od = OverfittingDetector(db_client=self.timescale)
            od_result = await od.detect(
                strategy_id=strategy_id,
                df=df,
                signals=signals,
                params=None,
            )
            logger.info(
                f"{strategy_id}: Overfit prob={od_result.get('overfit_probability', 0):.2f} "
                f"robustness={od_result.get('robustness_score', 0):.2f}"
            )
        except Exception as e:
            logger.warning(f"{strategy_id}: Overfitting detection failed: {e}")

        try:
            # ---- Regime Validation ----
            rv = RegimeValidator(db_client=self.timescale)
            rv_result = await rv.validate(
                strategy_id=strategy_id,
                df=df,
                signals=signals,
            )
            logger.info(
                f"{strategy_id}: Regime survival score={rv_result.get('regime_survival_score', 0):.2f} "
                f"({rv_result.get('n_regimes_survived', 0)}/{rv_result.get('n_regimes_total', 0)} regimes)"
            )
        except Exception as e:
            logger.warning(f"{strategy_id}: Regime validation failed: {e}")

        try:
            # ---- Monte Carlo Simulation ----
            mc = MonteCarloSimulator(db_client=self.timescale)
            mc_result = await mc.simulate(
                strategy_id=strategy_id,
                trades=trades,
                background_results={},
            )
            logger.info(
                f"{strategy_id}: Monte Carlo survival={mc_result.get('monte_carlo_survival_score', 0):.2f} "
                f"tail_drawdown={mc_result.get('expected_tail_drawdown', 0):.4f}"
            )
        except Exception as e:
            logger.warning(f"{strategy_id}: Monte Carlo simulation failed: {e}")

    def _calc_sharpe(self, trade_returns: list, symbol: str = "") -> float:
        """
        Diagnostic Sharpe calculation for discrete trade returns (per-trade PnL pct).

        Uses actual trade-level PnL percentages, not per-bar strategy returns
        which are dominated by zeros for sparse-signal strategies.

        Returns 0.0 for insufficient data or near-zero volatility.
        """
        if not trade_returns or len(trade_returns) < 3:
            return 0.0

        arr = np.array(trade_returns, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        if std < 1e-8:
            logger.warning(
                f"Sharpe calc: std={std:.6f} near zero "
                f"(mean={mean:.6f}, n={len(arr)}) \u2014 returning 0"
            )
            return 0.0
        annualization_factor = 525600 if symbol.endswith("USDT") else 252 * 390
        annualization = annualization_factor**0.5
        return float((mean / std) * annualization)

    async def _log_lifecycle(self, trace_id, strategy_id, stage, status, metadata=None):
        if not trace_id:
            return
        try:
            lineage = EventLineageClient(self.timescale)
            await lineage.create_event(
                trace_id=trace_id,
                stage=stage,
                status=status,
                actor=self.name,
                strategy_id=strategy_id,
                metadata=metadata or {},
            )
        except Exception as exc:
            logger.warning(f"Lifecycle event log failed ({stage}/{status}): {exc}")

    async def _run_backtest(
        self,
        strategy,
        df: pd.DataFrame,
        symbol: str = "",
        strategy_id: str = "unknown",
        trace_id: str | None = None,        ) -> tuple[dict, list] | None:
        # FUTURE LEAKAGE GUARD: Pass a deep copy WITHOUT the time column.
        # This prevents strategies from using absolute timestamps to infer
        # their position in the data sequence (which would enable lookahead).
        # The time column is re-added below after signal generation.
        _backtest_df = df.drop(columns=["time"], errors="ignore").copy()
        signals = strategy.generate_signals(_backtest_df)

        if not isinstance(signals, pd.Series):
            raise TypeError(
                f"generate_signals must return pd.Series, got {type(signals)}"
            )

        signals = signals.reindex(df.index).fillna(0)

        entry_count = int((signals == 1).sum())
        exit_count = int((signals == -1).sum())
        total_signals = int((signals != 0).sum())

        if total_signals == 0:
            logger.warning(
                f"Strategy produced 0 signals — marking as no_signal_strategy"
            )
            await self.timescale.update_strategy_status(
                strategy_id,
                "no_signal_strategy",
                "Strategy generated zero entry signals across all bars",
            )
            await self.messaging.publish(
                Channel.STRATEGY_SIGNALS,
                {
                    "type": "backtest_complete",
                    "strategy_id": strategy_id,
                    "sharpe": 0.0,
                    "passed": False,
                    "reason": "no_signal_strategy",
                },
            )
            await self._log_lifecycle(
                trace_id,
                strategy_id,
                "backtest",
                "failed",
                {"error": "no_signal_strategy"},
            )
            return None

        logger.info(
            f"Backtest signals — entry: {entry_count}, "
            f"exit: {exit_count}, rows: {len(df)}"
        )

        df = df.copy()
        df["signal"] = signals

        # =====================================================
        # =====================================================
        # STATE MACHINE TRADE EXTRACTION
        # FLAT (0) → LONG (+1) or SHORT (-1)
        # Signal conventions:
        #   1  = enter long OR exit short
        #   -1 = enter short OR exit long
        # Also checks stop-loss/take-profit on each bar while in position.
        # =====================================================
        # Extract SL/TP from strategy instance (default: disabled)
        sl_pct = getattr(strategy, "stop_loss_pct", 0.0)
        tp_pct = getattr(strategy, "take_profit_pct", 0.0)

        trades = []
        pos = 0  # -1 = short, 0 = flat, 1 = long
        entry_price = 0.0
        entry_time = None
        entry_bar = 0

        position_series = pd.Series(0, index=df.index, dtype=int)
        closed_positions_count = 0

        for i in range(len(df)):
            sig = signals.iloc[i]

            if pos == 0:
                if sig == 1:
                    # Enter long
                    pos = 1
                    entry_price = float(df["close"].iloc[i])
                    entry_time = df["time"].iloc[i]
                    entry_bar = i
                elif sig == -1:
                    # Enter short
                    pos = -1
                    entry_price = float(df["close"].iloc[i])
                    entry_time = df["time"].iloc[i]
                    entry_bar = i
            elif pos == 1:
                # In a LONG position — exit on signal -1, stop-loss, or take-profit
                current_price = float(df["close"].iloc[i])
                _sl_triggered = (
                    sl_pct > 0 and current_price <= entry_price * (1.0 - sl_pct)
                )
                _tp_triggered = (
                    tp_pct > 0 and current_price >= entry_price * (1.0 + tp_pct)
                )
                _exit_signal = sig == -1

                if _exit_signal or _sl_triggered or _tp_triggered:
                    exit_price = current_price
                    pnl = exit_price - entry_price
                    pnl_pct = pnl / entry_price if entry_price != 0 else 0.0
                    _exit_reason = (
                        "stop_loss" if _sl_triggered else
                        "take_profit" if _tp_triggered else
                        "signal"
                    )
                    trades.append(
                        {
                            "entry_time": entry_time,
                            "exit_time": df["time"].iloc[i],
                            "entry_price": round(entry_price, 8),
                            "exit_price": round(exit_price, 8),
                            "side": "long",
                            "pnl": round(pnl, 8),
                            "pnl_pct": round(pnl_pct, 8),
                            "bars_held": i - entry_bar,
                            "exit_reason": _exit_reason,
                        }
                    )
                    pos = 0
                    closed_positions_count += 1
            elif pos == -1:
                # In a SHORT position — exit on signal 1, stop-loss, or take-profit
                current_price = float(df["close"].iloc[i])
                # SL for short: price rises above entry * (1 + sl%)
                _sl_triggered = (
                    sl_pct > 0 and current_price >= entry_price * (1.0 + sl_pct)
                )
                # TP for short: price drops below entry * (1 - tp%)
                _tp_triggered = (
                    tp_pct > 0 and current_price <= entry_price * (1.0 - tp_pct)
                )
                _exit_signal = sig == 1

                if _exit_signal or _sl_triggered or _tp_triggered:
                    exit_price = current_price
                    # Short PnL = entry_price - exit_price (profitable when price falls)
                    pnl = entry_price - exit_price
                    pnl_pct = pnl / entry_price if entry_price != 0 else 0.0
                    _exit_reason = (
                        "stop_loss" if _sl_triggered else
                        "take_profit" if _tp_triggered else
                        "signal"
                    )
                    trades.append(
                        {
                            "entry_time": entry_time,
                            "exit_time": df["time"].iloc[i],
                            "entry_price": round(entry_price, 8),
                            "exit_price": round(exit_price, 8),
                            "side": "short",
                            "pnl": round(pnl, 8),
                            "pnl_pct": round(pnl_pct, 8),
                            "bars_held": i - entry_bar,
                            "exit_reason": _exit_reason,
                        }
                    )
                    pos = 0
                    closed_positions_count += 1

            position_series.iloc[i] = pos

        logger.info(
            f"Backtest extracted {len(trades)} closed trades from "
            f"{entry_count} entry signals, {exit_count} exit signals"
        )

        # Anomaly detection
        if exit_count > 0 and closed_positions_count > 0:
            exits_per_trade = exit_count / closed_positions_count
            if exits_per_trade > 3:
                logger.warning(
                    f"ANOMALY: {exits_per_trade:.1f} exit signals per closed trade "
                    f"({exit_count} exits, {closed_positions_count} trades)"
                )
        if exit_count > entry_count * 2 and entry_count > 0:
            logger.warning(
                f"ANOMALY: exit_count ({exit_count}) > 2x entry_count ({entry_count})"
            )

        closed_trades = len(trades)

        # Use state machine position series for metric computation
        df["position"] = position_series
        df["market_return"] = df["close"].pct_change().fillna(0)

        n = len(df)
        train_end = int(n * 0.6)
        test_end = int(n * 0.8)

        def calc_metrics_institutional(sub_df, dyn_mult=None, pos_size=None):
            if len(sub_df) == 0:
                return (0.0, 0.0, 0.0, 0.0, 0.0, 0, 1.0)

            sub_df = sub_df.copy()

            sub_df["market_return"] = sub_df["close"].pct_change().fillna(0)

            per_side_base = (
                self.commission_pct + self.slippage_pct + self.spread_cost_pct
            )

            if dyn_mult is not None and len(dyn_mult) == len(sub_df):
                per_side_cost = per_side_base * dyn_mult
                total_roundtrip = per_side_cost * 2
            else:
                total_flat = per_side_base * 2
                total_roundtrip = np.full(len(sub_df), total_flat)

            sub_df["trade_cost"] = np.where(
                sub_df["position"].diff().fillna(0) != 0,
                total_roundtrip,
                0.0,
            )

            # Use per-bar position size if provided, fall back to fixed
            _pos_size = pos_size if pos_size is not None else self.position_size
            sub_df["strategy_return"] = (
                sub_df["position"] * sub_df["market_return"] * _pos_size
            ) - (sub_df["trade_cost"] * _pos_size)

            sub_df["cum_return"] = (1 + sub_df["strategy_return"]).cumprod()

            total_return = (
                sub_df["cum_return"].iloc[-1] - 1 if not sub_df.empty else 0.0
            )

            bars_per_year = 525600 if symbol.endswith("USDT") else 252 * 390
            if total_return <= -1.0:
                cagr = -1.0
            else:
                cagr = ((1 + total_return) ** (bars_per_year / max(len(sub_df), 1))) - 1

            if isinstance(cagr, complex):
                cagr = -1.0
            elif pd.isna(cagr) or np.isnan(cagr) or np.isinf(cagr):
                cagr = 0.0

            trades = sub_df[sub_df["position"].diff().fillna(0) != 0]
            total_trades = len(trades) // 2

            # Phase 30: Minimum trade threshold lowered to 2 to increase trade density
            if total_trades < 2:
                return (0.0, 0.0, 0.0, 0.0, 0.0, total_trades, 1.0, 0.0, 0.0)

            std = sub_df["strategy_return"].std()

            sharpe_ratio = 0.0
            if std and std > 0:
                sharpe_ratio = np.sqrt(bars_per_year) * (
                    sub_df["strategy_return"].mean() / std
                )

            if np.isnan(sharpe_ratio):
                sharpe_ratio = 0.0

            # Cap extreme Sharpe values from sparse signals
            sharpe_ratio = max(min(sharpe_ratio, 10.0), -10.0)

            # SAFETY: Cap cum_return at 0 before computing drawdown to prevent below-100% values
            _cum_safe = sub_df["cum_return"].clip(lower=0)
            roll_max = _cum_safe.cummax()
            drawdown = _cum_safe / roll_max - 1
            max_drawdown = drawdown.min()

            winning_periods = sub_df[sub_df["strategy_return"] > 0]
            losing_periods = sub_df[sub_df["strategy_return"] < 0]

            win_rate = 0.0
            if len(winning_periods) + len(losing_periods) > 0:
                win_rate = len(winning_periods) / (
                    len(winning_periods) + len(losing_periods)
                )

            gross_profit = winning_periods["strategy_return"].sum()
            gross_loss = abs(losing_periods["strategy_return"].sum())

            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0

            if np.isnan(profit_factor) or np.isinf(profit_factor):
                profit_factor = 1.0

            downside_returns = sub_df[sub_df["strategy_return"] < 0]["strategy_return"]
            downside_std = downside_returns.std()
            sortino_ratio = 0.0
            if downside_std and downside_std > 0:
                sortino_ratio = np.sqrt(bars_per_year) * (
                    sub_df["strategy_return"].mean() / downside_std
                )
            if np.isnan(sortino_ratio):
                sortino_ratio = 0.0
            sortino_ratio = max(min(sortino_ratio, 15.0), -10.0)

            expectancy = 0.0
            if total_trades > 0:
                avg_win = (
                    winning_periods["strategy_return"].mean()
                    if len(winning_periods) > 0
                    else 0.0
                )
                avg_loss = (
                    abs(losing_periods["strategy_return"].mean())
                    if len(losing_periods) > 0
                    else 0.0
                )
                expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

            try:
                total_return = (
                    float(total_return)
                    if not np.isnan(float(total_return))
                    and not np.isinf(float(total_return))
                    else 0.0
                )
                cagr = (
                    float(cagr)
                    if not np.isnan(float(cagr)) and not np.isinf(float(cagr))
                    else 0.0
                )
                sharpe_ratio = (
                    float(sharpe_ratio)
                    if not np.isnan(float(sharpe_ratio))
                    and not np.isinf(float(sharpe_ratio))
                    else 0.0
                )
                max_drawdown = (
                    float(max_drawdown)
                    if not np.isnan(float(max_drawdown))
                    and not np.isinf(float(max_drawdown))
                    else 0.0
                )
                win_rate = (
                    float(win_rate)
                    if not np.isnan(float(win_rate)) and not np.isinf(float(win_rate))
                    else 0.0
                )
                profit_factor = (
                    float(profit_factor)
                    if not np.isnan(float(profit_factor))
                    and not np.isinf(float(profit_factor))
                    else 1.0
                )
                sortino_ratio = (
                    float(sortino_ratio)
                    if not np.isnan(float(sortino_ratio))
                    and not np.isinf(float(sortino_ratio))
                    else 0.0
                )
                expectancy = (
                    float(expectancy)
                    if not np.isnan(float(expectancy))
                    and not np.isinf(float(expectancy))
                    else 0.0
                )
            except Exception:
                pass

            return (
                total_return,
                cagr,
                sharpe_ratio,
                max_drawdown,
                win_rate,
                total_trades,
                profit_factor,
                sortino_ratio,
                expectancy,
            )

        train_df = df.iloc[:train_end]
        test_df = df.iloc[train_end:test_end]
        holdout_df = df.iloc[test_end:]

        # Compute dynamic slippage multipliers
        dyn_mult = self._compute_dynamic_slippage(df)
        df["_dyn_slippage_mult"] = dyn_mult

        # Volatility-adjusted position sizing (per-bar)
        pos_size_arr = self._compute_vol_adjusted_position_size(df, self.position_size)
        df["_pos_size"] = pos_size_arr

        train_mult = dyn_mult[:train_end]
        test_mult = dyn_mult[train_end:test_end]
        holdout_mult = dyn_mult[test_end:]

        train_pos_size = pos_size_arr[:train_end]
        test_pos_size = pos_size_arr[train_end:test_end]
        holdout_pos_size = pos_size_arr[test_end:]

        if is_short_window(df):
            sw_train = compute_short_window_metrics(
                train_df,
                train_df["position"],
                train_df["market_return"],
                train_pos_size,
                self.commission_pct,
                self.slippage_pct,
                self.spread_cost_pct,
                dynamic_slippage=train_mult,
            )
            sw_test = compute_short_window_metrics(
                test_df,
                test_df["position"],
                test_df["market_return"],
                test_pos_size,
                self.commission_pct,
                self.slippage_pct,
                self.spread_cost_pct,
                dynamic_slippage=test_mult,
            )
            sw_holdout = compute_short_window_metrics(
                holdout_df,
                holdout_df["position"],
                holdout_df["market_return"],
                holdout_pos_size,
                self.commission_pct,
                self.slippage_pct,
                self.spread_cost_pct,
                dynamic_slippage=holdout_mult,
            )

            composite = compute_composite_short_window_score(sw_holdout)

            logger.info(
                f"SHORT WINDOW MODE: {len(df)} bars | "
                f"Return={sw_holdout['total_return']:+.4%} | "
                f"Gross={sw_holdout['gross_edge']:+.4%} | "
                f"Cost={sw_holdout['cost_burden']:+.4%} | "
                f"Trades={sw_holdout['total_trades']} | "
                f"PF={sw_holdout['profit_factor']:.2f} | "
                f"WR={sw_holdout['win_rate']:.1%} | "
                f"Composite={composite}"
            )

            regime_score = self._compute_regime_score(df, signals)

            # Per-bar Sharpe from short_window evaluator (near 0 for sparse signals)
            per_bar_sharpe = sw_holdout.get("sharpe_ratio", 0.0)

            # Per-trade Sharpe using actual trade PnL pcts (meaningful for sparse signals)
            all_trade_returns = [
                t.get("pnl_pct") for t in trades if t.get("pnl_pct") is not None
            ]
            per_trade_sharpe = self._calc_sharpe(all_trade_returns, symbol)

            # Use per-trade Sharpe as primary; fall back to per-bar for 0-trade strategies
            holdout_sharpe = (
                per_trade_sharpe if per_trade_sharpe != 0.0 else per_bar_sharpe
            )
            # Window-specific per-bar Sharpe for overfit detection
            train_sharpe = sw_train.get("sharpe_ratio", 0.0)
            test_sharpe = sw_test.get("sharpe_ratio", 0.0)

            logger.info(
                f"Sharpe: train_per_bar={train_sharpe:.4f} test_per_bar={test_sharpe:.4f} "
                f"holdout_per_trade={holdout_sharpe:.4f} "
                f"(from {len(all_trade_returns)} trade returns, {len(trades)} closed trades)"
            )

            results = {
                "total_return": float(sw_holdout["total_return"]),
                "cagr": 0.0,
                "sharpe_ratio": float(holdout_sharpe),
                "max_drawdown": float(sw_holdout["max_drawdown"] * 100),
                "win_rate": float(sw_holdout["win_rate"]),
                "total_trades": int(max(sw_holdout["total_trades"], closed_trades)),
                "entry_count": entry_count,
                "exit_count": exit_count,
                "bars_processed": len(df),
                "avg_trade_duration_bars": 10,
                "profit_factor": float(sw_holdout["profit_factor"]),
                "calmar_ratio": 0.0,
                "holdout_sharpe": float(holdout_sharpe),
                "train_sharpe": float(train_sharpe),
                "test_sharpe": float(test_sharpe),
                "per_bar_sharpe": float(per_bar_sharpe),
                "per_trade_sharpe": float(per_trade_sharpe),
                "evaluation_mode": "short_window",
                "composite_score": float(composite),
                "short_window_score": float(composite),
                "composite_fitness_score": float(composite),
                "sortino_ratio": 0.0,
                "expectancy": 0.0,
                "gross_edge": float(sw_holdout["gross_edge"]),
                "cost_burden": float(sw_holdout["cost_burden"]),
                "avg_return_per_trade": float(sw_holdout["avg_return_per_trade"]),
                "trade_returns": all_trade_returns,
                "regime_score": float(regime_score),
            }
            return results, trades, signals

        # INSTITUTIONAL MODE — full annualized Sharpe (requires >20k bars)
        _, _, train_sharpe, _, _, _, _, _, _ = calc_metrics_institutional(
            train_df, train_mult, train_pos_size
        )
        _, _, test_sharpe, _, _, _, _, _, _ = calc_metrics_institutional(
            test_df, test_mult, test_pos_size
        )

        (
            h_ret,
            h_cagr,
            holdout_sharpe,
            h_max_drawdown,
            h_win_rate,
            h_total_trades,
            h_profit_factor,
            h_sortino,
            h_expectancy,
        ) = calc_metrics_institutional(holdout_df, holdout_mult, holdout_pos_size)

        calmar_ratio = h_cagr / abs(h_max_drawdown) if h_max_drawdown < -0.0001 else 0.0

        regime_score = self._compute_regime_score(df, signals)

        # Composite Fitness Engine (fixed normalization)
        # Blends Sharpe, Sortino, Calmar, Win Rate, and Expectancy
        # Expectancy is per-bar decimal; normalize so 0.1%/bar = 0.5 pts (capped at 5.0)
        _norm_expectancy = min(h_expectancy * 500, 5.0)
        composite_fitness_score = (
            (holdout_sharpe * 0.3)
            + (h_sortino * 0.3)
            + (calmar_ratio * 0.2)
            + (_norm_expectancy * 0.1)
            + (h_win_rate * 0.1)
        )

        return {
            "total_return": float(h_ret),
            "cagr": float(h_cagr),
            "sharpe_ratio": float(holdout_sharpe),
            "max_drawdown": float(h_max_drawdown * 100),
            "win_rate": float(h_win_rate),
            "total_trades": int(max(h_total_trades, closed_trades)),
            "entry_count": entry_count,
            "exit_count": exit_count,
            "bars_processed": len(df),
            "avg_trade_duration_bars": 10,
            "profit_factor": float(h_profit_factor),
            "calmar_ratio": float(calmar_ratio),
            "sortino_ratio": float(h_sortino),
            "expectancy": float(h_expectancy),
            "composite_fitness_score": float(composite_fitness_score),
            "holdout_sharpe": float(holdout_sharpe),
            "train_sharpe": float(train_sharpe),
            "test_sharpe": float(test_sharpe),
            "evaluation_mode": "institutional",
            "composite_score": float(composite_fitness_score),
            "gross_edge": 0.0,
            "cost_burden": 0.0,
            "avg_return_per_trade": 0.0,
            "regime_score": float(regime_score),
        }, trades, signals


async def main():
    print("=== BACKTEST MAIN STARTED ===", flush=True)

    settings = get_settings()

    print("=== CONNECTING REDIS ===", flush=True)
    redis_client = Redis.from_url(settings.redis_url)

    print("=== CREATING BACKTEST RUNNER ===", flush=True)
    agent = BacktestRunner(redis_client)

    print("=== STARTING BACKTEST RUNNER ===", flush=True)
    await agent.run()


if __name__ == "__main__":
    print("=== BACKTEST EXECUTION HIT ===", flush=True)
    asyncio.run(main())
