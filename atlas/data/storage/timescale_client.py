import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.sql import text
import pandas as pd


def _r4(v: float) -> float:
    return round(float(v), 4)


def _r6(v: float) -> float:
    return round(float(v), 6)


def _r8(v: float) -> float:
    return round(float(v), 8)


class BarData(BaseModel):
    time: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    interval: str
    asset_class: str = "crypto"


class OrderbookData(BaseModel):
    time: datetime
    symbol: str
    bids: Dict[str, Any]
    asks: Dict[str, Any]
    spread: float
    mid_price: float


class FeatureData(BaseModel):
    time: datetime
    symbol: str
    feature_name: str
    value: float


class AgentData(BaseModel):
    id: str
    name: str
    type: str
    layer: str
    status: str
    pid: Optional[int] = None
    last_heartbeat: datetime
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class LogData(BaseModel):
    time: datetime
    agent_id: str
    level: str
    message: str
    metadata: Optional[Dict[str, Any]] = None


class QuoteData(BaseModel):
    """Market data for quotes (Q.* stream)"""

    time: datetime
    symbol: str
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    bid_exchange: str
    ask_exchange: str
    source: str = "polygon"


class TradeData(BaseModel):
    """Market data for trades (T.* stream)"""

    time: datetime
    symbol: str
    price: float
    size: float
    side: str  # "buy", "sell", or "unknown"
    exchange: str
    source: str = "polygon"


class AggregateData(BaseModel):
    """Market data for aggregates (A.* stream) - used as L1 bars"""

    time: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float
    source: str = "polygon"
    interval: str = "1m"


class BinanceTradeData(BaseModel):
    """Crypto trade data from Binance @trade stream"""

    time: datetime
    symbol: str
    price: float
    quantity: float
    buyer_maker: bool  # True if buyer was the maker
    trade_id: int
    source: str = "binance"


class BinanceDepthData(BaseModel):
    """Crypto depth/orderbook data from Binance @depth20@100ms stream"""

    time: datetime
    symbol: str
    bids: Dict[str, Any]  # price: quantity mapping
    asks: Dict[str, Any]  # price: quantity mapping
    source: str = "binance"
    last_update_id: int = 0


class TimescaleClient:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(self.db_url, echo=False)

    async def get_mutation_leaderboard(self) -> list[dict]:
        """
        Retrieves the aggregated mutation intelligence (ranked by conversion rate and average delta).
        Provides IdeatorAgent with empirical priors of what mutations are currently working.
        """
        query = """
            SELECT
                mutation_type,
                COUNT(*)                                                AS total,
                COUNT(*) FILTER (WHERE improved = TRUE)                 AS improved_count,
                COUNT(*) FILTER (WHERE improved = FALSE)                AS failed_count,
                ROUND(AVG(parent_composite_score)::numeric, 2)          AS avg_parent_score,
                ROUND(AVG(child_composite_score)::numeric, 2)           AS avg_child_score,
                ROUND(AVG(score_delta)::numeric, 2)                     AS avg_score_delta,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE improved = TRUE)
                    / NULLIF(COUNT(*) FILTER (WHERE improved IS NOT NULL), 0),
                    1
                )                                                       AS conversion_rate_pct
            FROM mutation_memory
            GROUP BY mutation_type
            ORDER BY conversion_rate_pct DESC NULLS LAST, avg_score_delta DESC NULLS LAST
        """
        try:
            async with self.engine.connect() as conn:
                res = await conn.execute(text(query))
                rows = res.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "mutation_type":      r[0],
                        "total":              int(r[1]),
                        "improved":           int(r[2]),
                        "failed":             int(r[3]),
                        "avg_parent_score":   float(r[4]) if r[4] is not None else None,
                        "avg_child_score":    float(r[5]) if r[5] is not None else None,
                        "avg_score_delta":    float(r[6]) if r[6] is not None else None,
                        "conversion_rate":    float(r[7]) if r[7] is not None else None,
                    })
                return results
        except Exception as e:
            from loguru import logger
            logger.error(f"Error fetching mutation leaderboard: {e}")
            return []

    async def connect(self) -> None:
        """Verify the database connection and apply missing migrations."""
        async with self.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            # Auto-migration: ensure schema additions from schema.sql are applied
            # backtest_trades
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    strategy_id UUID NOT NULL,
                    symbol TEXT NOT NULL,
                    entry_time TIMESTAMPTZ,
                    exit_time TIMESTAMPTZ,
                    entry_price NUMERIC,
                    exit_price NUMERIC,
                    side TEXT,
                    pnl NUMERIC,
                    pnl_pct NUMERIC,
                    bars_held INT,
                    exit_reason TEXT
                )
            """)
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_backtest_trades_strategy ON backtest_trades (strategy_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_backtest_trades_entry ON backtest_trades (entry_time)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol ON backtest_trades (symbol)"
                )
            )
            # market_data_l1 new columns
            await conn.execute(
                text(
                    "ALTER TABLE market_data_l1 ADD COLUMN IF NOT EXISTS asset_class TEXT NOT NULL DEFAULT 'crypto'"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE market_data_l1 ADD COLUMN IF NOT EXISTS ingestion_time TIMESTAMPTZ DEFAULT NOW()"
                )
            )
            # strategies new columns
            await conn.execute(
                text("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS prompt TEXT")
            )
            await conn.execute(
                text(
                    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS raw_response TEXT"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS normalized_strategy JSONB"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS compile_error TEXT"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS strategy_signature TEXT"
                )
            )
            # features_wide materialized view — auto-migrate if schema outdated
            has_price_vs_vwap = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'features_wide' AND column_name = 'price_vs_vwap_pct'"
                )
            )
            if has_price_vs_vwap.fetchone() is None:
                await conn.execute(
                    text("DROP MATERIALIZED VIEW IF EXISTS features_wide CASCADE")
                )
                await conn.execute(
                    text("""
                    CREATE MATERIALIZED VIEW features_wide AS
                    SELECT
                        time,
                        symbol,
                        MAX(CASE WHEN feature_name='returns'               THEN value END) AS returns,
                        MAX(CASE WHEN feature_name='log_returns'           THEN value END) AS log_returns,
                        MAX(CASE WHEN feature_name='rsi_14'                THEN value END) AS rsi_14,
                        MAX(CASE WHEN feature_name='macd'                  THEN value END) AS macd,
                        MAX(CASE WHEN feature_name='macd_signal'           THEN value END) AS macd_signal,
                        MAX(CASE WHEN feature_name='vwap'                  THEN value END) AS vwap,
                        MAX(CASE WHEN feature_name='sma_5'                 THEN value END) AS sma_5,
                        MAX(CASE WHEN feature_name='sma_20'                THEN value END) AS sma_20,
                        MAX(CASE WHEN feature_name='ema_5'                 THEN value END) AS ema_5,
                        MAX(CASE WHEN feature_name='ema_12'                THEN value END) AS ema_12,
                        MAX(CASE WHEN feature_name='ema_26'                THEN value END) AS ema_26,
                        MAX(CASE WHEN feature_name='bollinger_lower'       THEN value END) AS bollinger_lower,
                        MAX(CASE WHEN feature_name='bollinger_upper'       THEN value END) AS bollinger_upper,
                        MAX(CASE WHEN feature_name='rolling_volatility'    THEN value END) AS rolling_volatility,
                        MAX(CASE WHEN feature_name='price_vs_vwap_pct'     THEN value END) AS price_vs_vwap_pct,
                        MAX(CASE WHEN feature_name='ema_spread_pct'        THEN value END) AS ema_spread_pct,
                        MAX(CASE WHEN feature_name='relative_volume'       THEN value END) AS relative_volume,
                        MAX(CASE WHEN feature_name='bollinger_band_position' THEN value END) AS bollinger_band_position,
                        MAX(CASE WHEN feature_name='volatility_regime'     THEN value END) AS volatility_regime,
                        MAX(CASE WHEN feature_name='trend_strength'        THEN value END) AS trend_strength
                    FROM features
                    GROUP BY time, symbol
                """)
                )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_features_wide_time_symbol ON features_wide (time, symbol)"
                )
            )
            # pattern_memory — PatternAgent storage
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS pattern_memory (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    archetype TEXT,
                    feature_family TEXT[],
                    asset_class TEXT,
                    timeframe TEXT,
                    regime TEXT,
                    composite_score_avg NUMERIC,
                    short_window_score_avg NUMERIC,
                    sharpe_avg NUMERIC,
                    win_rate_avg NUMERIC,
                    total_trades_avg NUMERIC,
                    cost_burden_avg NUMERIC,
                    sample_size INT DEFAULT 0,
                    confidence_score NUMERIC DEFAULT 0.0,
                    recommendation TEXT,
                    motif_details JSONB,
                    detected_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_pattern_memory_type ON pattern_memory (pattern_type)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_pattern_memory_archetype ON pattern_memory (archetype)"
                )
            )
            # lifecycle_events — Event Lineage Layer (Day 7b)
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    strategy_id TEXT,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    parent_event_id TEXT,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lifecycle_trace ON lifecycle_events (trace_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lifecycle_strategy ON lifecycle_events (strategy_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lifecycle_stage ON lifecycle_events (stage)"
                )
            )
            # trace_id column on strategies
            await conn.execute(
                text("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS trace_id TEXT")
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_strategies_trace ON strategies (trace_id)"
                )
            )

    async def _execute_insert(self, query: str, params: Dict[str, Any]) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(query), params)

    async def write_bars(self, symbol: str, data: BarData) -> None:
        """Insert to market_data_l1 (idempotent — skips duplicates)"""
        is_crypto = data.asset_class == "crypto"
        query = """
            INSERT INTO market_data_l1 (time, symbol, open, high, low, close, volume, source, interval, asset_class, ingestion_time)
            VALUES (:time, :symbol, :open, :high, :low, :close, :volume, :source, :interval, :asset_class, NOW())
            ON CONFLICT (time, symbol) DO NOTHING
        """
        params = data.model_dump()
        params["symbol"] = symbol
        params["open"] = _r4(params["open"])
        params["high"] = _r4(params["high"])
        params["low"] = _r4(params["low"])
        params["close"] = _r4(params["close"])
        params["volume"] = _r6(params["volume"]) if is_crypto else _r4(params["volume"])
        await self._execute_insert(query, params)

    async def write_quote(self, data: QuoteData) -> None:
        """Insert quote data to market_data_l2 as orderbook snapshot"""
        query = """
            INSERT INTO market_data_l2 (time, symbol, bids, asks, spread, mid_price)
            VALUES (:time, :symbol, :bids, :asks, :spread, :mid_price)
        """
        spread = _r6(data.ask - data.bid)
        mid_price = _r6((data.bid + data.ask) / 2)

        params = {
            "time": data.time,
            "symbol": data.symbol,
            "bids": json.dumps({str(_r6(data.bid)): data.bid_size}),
            "asks": json.dumps({str(_r6(data.ask)): data.ask_size}),
            "spread": spread,
            "mid_price": mid_price,
        }
        await self._execute_insert(query, params)

    async def write_trade(self, data: TradeData) -> None:
        """Insert trade data to order_flow table"""
        query = """
            INSERT INTO order_flow (time, symbol, price, size, side, aggressor)
            VALUES (:time, :symbol, :price, :size, :side, :aggressor)
        """
        params = {
            "time": data.time,
            "symbol": data.symbol,
            "price": _r6(data.price),
            "size": _r4(data.size),
            "side": data.side,
            "aggressor": data.exchange,
        }
        await self._execute_insert(query, params)

    async def write_aggregate(self, data: AggregateData) -> None:
        """Insert aggregate/OHLCV data to market_data_l1"""
        asset_class = "crypto" if data.source == "binance" else "equity"
        is_crypto = asset_class == "crypto"
        query = """
            INSERT INTO market_data_l1 (time, symbol, open, high, low, close, volume, source, interval, asset_class, ingestion_time)
            VALUES (:time, :symbol, :open, :high, :low, :close, :volume, :source, :interval, :asset_class, NOW())
        """
        params = {
            "time": data.time,
            "symbol": data.symbol,
            "open": _r4(data.open),
            "high": _r4(data.high),
            "low": _r4(data.low),
            "close": _r4(data.close),
            "volume": _r6(data.volume) if is_crypto else _r4(data.volume),
            "source": data.source,
            "interval": data.interval,
            "asset_class": asset_class,
        }
        await self._execute_insert(query, params)

    async def write_orderbook(self, symbol: str, data: OrderbookData) -> None:
        """Insert to market_data_l2"""
        query = """
            INSERT INTO market_data_l2 (time, symbol, bids, asks, spread, mid_price)
            VALUES (:time, :symbol, :bids, :asks, :spread, :mid_price)
        """
        params = data.model_dump()
        params["symbol"] = symbol
        params["bids"] = json.dumps(params["bids"])
        params["asks"] = json.dumps(params["asks"])
        params["spread"] = _r6(params["spread"])
        params["mid_price"] = _r6(params["mid_price"])
        await self._execute_insert(query, params)

    async def write_binance_trade(self, data: BinanceTradeData) -> None:
        """Insert Binance trade data to order_flow table"""
        query = """
            INSERT INTO order_flow (time, symbol, price, size, side, aggressor)
            VALUES (:time, :symbol, :price, :size, :side, :aggressor)
        """
        # Determine side: if buyer was maker, then buyer is passive (sell side pressure)
        # Otherwise buyer is aggressive (buy side pressure)
        side = "sell" if data.buyer_maker else "buy"

        params = {
            "time": data.time,
            "symbol": data.symbol,
            "price": _r6(data.price),
            "size": _r6(data.quantity),
            "side": side,
            "aggressor": str(data.trade_id),  # Use trade ID as aggressor identifier
        }
        await self._execute_insert(query, params)

    async def write_binance_depth(self, data: BinanceDepthData) -> None:
        """Insert Binance depth data to market_data_l2 as orderbook snapshot"""
        query = """
            INSERT INTO market_data_l2 (time, symbol, bids, asks, spread, mid_price)
            VALUES (:time, :symbol, :bids, :asks, :spread, :mid_price)
        """

        # Calculate spread and mid price from top level
        bids_list = sorted(
            [(float(price), float(qty)) for price, qty in data.bids.items()],
            key=lambda x: x[0],
            reverse=True,
        )
        asks_list = sorted(
            [(float(price), float(qty)) for price, qty in data.asks.items()],
            key=lambda x: x[0],
        )

        best_bid = bids_list[0][0] if bids_list else 0
        best_ask = asks_list[0][0] if asks_list else 0
        spread = _r6(best_ask - best_bid) if best_bid > 0 and best_ask > 0 else 0
        mid_price = (
            _r6((best_bid + best_ask) / 2) if best_bid > 0 and best_ask > 0 else 0
        )

        params = {
            "time": data.time,
            "symbol": data.symbol,
            "bids": json.dumps(data.bids),
            "asks": json.dumps(data.asks),
            "spread": spread,
            "mid_price": mid_price,
        }
        await self._execute_insert(query, params)

    async def write_features(
        self, symbol: str, features_dict: Dict[str, float]
    ) -> None:
        """Insert to features"""
        query = """
            INSERT INTO features (time, symbol, feature_name, value)
            VALUES (:time, :symbol, :feature_name, :value)
        """
        time_now = datetime.utcnow()
        ratio_features = {
            "returns",
            "log_returns",
            "price_vs_vwap_pct",
            "ema_spread_pct",
            "trend_strength",
        }
        async with self.engine.begin() as conn:
            for feature_name, value in features_dict.items():
                rnd = _r8 if feature_name in ratio_features else _r6
                params = {
                    "time": time_now,
                    "symbol": symbol,
                    "feature_name": feature_name,
                    "value": rnd(value),
                }
                await conn.execute(text(query), params)

    async def get_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str
    ) -> pd.DataFrame:
        """Returns DataFrame of market_data_l1"""
        query = """
            SELECT time, symbol, open, high, low, close, volume, source, interval
            FROM market_data_l1
            WHERE symbol = :symbol AND interval = :interval AND time >= :start AND time <= :end
            ORDER BY time ASC
        """
        params = {"symbol": symbol, "start": start, "end": end, "interval": interval}
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), params)
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(
                rows,
                columns=[
                    "time",
                    "symbol",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "source",
                    "interval",
                ],
            )
            return df

    async def fetch_recent_bars(self, symbol: str, limit: int = 5000) -> pd.DataFrame:
        query = """
            SELECT time, open, high, low, close, volume
            FROM market_data_l1
            WHERE symbol = :symbol
            ORDER BY time ASC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"symbol": symbol, "limit": limit})
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(
                rows, columns=["time", "open", "high", "low", "close", "volume"]
            )
            numeric_cols = ["open", "high", "low", "close", "volume"]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df.dropna()
            return df

    async def write_agent(self, agent_data: AgentData) -> None:
        """Upserts to agent_registry"""
        query = """
            INSERT INTO agent_registry (id, name, type, layer, status, pid, last_heartbeat, created_at, metadata)
            VALUES (:id, :name, :type, :layer, :status, :pid, :last_heartbeat, :created_at, :metadata)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                layer = EXCLUDED.layer,
                status = EXCLUDED.status,
                pid = EXCLUDED.pid,
                last_heartbeat = EXCLUDED.last_heartbeat,
                metadata = EXCLUDED.metadata
        """
        params = agent_data.model_dump()
        params["id"] = str(params["id"])  # ensure uuid string
        params["metadata"] = (
            json.dumps(params["metadata"]) if params["metadata"] else None
        )
        await self._execute_insert(query, params)

    async def log(
        self,
        agent_id: str,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inserts to system_logs"""
        query = """
            INSERT INTO system_logs (time, agent_id, level, message, metadata)
            VALUES (:time, :agent_id, :level, :message, :metadata)
        """
        params = {
            "time": datetime.utcnow(),
            "agent_id": str(agent_id),
            "level": level,
            "message": message,
            "metadata": json.dumps(metadata) if metadata else None,
        }
        await self._execute_insert(query, params)

    async def get_latest_features(self, symbols: list[str], limit: int = 5) -> dict:
        """Returns: {symbol: {feature_name: value}} for latest features per symbol"""
        query = """
            SELECT symbol, feature_name, value 
            FROM (
                SELECT symbol, feature_name, value,
                       ROW_NUMBER() OVER(PARTITION BY symbol, feature_name ORDER BY time DESC) as rn
                FROM features
                WHERE symbol = ANY(:symbols)
            ) sub
            WHERE rn = 1
        """
        result_dict = {sym: {} for sym in symbols}
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"symbols": symbols})
            rows = result.fetchall()
            for row in rows:
                result_dict[row[0]][row[1]] = float(row[2])
        return result_dict

    async def get_recent_backtest_results(self, limit: int = 5) -> list[dict]:
        """Returns: last N backtest results ordered by created_at DESC"""
        query = """
            SELECT b.strategy_id, b.start_date, b.end_date, b.sharpe, b.cagr, 
                   b.max_drawdown, b.win_rate, b.total_trades, b.passed_validation, b.results,
                   s.created_at
            FROM backtest_results b
            JOIN strategies s ON b.strategy_id = s.id
            ORDER BY s.created_at DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"limit": limit})
            rows = result.fetchall()
            out = []
            for r in rows:
                out.append(
                    {
                        "strategy_id": str(r[0]),
                        "start_date": r[1],
                        "end_date": r[2],
                        "sharpe": float(r[3]) if r[3] is not None else None,
                        "cagr": float(r[4]) if r[4] is not None else None,
                        "max_drawdown": float(r[5]) if r[5] is not None else None,
                        "win_rate": float(r[6]) if r[6] is not None else None,
                        "total_trades": int(r[7]) if r[7] is not None else None,
                        "passed_validation": bool(r[8]),
                        "results": r[9],
                        "created_at": r[10],
                    }
                )
            return out

    async def get_top_patterns(
        self,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> dict[str, list[dict]]:
        """Returns pattern intelligence grouped by type.
        Returns: {winning: [...], losing: [...], cost_traps: [...], neutral: [...]}
        """
        query = """
            SELECT pattern_type, archetype, feature_family, asset_class,
                   composite_score_avg, short_window_score_avg, sharpe_avg,
                   win_rate_avg, total_trades_avg, cost_burden_avg,
                   sample_size, confidence_score, recommendation, motif_details
            FROM pattern_memory
            WHERE confidence_score >= :min_conf
            ORDER BY composite_score_avg DESC
            LIMIT :lim
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(query), {"min_conf": min_confidence, "lim": limit}
            )
            rows = result.fetchall()

        grouped: dict[str, list[dict]] = {
            "winning": [],
            "losing": [],
            "cost_traps": [],
            "neutral": [],
        }
        for r in rows:
            motif = {
                "pattern_type": r[0],
                "archetype": r[1],
                "feature_family": r[2]
                if isinstance(r[2], list)
                else (list(r[2]) if r[2] else []),
                "asset_class": r[3],
                "composite_score_avg": float(r[4]) if r[4] is not None else 0,
                "short_window_score_avg": float(r[5]) if r[5] is not None else 0,
                "sharpe_avg": float(r[6]) if r[6] is not None else 0,
                "win_rate_avg": float(r[7]) if r[7] is not None else 0,
                "total_trades_avg": float(r[8]) if r[8] is not None else 0,
                "cost_burden_avg": float(r[9]) if r[9] is not None else 0,
                "sample_size": int(r[10]) if r[10] is not None else 0,
                "confidence_score": float(r[11]) if r[11] is not None else 0,
                "recommendation": r[12] or "",
                "motif_details": r[13] if isinstance(r[13], dict) else {},
            }
            ptype = r[0]
            if ptype == "winning_motif":
                grouped["winning"].append(motif)
            elif ptype == "losing_motif":
                grouped["losing"].append(motif)
            elif ptype == "cost_trap":
                grouped["cost_traps"].append(motif)
            else:
                grouped["neutral"].append(motif)

        return grouped

    async def get_recent_strategy_names(self, limit: int = 10) -> list[str]:
        """Returns: last N strategy names to avoid duplicates"""
        query = """
            SELECT name FROM strategies
            ORDER BY created_at DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"limit": limit})
            return [row[0] for row in result.fetchall()]

    async def get_strategy_signatures(self, limit: int = 100) -> set[str]:
        """Returns: set of recent strategy signatures for dedup."""
        query = """
            SELECT strategy_signature FROM strategies
            WHERE strategy_signature IS NOT NULL
            ORDER BY created_at DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"limit": limit})
            return {row[0] for row in result.fetchall() if row[0]}

    async def get_recent_feature_combos(
        self, limit: int = 50
    ) -> list[tuple[set[str], str]]:
        """Returns: list of (feature_set, archetype) from recent strategies."""
        query = """
            SELECT normalized_strategy FROM strategies
            WHERE normalized_strategy IS NOT NULL
            ORDER BY created_at DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"limit": limit})
            combos = []
            for row in result.fetchall():
                raw = row[0]
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        continue
                if not isinstance(raw, dict):
                    continue
                features = set()
                for key in ("entry_conditions", "exit_conditions"):
                    for cond in raw.get(key) or []:
                        if isinstance(cond, str):
                            for feat in re.findall(r"\b[a-z_][a-z_0-9]+\b", cond):
                                features.add(feat)
                archetype = (raw.get("tags") or ["unknown"])[0]
                if features:
                    combos.append((features, archetype))
            return combos

    async def save_strategy(
        self,
        spec: Any,
        status: str,
        author_agent: str,
        prompt: Optional[str] = None,
        raw_response: Optional[str] = None,
        strategy_signature: Optional[str] = None,
        generation_batch: Optional[str] = None,
    ) -> str:
        """Inserts to strategies table, returns strategy_id (uuid)."""
        import uuid

        # Defensive normalization
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except json.JSONDecodeError:
                raise ValueError(
                    f"save_strategy received non-JSON string: {spec[:200]}"
                )
        if isinstance(spec, tuple):
            spec = spec[0] if spec else {}
        if not isinstance(spec, dict):
            raise TypeError(
                f"save_strategy expected dict, got {type(spec).__name__}: {spec!r}"
            )

        strategy_name = spec.get("strategy_name") or spec.get("name")
        if not strategy_name:
            raise KeyError(
                f"Missing strategy_name in spec. Keys: {list(spec.keys())} | spec: {spec}"
            )

        strategy_id = str(uuid.uuid4())
        trace_id = uuid.uuid4().hex[:16]
        query = """
            INSERT INTO strategies (id, name, code, parameters, status, created_at, author_agent, prompt, raw_response, normalized_strategy, strategy_signature, trace_id, generation_batch)
            VALUES (:id, :name, :code, :parameters, :status, :created_at, :author_agent, :prompt, :raw_response, :normalized_strategy, :strategy_signature, :trace_id, :generation_batch)
        """
        params = {
            "id": strategy_id,
            "name": strategy_name,
            "code": "",
            "parameters": json.dumps(spec),
            "status": status,
            "created_at": datetime.utcnow(),
            "author_agent": author_agent,
            "prompt": prompt,
            "raw_response": raw_response,
            "normalized_strategy": json.dumps(spec),
            "strategy_signature": strategy_signature,
            "trace_id": trace_id,
            "generation_batch": generation_batch,
        }
        await self._execute_insert(query, params)

        # Log first lifecycle event
        try:
            from atlas.core.event_lineage import EventLineageClient

            lineage = EventLineageClient(self)
            await lineage.create_event(
                trace_id=trace_id,
                stage="ideator",
                status="completed",
                actor=author_agent,
                strategy_id=strategy_id,
                metadata={
                    "strategy_name": strategy_name,
                    "status": status,
                    "mode": spec.get("mode", "unknown"),
                },
            )
        except Exception as exc:
            logger.warning(f"Failed to log lifecycle event: {exc}")

        return strategy_id

    async def update_strategy_status(
        self, strategy_id: str, status: str, message: Optional[str] = None
    ) -> None:
        """Updates status in strategies table. Optional message is logged."""
        query = """
            UPDATE strategies
            SET status = :status
            WHERE id = :id
        """
        params = {"id": strategy_id, "status": status}
        await self._execute_insert(query, params)
        if message:
            await self.log(strategy_id, "INFO", message)

    async def update_strategy_code(
        self, strategy_id: str, code: str, status: str
    ) -> None:
        """Updates code + status in strategies table"""
        query = """
            UPDATE strategies 
            SET code = :code, status = :status
            WHERE id = :id
        """
        params = {"id": strategy_id, "code": code, "status": status}
        await self._execute_insert(query, params)

    async def get_backtest_result(self, strategy_id: str) -> dict | None:
        """Fetch latest backtest result for a strategy"""
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT *, results::jsonb as results_json
                    FROM backtest_results
                    WHERE strategy_id = :sid
                """),
                {"sid": str(strategy_id)},
            )
            row = result.fetchone()
            if not row:
                return None
            d = dict(row._mapping)
            # Merge results JSONB into top level for easy access
            if d.get("results_json"):
                try:
                    extra = (
                        json.loads(d["results_json"])
                        if isinstance(d["results_json"], str)
                        else d["results_json"]
                    )
                    d.update(extra)
                except:
                    pass
            return d

    async def update_strategy_status(
        self, strategy_id: str, status: str, notes: str = ""
    ) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE strategies
                    SET status = :status,
                        parameters = jsonb_set(
                            COALESCE(parameters::jsonb, '{}'::jsonb),
                            '{validation_notes}',
                            cast(:notes_json as jsonb)
                        )
                    WHERE id = :sid
                """),
                {
                    "status": status,
                    "notes_json": json.dumps(notes),
                    "sid": str(strategy_id),
                },
            )

    async def get_strategies_by_status(self, status: str) -> list[dict]:
        """Returns all strategies matching status"""
        query = """
            SELECT id, name, code, parameters, status, created_at, author_agent, trace_id
            FROM strategies
            WHERE status = :status
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"status": status})
            rows = result.fetchall()
            out = []
            for r in rows:
                out.append(
                    {
                        "id": str(r[0]),
                        "name": r[1],
                        "code": r[2],
                        "parameters": r[3]
                        if isinstance(r[3], dict)
                        else json.loads(r[3]),
                        "status": r[4],
                        "created_at": r[5],
                        "author_agent": r[6],
                        "trace_id": str(r[7]) if r[7] else None,
                    }
                )
            return out

    async def get_strategies_with_backtest(
        self, statuses: list[str] | None = None, limit: int = 10
    ) -> list[dict]:
        """Returns strategies with backtest results joined, ordered by short_window_score.
        Only queries verified top-level columns; profit_factor/composite_score/gross_edge/cost_burden
        are extracted from the results JSONB.
        Used by the ideator to learn from past failures and successes.
        Defaults to failed_validation + repair_candidate if no statuses given.
        """
        if statuses is None:
            statuses = ["failed_validation", "repair_candidate"]
        query = """
            SELECT s.id, s.name, s.code, s.parameters, s.status, s.created_at,
                   s.author_agent, b.total_trades,
                   b.max_drawdown, b.win_rate, b.short_window_score,
                   b.results
            FROM strategies s
            JOIN backtest_results b ON s.id = b.strategy_id
            WHERE s.status = ANY(:statuses)
            ORDER BY b.short_window_score DESC NULLS LAST
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(query), {"statuses": statuses, "limit": limit}
            )
            rows = result.fetchall()
            out = []
            for r in rows:
                params = r[3] if isinstance(r[3], dict) else json.loads(r[3])
                results_raw = r[11] if r[11] else {}
                results = (
                    json.loads(results_raw)
                    if isinstance(results_raw, str)
                    else (results_raw if isinstance(results_raw, dict) else {})
                )
                out.append(
                    {
                        "id": str(r[0]),
                        "name": r[1],
                        "code": r[2],
                        "parameters": params,
                        "status": r[4],
                        "created_at": r[5],
                        "author_agent": r[6],
                        "total_trades": r[7] or 0,
                        "max_drawdown": r[8] or 0,
                        "win_rate": r[9] or 0,
                        "short_window_score": r[10] or 0.0,
                        "profit_factor": float(results.get("profit_factor", 1.0)),
                        "composite_score": float(results.get("composite_score", 0.0)),
                        "gross_edge": float(results.get("gross_edge", 0.0)),
                        "cost_burden": float(results.get("cost_burden", 0.0)),
                    }
                )
            return out

    async def get_top_strategies_by_sharpe(
        self, min_sharpe: float, max_sharpe: float, limit: int
    ) -> list[dict]:
        """Returns validated strategies filtered by sharpe range"""
        query = """
            SELECT s.id, s.name, s.code, s.parameters, s.status, s.created_at, s.author_agent, b.sharpe
            FROM strategies s
            JOIN backtest_results b ON s.id = b.strategy_id
            WHERE s.status = 'validated' 
              AND b.sharpe >= :min_sharpe 
              AND b.sharpe <= :max_sharpe
            ORDER BY b.sharpe DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(query),
                {"min_sharpe": min_sharpe, "max_sharpe": max_sharpe, "limit": limit},
            )
            rows = result.fetchall()
            out = []
            for r in rows:
                out.append(
                    {
                        "id": str(r[0]),
                        "name": r[1],
                        "code": r[2],
                        "parameters": r[3]
                        if isinstance(r[3], dict)
                        else json.loads(r[3]),
                        "status": r[4],
                        "created_at": r[5],
                        "sharpe": float(r[7]),
                    }
                )
            return out

    async def get_top_strategies_by_composite_score(
        self, min_score: float, max_score: float, limit: int
    ) -> list[dict]:
        """Returns strategies sorted by short_window_score (temporal fitness).
        Includes pending_validation and benchmark strategies that have been backtested.
        """
        query = """
            SELECT s.id, s.name, s.code, s.parameters, s.status, s.created_at,
                   s.author_agent, b.short_window_score
            FROM strategies s
            JOIN backtest_results b ON s.id = b.strategy_id
            WHERE b.short_window_score IS NOT NULL
              AND b.short_window_score >= :min_score
              AND b.short_window_score <= :max_score
              AND s.status IN ('pending_validation', 'benchmark')
            ORDER BY b.short_window_score DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(query),
                {"min_score": min_score, "max_score": max_score, "limit": limit},
            )
            rows = result.fetchall()
            out = []
            for r in rows:
                out.append(
                    {
                        "id": str(r[0]),
                        "name": r[1],
                        "code": r[2],
                        "parameters": r[3]
                        if isinstance(r[3], dict)
                        else json.loads(r[3]),
                        "status": r[4],
                        "created_at": r[5],
                        "short_window_score": float(r[7]) if r[7] is not None else 0.0,
                    }
                )
            return out

    async def check_combination_exists(self, parent_a: str, parent_b: str) -> bool:
        """Check if a combination of these two parents already exists (unordered)."""
        query = """
            SELECT 1 FROM combination_memory
            WHERE (parent_a = :a AND parent_b = :b)
               OR (parent_a = :b AND parent_b = :a)
            LIMIT 1
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"a": parent_a, "b": parent_b})
            return result.fetchone() is not None

    async def save_combination_record(
        self,
        parent_a: str,
        parent_b: str,
        child_id: str,
        combination_type: str = "claude_hybrid",
        parent_a_score: float = 0.0,
        parent_b_score: float = 0.0,
        child_score: float = 0.0,
    ) -> None:
        """Record a combination in combination_memory with score delta."""
        # Normalize ordering to avoid (a,b) vs (b,a) duplicates
        if parent_a > parent_b:
            parent_a, parent_b = parent_b, parent_a
            parent_a_score, parent_b_score = parent_b_score, parent_a_score
        query = """
            INSERT INTO combination_memory
                (parent_a, parent_b, child_id, combination_type,
                 parent_a_sharpe, parent_b_sharpe, child_sharpe, sharpe_delta)
            VALUES
                (:parent_a, :parent_b, :child_id, :combination_type,
                 :parent_a_score, :parent_b_score, :child_score, :sharpe_delta)
            ON CONFLICT (parent_a, parent_b, combination_type) DO NOTHING
        """
        params = {
            "parent_a": parent_a,
            "parent_b": parent_b,
            "child_id": child_id,
            "combination_type": combination_type,
            "parent_a_score": parent_a_score,
            "parent_b_score": parent_b_score,
            "child_score": child_score,
            "sharpe_delta": child_score - max(parent_a_score, parent_b_score),
        }
        await self._execute_insert(query, params)

    async def save_backtest_results(
        self, strategy_id: str, results: dict, start_date: str, end_date: str
    ) -> None:
        """Saves backtest results including short_window temporal scores"""
        query = """
            INSERT INTO backtest_results (strategy_id, start_date, end_date, sharpe, cagr, max_drawdown, win_rate, total_trades, passed_validation, results, entry_count, exit_count, bars_processed, short_window_score, score_7d, score_14d, score_30d)
            VALUES (:strategy_id, :start_date, :end_date, :sharpe, :cagr, :max_drawdown, :win_rate, :total_trades, :passed_validation, :results, :entry_count, :exit_count, :bars_processed, :short_window_score, :score_7d, :score_14d, :score_30d)
            ON CONFLICT (strategy_id, start_date, end_date) DO UPDATE SET
                sharpe = EXCLUDED.sharpe,
                cagr = EXCLUDED.cagr,
                max_drawdown = EXCLUDED.max_drawdown,
                win_rate = EXCLUDED.win_rate,
                total_trades = EXCLUDED.total_trades,
                passed_validation = EXCLUDED.passed_validation,
                results = EXCLUDED.results,
                entry_count = EXCLUDED.entry_count,
                exit_count = EXCLUDED.exit_count,
                bars_processed = EXCLUDED.bars_processed,
                short_window_score = EXCLUDED.short_window_score,
                score_7d = EXCLUDED.score_7d,
                score_14d = EXCLUDED.score_14d,
                score_30d = EXCLUDED.score_30d
        """
        params = {
            "strategy_id": strategy_id,
            "start_date": datetime.fromisoformat(start_date)
            if isinstance(start_date, str)
            else start_date,
            "end_date": datetime.fromisoformat(end_date)
            if isinstance(end_date, str)
            else end_date,
            "sharpe": results.get("holdout_sharpe", results.get("sharpe_ratio", 0.0)),
            "cagr": results.get("cagr", 0.0),
            "max_drawdown": results.get("max_drawdown", 0.0),
            "win_rate": results.get("win_rate", 0.0),
            "total_trades": results.get("total_trades", 0),
            "passed_validation": results.get("passed_validation", False),
            "results": json.dumps(results),
            "entry_count": results.get("entry_count", 0),
            "exit_count": results.get("exit_count", 0),
            "bars_processed": results.get("bars_processed", 0),
            "short_window_score": results.get("short_window_score"),
            "score_7d": results.get("score_7d"),
            "score_14d": results.get("score_14d"),
            "score_30d": results.get("score_30d"),
        }
        await self._execute_insert(query, params)

    async def get_open_paper_trades(self) -> list[dict]:
        query = "SELECT * FROM paper_trades WHERE status = 'open'"
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            cols = result.keys()
            return [dict(zip(cols, row)) for row in rows]

    async def get_daily_pnl(self) -> float:
        query = (
            "SELECT SUM(pnl) FROM paper_trades WHERE time >= NOW() - INTERVAL '1 day'"
        )
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query))
            val = result.scalar()
            return float(val) if val else 0.0

    async def get_weekly_pnl(self) -> float:
        query = (
            "SELECT SUM(pnl) FROM paper_trades WHERE time >= NOW() - INTERVAL '7 days'"
        )
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query))
            val = result.scalar()
            return float(val) if val else 0.0

    async def get_agent_metadata(self, name: str) -> dict:
        query = "SELECT metadata FROM agent_registry WHERE name = :name"
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"name": name})
            val = result.scalar()
            return val if val else {}

    async def update_agent_metadata_active(self, name: str, active: bool) -> None:
        # Simplistic approach to handle jsonb update since we don't have jsonb_set working cleanly in all mock cases.
        # We will fetch, update, and save.
        meta = await self.get_agent_metadata(name)
        if not meta:
            meta = {}
        meta["active"] = active
        query = "UPDATE agent_registry SET metadata = :meta WHERE name = :name"
        params = {"meta": json.dumps(meta), "name": name}
        await self._execute_insert(query, params)

    async def save_paper_trade(self, trade: dict) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                INSERT INTO paper_trades
                (time, strategy_id, symbol, side, quantity, price, fill_price, status, pnl)
                VALUES (NOW(), :strategy_id, :symbol, :side, :quantity,
                        :price, :fill_price, :status, :pnl)
                ON CONFLICT DO NOTHING
            """
                ),
                trade,
            )

    async def save_backtest_trade(self, strategy_id: str, trade: dict) -> None:
        """Insert a single backtest trade into backtest_trades"""
        query = """
            INSERT INTO backtest_trades (strategy_id, symbol, entry_time, exit_time, entry_price, exit_price, side, pnl, pnl_pct, bars_held, exit_reason)
            VALUES (:strategy_id, :symbol, :entry_time, :exit_time, :entry_price, :exit_price, :side, :pnl, :pnl_pct, :bars_held, :exit_reason)
        """
        params = {
            "strategy_id": strategy_id,
            "symbol": trade.get("symbol", ""),
            "entry_time": trade.get("entry_time"),
            "exit_time": trade.get("exit_time"),
            "entry_price": trade.get("entry_price"),
            "exit_price": trade.get("exit_price"),
            "side": trade.get("side"),
            "pnl": trade.get("pnl"),
            "pnl_pct": trade.get("pnl_pct"),
            "bars_held": trade.get("bars_held", 0),
            "exit_reason": trade.get("exit_reason", "signal"),
        }
        await self._execute_insert(query, params)

    async def update_strategy_fields(self, strategy_id: str, **kwargs) -> None:
        """Generic update for arbitrary strategy columns. Usage:
        await db.update_strategy_fields(sid, compile_error="...", normalized_strategy={...})
        """
        if not kwargs:
            return
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        params = {"id": strategy_id, **kwargs}
        query = f"UPDATE strategies SET {sets} WHERE id = :id"
        await self._execute_insert(query, params)

    async def get_paper_trades_for_strategy(self, strategy_id: str) -> list:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM paper_trades WHERE strategy_id=:sid"),
                {"sid": str(strategy_id)},
            )
            return [dict(r._mapping) for r in result.fetchall()]

    async def get_repair_candidates(self, limit: int = 10) -> list[dict]:
        """
        Fetch strategies suitable for mutation repair.
        Targets: failed_validation with entries + trades, research_candidate, validated_B.
        """
        query = """
            SELECT s.id, s.name, s.code, s.parameters, s.normalized_strategy,
                   s.status, s.created_at, s.author_agent,
                   b.sharpe, b.entry_count, b.total_trades, b.max_drawdown,
                   b.win_rate, b.results
            FROM strategies s
            JOIN backtest_results b ON s.id = b.strategy_id
            WHERE (
                (s.status = 'failed_validation' AND b.entry_count > 0 AND b.total_trades >= 3)
                OR s.status IN ('repair_candidate', 'research_candidate')
            )
            ORDER BY
                CASE s.status
                    WHEN 'research_candidate' THEN 1
                    WHEN 'repair_candidate' THEN 2
                    ELSE 3
                END,
                b.sharpe DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), {"limit": limit})
            rows = result.fetchall()
            import decimal

            out = []
            for r in rows:
                d = dict(r._mapping)
                # Convert Decimal values to native float/int for JSON safety
                for k, v in d.items():
                    if isinstance(v, decimal.Decimal):
                        d[k] = float(v) if "." in str(v) else int(v)
                if isinstance(d.get("parameters"), str):
                    d["parameters"] = json.loads(d["parameters"])
                if isinstance(d.get("normalized_strategy"), str):
                    d["normalized_strategy"] = json.loads(d["normalized_strategy"])
                # Merge results JSONB for diagnostics
                results_raw = d.get("results")
                if isinstance(results_raw, dict):
                    d.update(results_raw)
                out.append(d)
            return out

    async def save_mutation_record(
        self,
        parent_id: str,
        child_id: str,
        mutation_type: str,
        changed_fields: list[str],
        parent_metrics: dict,
        child_metrics: dict,
    ) -> None:
        """Record a parent-child mutation lineage."""
        query = """
            INSERT INTO mutation_memory
                (parent_strategy_id, child_strategy_id, mutation_type, changed_fields,
                 parent_sharpe, child_sharpe, sharpe_delta,
                 parent_entry_count, child_entry_count,
                 parent_trades, child_trades,
                 parent_composite_score, child_composite_score,
                 score_delta, improved)
            VALUES
                (:parent_id, :child_id, :mutation_type, :changed_fields,
                 :parent_sharpe, :child_sharpe, :sharpe_delta,
                 :parent_entry_count, :child_entry_count,
                 :parent_trades, :child_trades,
                 :parent_composite_score, :child_composite_score,
                 :score_delta, :improved)
        """
        p_sharpe = float(
            parent_metrics.get("sharpe", parent_metrics.get("holdout_sharpe", 0))
        )
        c_sharpe = float(
            child_metrics.get("sharpe", child_metrics.get("holdout_sharpe", 0))
        )
        import json
        if isinstance(changed_fields, (dict, list)):
            changed_fields = json.dumps(changed_fields)

        p_composite = parent_metrics.get("composite_score") or parent_metrics.get("composite_score_avg")
        c_composite = child_metrics.get("composite_score") or child_metrics.get("composite_score_avg")
        p_composite = float(p_composite) if p_composite is not None else None
        c_composite = float(c_composite) if c_composite is not None else None
        score_delta = (c_composite - p_composite) if (p_composite is not None and c_composite is not None) else None
        improved = (score_delta > 0) if score_delta is not None else None

        params = {
            "parent_id": parent_id,
            "child_id": child_id,
            "mutation_type": mutation_type,
            "changed_fields": changed_fields,
            "parent_sharpe": p_sharpe,
            "child_sharpe": c_sharpe,
            "sharpe_delta": c_sharpe - p_sharpe,
            "parent_entry_count": int(parent_metrics.get("entry_count", 0)),
            "child_entry_count": int(child_metrics.get("entry_count", 0)),
            "parent_trades": int(parent_metrics.get("total_trades", 0)),
            "child_trades": int(child_metrics.get("total_trades", 0)),
            "parent_composite_score": p_composite,
            "child_composite_score": c_composite,
            "score_delta": score_delta,
            "improved": improved,
        }
        await self._execute_insert(query, params)

    async def get_mutation_history(
        self, strategy_id: str, max_depth: int = 3
    ) -> list[dict]:
        """Fetch mutation lineage for a strategy (both as parent and child)."""
        query = """
            SELECT * FROM mutation_memory
            WHERE parent_strategy_id = :sid OR child_strategy_id = :sid
            ORDER BY created_at DESC
            LIMIT :limit
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(
                text(query), {"sid": strategy_id, "limit": max_depth * 2}
            )
            return [dict(r._mapping) for r in result.fetchall()]
