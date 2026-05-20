"""
test_internal_scout_network.py — Phase 10 Scout Network Independent Validation.

Tests each scout in isolation with mocked DB and Redis dependencies:

1. RegimeScout  → classifies at least 1 symbol with synthetic OHLCV data
2. LiquidityScout → falls back to volume heuristic when L2 data unavailable
3. CorrelationScout → computes pairwise correlation with 2+ symbols
4. ExecutionScout → handles empty execution log gracefully (no crash)
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pandas as pd
import numpy as np

from atlas.core.agent_base import BaseAgent
from atlas.core.scout_contracts.scout_contract import (
    RegimePayload,
    LiquidityPayload,
    CorrelationPayload,
    ExecutionPayload,
    scout_summary_for_ideator,
)


# ============================================================================
# Fixtures — shared mock infrastructure
# ============================================================================

@pytest.fixture
def mock_redis():
    """Standard Redis mock with pub/sub support."""
    redis = AsyncMock()
    redis.publish = AsyncMock()
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def mock_db():
    """Standard DB client mock with async engine."""
    db = AsyncMock()
    db._execute_insert = AsyncMock()
    db.fetch_recent_bars = AsyncMock()
    return db


@pytest.fixture
def mock_db_engine(mock_db):
    """
    Extended DB mock that sets up a mock engine.connect() context manager.
    Needed for scouts that query DB directly (LiquidityScout L2, ExecutionScout paper_trades).
    """
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone = MagicMock(return_value=None)   # default: no rows
    mock_result.fetchall = MagicMock(return_value=[])      # default: empty rows
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_db.engine = mock_engine
    return mock_db, mock_conn, mock_result


# ============================================================================
# Synthetic data generators
# ============================================================================

def make_synthetic_bars(
    n_bars: int = 200,
    base_price: float = 100.0,
    vol: float = 1.0,
    trend: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Create a realistic OHLCV DataFrame with controlled volatility and trend.

    Parameters:
        n_bars: Number of bars to generate
        base_price: Starting price
        vol: Daily volatility (std of log returns)
        trend: Trend drift per bar (positive = up, negative = down)
        seed: Random seed for reproducibility
    """
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(trend, vol, n_bars)
    prices = base_price * np.exp(np.cumsum(log_returns))
    prices = np.maximum(prices, base_price * 0.1)  # floor at 10% of base

    ohlc = np.column_stack([
        prices * (1 + rng.uniform(-0.005, 0.005, n_bars)),  # open
        prices * (1 + rng.uniform(0.002, 0.015, n_bars)),   # high
        prices * (1 + rng.uniform(-0.015, -0.002, n_bars)), # low
        prices,                                               # close
    ])
    ohlc = np.maximum(ohlc, base_price * 0.01)  # apply floor to all

    volumes = rng.uniform(1000, 10000, n_bars)
    times = [datetime.now(timezone.utc) - timedelta(minutes=n_bars - i)
             for i in range(n_bars)]

    df = pd.DataFrame({
        "time": times,
        "open": ohlc[:, 0],
        "high": ohlc[:, 1],
        "low": ohlc[:, 2],
        "close": ohlc[:, 3],
        "volume": volumes,
    })
    return df


# ============================================================================
# Test 1: RegimeScout — classifies at least 1 symbol
# ============================================================================

@pytest.mark.asyncio
async def test_regime_scout_classifies_one_symbol(mock_redis, mock_db):
    """RegimeScout must produce a valid classification payload for 1+ symbols."""
    from atlas.agents.scouts.regime_scout import RegimeScout

    # --- Arrange: synthetic data with clear uptrend + moderate volatility ---
    df = make_synthetic_bars(n_bars=200, base_price=100.0, vol=0.008, trend=0.002, seed=1)
    mock_db.fetch_recent_bars.return_value = df

    scout = RegimeScout(redis_client=mock_redis, db_client=mock_db, symbols=["BTCUSDT", "ETHUSDT"])

    # --- Act: analyze one symbol ---
    payload = await scout._analyze_symbol("BTCUSDT")

    # --- Assert ---
    assert payload is not None, "RegimeScout returned None for valid data"
    assert isinstance(payload, RegimePayload), f"Expected RegimePayload, got {type(payload)}"
    assert payload.symbol == "BTCUSDT"
    assert payload.volatility_regime in ("low_vol", "normal_vol", "high_vol", "panic_vol"), \
        f"Unexpected volatility_regime: {payload.volatility_regime}"
    assert payload.trend_regime in ("trending_up", "trending_down", "mean_reverting", "choppy"), \
        f"Unexpected trend_regime: {payload.trend_regime}"
    assert payload.liquidity_regime in ("deep_liquid", "normal", "thin", "dangerous"), \
        f"Unexpected liquidity_regime: {payload.liquidity_regime}"
    assert payload.correlation_regime in ("diversified", "clustered", "panic_correlation"), \
        f"Unexpected correlation_regime: {payload.correlation_regime}"
    assert payload.confidence_score > 0, "confidence_score should be > 0 for 200 bars"
    assert isinstance(payload.atr_percentile, float)
    assert isinstance(payload.realized_volatility, float)
    assert isinstance(payload.relative_volume, float)

    # --- Verify DB persistence was called ---
    mock_db._execute_insert.assert_called_once()
    insert_query = mock_db._execute_insert.call_args[0][0]
    assert "INSERT INTO market_regime_memory" in insert_query, \
        "RegimeScout did not persist to market_regime_memory"

    # --- Verify Redis publication ---
    mock_redis.publish.assert_called_once()
    published_channel = mock_redis.publish.call_args[0][0]
    assert published_channel == "scout:regime", \
        f"Expected scout:regime channel, got {published_channel}"


# ============================================================================
# Test 2: LiquidityScout — falls back to volume heuristic gracefully
# ============================================================================

@pytest.mark.asyncio
async def test_liquidity_scout_falls_back_to_volume_heuristic(mock_redis, mock_db_engine):
    """
    When L2 orderbook data is unavailable, LiquidityScout must gracefully
    fall back to volume-based liquidity estimation without crashing.
    """
    from atlas.agents.scouts.liquidity_scout import LiquidityScout

    mock_db, mock_conn, mock_result = mock_db_engine

    # --- Arrange: make L2 query return no data ---
    mock_result.fetchone.return_value = None

    # --- Arrange: volume data for fallback ---
    df = make_synthetic_bars(n_bars=100, base_price=50000.0, vol=0.01, trend=0.0, seed=2)
    mock_db.fetch_recent_bars.return_value = df

    scout = LiquidityScout(redis_client=mock_redis, db_client=mock_db, symbols=["BTCUSDT"])

    # --- Act ---
    payload = await scout._analyze_liquidity("BTCUSDT")

    # --- Assert: payload exists and uses volume heuristic ---
    assert payload is not None, "LiquidityScout returned None on volume fallback"
    assert isinstance(payload, LiquidityPayload), f"Expected LiquidityPayload, got {type(payload)}"
    assert payload.symbol == "BTCUSDT"
    assert payload.liquidity_regime in ("excellent", "stable", "thin", "dangerous"), \
        f"Unexpected liquidity_regime: {payload.liquidity_regime}"
    assert 0 <= payload.liquidity_score <= 100, \
        f"liquidity_score out of range: {payload.liquidity_score}"
    assert 0 <= payload.slippage_risk <= 1, \
        f"slippage_risk out of range: {payload.slippage_risk}"
    assert payload.metadata.get("method") == "volume_heuristic", \
        f"Expected volume_heuristic method, got {payload.metadata.get('method')}"

    # --- Verify the L2 query was attempted ---
    l2_query_calls = [
        call for call in mock_conn.execute.call_args_list
        if "FROM market_data_l2" in str(call[0][0])
    ]
    assert len(l2_query_calls) >= 1, "LiquidityScout did not try L2 query"

    # --- Verify DB persistence ---
    insert_calls = [
        call for call in mock_db._execute_insert.call_args_list
        if "INSERT INTO liquidity_intelligence" in str(call[0][0])
    ]
    assert len(insert_calls) >= 1, "LiquidityScout did not persist to liquidity_intelligence"

    # --- Verify Redis publication ---
    pub_calls = [
        call for call in mock_redis.publish.call_args_list
        if call[0][0] == "scout:liquidity"
    ]
    assert len(pub_calls) >= 1, "LiquidityScout did not publish to scout:liquidity"


# ============================================================================
# Test 3: CorrelationScout — computes pairwise correlation with 2+ symbols
# ============================================================================

@pytest.mark.asyncio
async def test_correlation_scout_computes_pairwise_corr(mock_redis, mock_db):
    """CorrelationScout must compute pairwise correlation when 2+ symbols have data."""
    from atlas.agents.scouts.correlation_scout import CorrelationScout

    # --- Arrange: create correlated data for 3 symbols ---
    rng = np.random.default_rng(42)
    n_bars = 100
    common_factor = rng.normal(0, 0.005, n_bars)  # shared return component

    def make_correlated_bars(symbol: str, beta: float, noise_scale: float, seed_offset: int) -> pd.DataFrame:
        rng_local = np.random.default_rng(seed=42 + seed_offset)
        noise = rng_local.normal(0, noise_scale, n_bars)
        log_ret = beta * common_factor + noise
        prices = 100.0 * np.exp(np.cumsum(log_ret))
        prices = np.maximum(prices, 1.0)

        times = [datetime.now(timezone.utc) - timedelta(minutes=n_bars - i)
                 for i in range(n_bars)]
        return pd.DataFrame({
            "time": times,
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": rng_local.uniform(1000, 10000, n_bars),
        })

    # Symbol 1 & 2: highly correlated (same beta, low noise)
    df1 = make_correlated_bars("BTCUSDT", beta=1.0, noise_scale=0.002, seed_offset=0)
    df2 = make_correlated_bars("ETHUSDT", beta=0.9, noise_scale=0.003, seed_offset=1)
    df3 = make_correlated_bars("SOLUSDT", beta=0.3, noise_scale=0.010, seed_offset=2)  # lower corr

    # Mock fetch_recent_bars to return per-symbol data
    async def mock_fetch_bars(symbol: str, limit: int = 5000):
        mapping = {"BTCUSDT": df1, "ETHUSDT": df2, "SOLUSDT": df3}
        return mapping.get(symbol, pd.DataFrame())

    mock_db.fetch_recent_bars = AsyncMock(side_effect=mock_fetch_bars)

    scout = CorrelationScout(
        redis_client=mock_redis,
        db_client=mock_db,
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    )

    # --- Act ---
    payload = await scout._analyze_correlations()

    # --- Assert: correlation computed correctly ---
    assert payload is not None, "CorrelationScout returned None with 3 symbols"
    assert isinstance(payload, CorrelationPayload), f"Expected CorrelationPayload, got {type(payload)}"
    assert len(payload.symbols_analyzed) >= 2, \
        f"Expected >= 2 symbols analyzed, got {payload.symbols_analyzed}"
    assert payload.avg_pairwise_corr >= -1.0 and payload.avg_pairwise_corr <= 1.0, \
        f"avg_pairwise_corr out of range: {payload.avg_pairwise_corr}"
    assert payload.risk_state in ("diversified", "clustered", "panic_correlation", "regime_break"), \
        f"Unexpected risk_state: {payload.risk_state}"
    assert payload.cluster_name is not None and len(payload.cluster_name) > 0
    assert payload.dominant_factor is not None and len(payload.dominant_factor) > 0
    assert isinstance(payload.top_correlated_pairs, dict)
    assert len(payload.top_correlated_pairs) >= 1, \
        "Expected at least 1 correlated pair"

    # Note: _analyze_correlations() does NOT call _persist/_publish internally.
    # Persistence is done in run(). So we verify the payload is correct here.
    # DB persistence is tested implicitly via test_execution_scout_computes_quality
    # which exercises the full _analyze_broker -> _persist -> _publish flow.


# ============================================================================
# Test 4: ExecutionScout — handles empty execution log gracefully
# ============================================================================

@pytest.mark.asyncio
async def test_execution_scout_handles_empty_execution_log(mock_redis, mock_db_engine):
    """
    When there are no execution records (empty paper_trades),
    ExecutionScout must not crash and must handle gracefully.
    """
    from atlas.agents.scouts.execution_scout import ExecutionScout

    mock_db, mock_conn, mock_result = mock_db_engine

    # --- Arrange: empty execution log ---
    mock_result.fetchall.return_value = []  # no paper_trades rows

    scout = ExecutionScout(
        redis_client=mock_redis,
        db_client=mock_db,
        brokers=["simulator"],
    )

    # --- Act: should not raise any exception ---
    try:
        await scout._analyze_broker("simulator")
    except Exception as e:
        pytest.fail(f"ExecutionScout raised an exception on empty log: {e}")

    # --- Assert: no persistence or publication (no data to publish) ---
    # However, _execute_insert should not have been called for execution_intelligence
    insert_calls = [
        call for call in mock_db._execute_insert.call_args_list
        if "INSERT INTO execution_intelligence" in str(call[0][0])
    ]
    assert len(insert_calls) == 0, \
        "ExecutionScout should not persist when there is no execution data"

    # --- Verify the paper_trades query was attempted ---
    paper_trade_calls = [
        call for call in mock_conn.execute.call_args_list
        if "FROM paper_trades" in str(call[0][0])
    ]
    assert len(paper_trade_calls) >= 1, \
        "ExecutionScout did not attempt paper_trades query"

    # --- Verify graceful handling: latest_payload remains empty ---
    assert len(scout._latest_payload) == 0, \
        "ExecutionScout should not cache payload when no data"

    # --- Verify worst-case retrieval returns None gracefully ---
    latest = scout.get_latest()
    assert latest is None, \
        "get_latest() should return None when no execution data exists"


# ============================================================================
# Test 5: Scout contract helpers
# ============================================================================

def test_scout_summary_for_ideator():
    """Verify scout_summary_for_ideator builds correct summary strings."""
    # --- With regime data ---
    regime = RegimePayload(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        volatility_regime="high_vol",
        trend_regime="trending_up",
        liquidity_regime="thin",
        confidence_score=0.85,
    )
    summary = scout_summary_for_ideator(regime=regime)
    assert "vol=high_vol" in summary
    assert "trend=trending_up" in summary
    assert "liq=thin" in summary
    assert "conf=85%" in summary

    # --- With liquidity data ---
    liquidity = LiquidityPayload(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        liquidity_regime="thin",
        liquidity_score=45.0,
        slippage_risk=0.7,
    )
    summary = scout_summary_for_ideator(liquidity=liquidity)
    assert "regime=thin" in summary
    assert "score=45" in summary
    assert "risk=0.7" in summary

    # --- With all scouts ---
    full_summary = scout_summary_for_ideator(
        regime=regime,
        liquidity=liquidity,
        correlation=CorrelationPayload(
            timestamp=datetime.now(timezone.utc),
            cluster_name="crypto_majors",
            avg_pairwise_corr=0.75,
            risk_state="clustered",
        ),
        execution=ExecutionPayload(
            symbol="BTCUSDT",
            broker="simulator",
            timestamp=datetime.now(timezone.utc),
            execution_regime="optimal",
            fill_quality_score=92.0,
            avg_slippage_bps=1.5,
            sample_size=50,
        ),
    )
    assert "vol=high_vol" in full_summary
    assert "Liquidity" in full_summary
    assert "Correlation" in full_summary
    assert "Execution" in full_summary
    assert "fill_score=92" in full_summary

    # --- With no data ---
    empty = scout_summary_for_ideator()
    assert empty == "Scout intelligence unavailable."


# ============================================================================
# Test 6: All scout payloads serialize to dict correctly
# ============================================================================

def test_scout_payload_to_dict():
    """Every scout payload must produce a valid to_dict() with type field."""
    now = datetime.now(timezone.utc)

    regime = RegimePayload(symbol="BTCUSDT", timestamp=now)
    rd = regime.to_dict()
    assert rd["type"] == "regime_intelligence"
    assert rd["symbol"] == "BTCUSDT"
    assert "timestamp" in rd

    liquidity = LiquidityPayload(symbol="BTCUSDT", timestamp=now)
    ld = liquidity.to_dict()
    assert ld["type"] == "liquidity_intelligence"
    assert ld["symbol"] == "BTCUSDT"

    correlation = CorrelationPayload(timestamp=now)
    cd = correlation.to_dict()
    assert cd["type"] == "correlation_intelligence"

    execution = ExecutionPayload(symbol="BTCUSDT", broker="simulator", timestamp=now)
    ed = execution.to_dict()
    assert ed["type"] == "execution_intelligence"
    assert ed["broker"] == "simulator"


# ============================================================================
# Test 7: RegimeScout handles missing data gracefully
# ============================================================================

@pytest.mark.asyncio
async def test_regime_scout_handles_missing_data(mock_redis, mock_db):
    """RegimeScout must not crash when fetch_recent_bars returns empty DataFrame."""
    from atlas.agents.scouts.regime_scout import RegimeScout

    # Empty DataFrame
    mock_db.fetch_recent_bars.return_value = pd.DataFrame()

    scout = RegimeScout(redis_client=mock_redis, db_client=mock_db, symbols=["BTCUSDT"])

    payload = await scout._analyze_symbol("BTCUSDT")
    assert payload is None, "RegimeScout should return None for empty data"


# ============================================================================
# Test 8: LiquidityScout handles missing data gracefully
# ============================================================================

@pytest.mark.asyncio
async def test_liquidity_scout_handles_missing_data(mock_redis, mock_db_engine):
    """LiquidityScout must return None when insufficient bars for volume fallback."""
    from atlas.agents.scouts.liquidity_scout import LiquidityScout

    mock_db, mock_conn, mock_result = mock_db_engine

    # Too few bars (less than 20)
    df = make_synthetic_bars(n_bars=10, seed=3)
    mock_db.fetch_recent_bars.return_value = df

    scout = LiquidityScout(redis_client=mock_redis, db_client=mock_db, symbols=["BTCUSDT"])

    payload = await scout._analyze_liquidity("BTCUSDT")
    assert payload is None, "LiquidityScout should return None for insufficient bars"


# ============================================================================
# Test 9: ExecutionScout computes quality from valid data
# ============================================================================

@pytest.mark.asyncio
async def test_execution_scout_computes_quality(mock_redis, mock_db_engine):
    """ExecutionScout must compute fill_quality_score from execution records."""
    from atlas.agents.scouts.execution_scout import ExecutionScout

    mock_db, mock_conn, mock_result = mock_db_engine

    # --- Arrange: 10 paper trade records ---
    now = datetime.now(timezone.utc)
    execs = []
    for i in range(10):
        execs.append({
            "time": now - timedelta(minutes=i),
            "symbol": "BTCUSDT",
            "side": "buy" if i % 2 == 0 else "sell",
            "quantity": 0.1,
            "price": 50000.0 + i * 10,
            "fill_price": 50000.0 + i * 10 + 2.0,  # slight positive slippage
            "status": "filled",
            "pnl": 5.0 if i % 2 == 1 else 0.0,
        })
    mock_result.fetchall.return_value = [tuple(e.values()) for e in execs]
    # Map column names from query: time, symbol, side, quantity, price, fill_price, status, pnl
    mock_result.keys.return_value = ["time", "symbol", "side", "quantity", "price",
                                      "fill_price", "status", "pnl"]

    scout = ExecutionScout(
        redis_client=mock_redis,
        db_client=mock_db,
        brokers=["simulator"],
    )

    # --- Act ---
    await scout._analyze_broker("simulator")

    # --- Assert: quality computed ---
    key = "simulator:BTCUSDT"
    assert key in scout._latest_payload, \
        f"Expected payload for {key}, got keys: {list(scout._latest_payload.keys())}"
    payload = scout._latest_payload[key]
    assert payload.fill_quality_score > 0, \
        f"fill_quality_score should be > 0, got {payload.fill_quality_score}"
    assert payload.execution_regime in ("optimal", "degraded", "stressed", "unstable"), \
        f"Unexpected execution_regime: {payload.execution_regime}"
    assert payload.avg_slippage_bps >= 0, \
        f"avg_slippage_bps should be >= 0, got {payload.avg_slippage_bps}"
    assert payload.sample_size == 10, \
        f"Expected sample_size=10, got {payload.sample_size}"

    # --- Verify persistence ---
    insert_calls = [
        call for call in mock_db._execute_insert.call_args_list
        if "INSERT INTO execution_intelligence" in str(call[0][0])
    ]
    assert len(insert_calls) >= 1, "ExecutionScout did not persist"

    # --- Verify Redis publication ---
    pub_calls = [
        call for call in mock_redis.publish.call_args_list
        if call[0][0] == "scout:execution"
    ]
    assert len(pub_calls) >= 1, "ExecutionScout did not publish"
