import asyncio
import json
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

    def generate_signals(self, df):
        return pd.Series(
            np.where(df["close"].pct_change().fillna(0) > 0, 1, -1),
            index=df.index,
        )


class BacktestRunner(BaseAgent):
    def __init__(self, redis_client):
        super().__init__("BacktestRunner", "backtester", "L3", redis_client)

        self.settings = get_settings()
        self.timescale = TimescaleClient(self.settings.database_url)
        self.messaging = MessagingClient(redis_client)

        self.commission_pct = 0.001
        self.slippage_pct = 0.0005
        self.spread_cost_pct = 0.0005
        self.position_size = 0.10

    async def run(self):
        print("=== BACKTEST RUN LOOP ENTERED ===", flush=True)
        logger.info("BacktestRunner DB polling started")

        # Run auto-migrations (schema creation, MV upgrades, etc.)
        await self.timescale.connect()

        while True:
            try:
                strategies = await self.timescale.get_strategies_by_status(
                    "pending_backtest"
                )

                print(f"=== FOUND {len(strategies)} STRATEGIES ===", flush=True)
                logger.info(f"Found {len(strategies)} pending_backtest strategies")

                for strategy in strategies:
                    await self.process_strategy(strategy)

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(
                    f"BacktestRunner loop error: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(5)

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
        strategy_id = strategy_record["id"]
        trace_id = strategy_record.get("trace_id")

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
                df = df.ffill().bfill()

            logger.info(f"{strategy_id}: Columns available: {df.columns.tolist()}")

            # =====================================================
            # MISSING COLUMN VALIDATION
            # =====================================================
            REQUIRED_FEATURES = [
                "returns",
                "log_returns",
                "rsi_14",
                "macd",
                "macd_signal",
                "vwap",
                "sma_5",
                "sma_20",
                "ema_5",
                "ema_12",
                "ema_26",
                "bollinger_lower",
                "bollinger_upper",
                "rolling_volatility",
                "price_vs_vwap_pct",
                "ema_spread_pct",
                "relative_volume",
                "bollinger_band_position",
                "volatility_regime",
                "trend_strength",
            ]
            missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
            if missing:
                logger.error(
                    f"{strategy_id}: Missing required features for {symbol}: {missing}"
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
                        "reason": f"missing_features: {missing}",
                    },
                )
                return

            if len(df) < 50:
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
                for feat in _re.findall(r"\b[a-z_]+\b", cond):
                    if feat in df.columns:
                        referenced_features.add(feat)
            high_nan = []
            for feat in referenced_features:
                nan_pct = df[feat].isna().mean()
                if nan_pct > 0.20:
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
            results, trades = await self._run_backtest(strategy_instance, df, symbol)
            results = clean_metrics(results)

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
            logger.error(
                f"Backtest error for {strategy_id}: {type(e).__name__}: {e}",
                exc_info=True,
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
        self, strategy, df: pd.DataFrame, symbol: str = ""
    ) -> tuple[dict, list]:
        signals = strategy.generate_signals(df)

        if not isinstance(signals, pd.Series):
            raise TypeError(
                f"generate_signals must return pd.Series, got {type(signals)}"
            )

        signals = signals.reindex(df.index).fillna(0)

        entry_count = int((signals == 1).sum())
        exit_count = int((signals == -1).sum())

        logger.info(
            f"Backtest signals — entry: {entry_count}, "
            f"exit: {exit_count}, rows: {len(df)}"
        )

        df = df.copy()
        df["signal"] = signals

        # =====================================================
        # STATE MACHINE TRADE EXTRACTION
        # FLAT (0) → ENTRY (+1) → LONG (1) → EXIT (-1) → FLAT (0)
        # =====================================================
        trades = []
        pos = 0  # 0 = flat, 1 = long
        entry_price = 0.0
        entry_time = None
        entry_bar = 0

        position_series = pd.Series(0, index=df.index, dtype=int)
        closed_positions_count = 0

        for i in range(len(df)):
            sig = signals.iloc[i]

            if pos == 0:
                if sig == 1:
                    pos = 1
                    entry_price = float(df["close"].iloc[i])
                    entry_time = df["time"].iloc[i]
                    entry_bar = i
            elif pos == 1:
                if sig == -1:
                    exit_price = float(df["close"].iloc[i])
                    pnl = exit_price - entry_price
                    pnl_pct = pnl / entry_price if entry_price != 0 else 0.0
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
                            "exit_reason": "signal",
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

        # Use state machine position series for metric computation
        df["position"] = position_series
        df["market_return"] = df["close"].pct_change().fillna(0)

        n = len(df)
        train_end = int(n * 0.6)
        test_end = int(n * 0.8)

        def calc_metrics_institutional(sub_df):
            if len(sub_df) == 0:
                return (0.0, 0.0, 0.0, 0.0, 0.0, 0, 1.0)

            sub_df = sub_df.copy()

            sub_df["market_return"] = sub_df["close"].pct_change().fillna(0)

            entry_cost = self.commission_pct + self.slippage_pct + self.spread_cost_pct
            exit_cost = self.commission_pct + self.slippage_pct + self.spread_cost_pct
            total_roundtrip_cost = entry_cost + exit_cost

            sub_df["trade_cost"] = np.where(
                sub_df["position"].diff().fillna(0) != 0,
                total_roundtrip_cost,
                0.0,
            )

            sub_df["strategy_return"] = (
                sub_df["position"] * sub_df["market_return"] * self.position_size
            ) - (sub_df["trade_cost"] * self.position_size)

            sub_df["cum_return"] = (1 + sub_df["strategy_return"]).cumprod()

            total_return = (
                sub_df["cum_return"].iloc[-1] - 1 if not sub_df.empty else 0.0
            )

            bars_per_year = 525600
            cagr = ((1 + total_return) ** (bars_per_year / max(len(sub_df), 1))) - 1

            if np.isnan(cagr) or np.isinf(cagr):
                cagr = 0.0

            trades = sub_df[sub_df["position"].diff().fillna(0) != 0]
            total_trades = len(trades) // 2

            # Require minimum trades for meaningful metrics
            if total_trades < 5:
                return (0.0, 0.0, 0.0, 0.0, 0.0, total_trades, 1.0)

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

            roll_max = sub_df["cum_return"].cummax()
            drawdown = sub_df["cum_return"] / roll_max - 1
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

            return (
                total_return,
                cagr,
                sharpe_ratio,
                max_drawdown,
                win_rate,
                total_trades,
                profit_factor,
            )

        train_df = df.iloc[:train_end]
        test_df = df.iloc[train_end:test_end]
        holdout_df = df.iloc[test_end:]

        if is_short_window(df):
            sw_train = compute_short_window_metrics(
                train_df,
                train_df["position"],
                train_df["market_return"],
                self.position_size,
                self.commission_pct,
                self.slippage_pct,
                self.spread_cost_pct,
            )
            sw_test = compute_short_window_metrics(
                test_df,
                test_df["position"],
                test_df["market_return"],
                self.position_size,
                self.commission_pct,
                self.slippage_pct,
                self.spread_cost_pct,
            )
            sw_holdout = compute_short_window_metrics(
                holdout_df,
                holdout_df["position"],
                holdout_df["market_return"],
                self.position_size,
                self.commission_pct,
                self.slippage_pct,
                self.spread_cost_pct,
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

            results = {
                "total_return": float(sw_holdout["total_return"]),
                "cagr": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": float(sw_holdout["max_drawdown"] * 100),
                "win_rate": float(sw_holdout["win_rate"]),
                "total_trades": int(sw_holdout["total_trades"]),
                "entry_count": entry_count,
                "exit_count": exit_count,
                "bars_processed": len(df),
                "avg_trade_duration_bars": 10,
                "profit_factor": float(sw_holdout["profit_factor"]),
                "calmar_ratio": 0.0,
                "holdout_sharpe": 0.0,
                "train_sharpe": 0.0,
                "test_sharpe": 0.0,
                "evaluation_mode": "short_window",
                "composite_score": float(composite),
                "short_window_score": float(composite),
                "gross_edge": float(sw_holdout["gross_edge"]),
                "cost_burden": float(sw_holdout["cost_burden"]),
                "avg_return_per_trade": float(sw_holdout["avg_return_per_trade"]),
            }
            return results, trades

        # INSTITUTIONAL MODE — full annualized Sharpe (requires >20k bars)
        _, _, train_sharpe, _, _, _, _ = calc_metrics_institutional(train_df)
        _, _, test_sharpe, _, _, _, _ = calc_metrics_institutional(test_df)

        (
            h_ret,
            h_cagr,
            holdout_sharpe,
            h_max_drawdown,
            h_win_rate,
            h_total_trades,
            h_profit_factor,
        ) = calc_metrics_institutional(holdout_df)

        calmar_ratio = h_cagr / abs(h_max_drawdown) if h_max_drawdown < 0 else 0.0

        return {
            "total_return": float(h_ret),
            "cagr": float(h_cagr),
            "sharpe_ratio": float(holdout_sharpe),
            "max_drawdown": float(h_max_drawdown * 100),
            "win_rate": float(h_win_rate),
            "total_trades": int(h_total_trades),
            "entry_count": entry_count,
            "exit_count": exit_count,
            "bars_processed": len(df),
            "avg_trade_duration_bars": 10,
            "profit_factor": float(h_profit_factor),
            "calmar_ratio": float(calmar_ratio),
            "holdout_sharpe": float(holdout_sharpe),
            "train_sharpe": float(train_sharpe),
            "test_sharpe": float(test_sharpe),
            "evaluation_mode": "institutional",
            "composite_score": 0.0,
            "gross_edge": 0.0,
            "cost_burden": 0.0,
            "avg_return_per_trade": 0.0,
        }, trades


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
