"""P6 T6 — hermetic unit tests for the additive v1 SHADOW persistence layer.

Mirrors the mocked-engine convention in test_db.py (no live DB). Proves the
storage contracts: correct target tables, idempotent upsert, correct param
mapping, and — critically — that NO legacy table/column is touched and
strategies.status is never written (no authority switch).
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.data.storage.timescale_client import TimescaleClient

SID = "123e4567-e89b-12d3-a456-426614174000"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 2, 1, tzinfo=timezone.utc)


@pytest.fixture
def mock_engine():
    with patch(
        "atlas.data.storage.timescale_client.create_async_engine"
    ) as mock_create:
        engine = MagicMock()
        conn_mock = AsyncMock()
        engine.begin.return_value = AsyncMock()
        engine.begin.return_value.__aenter__.return_value = conn_mock
        engine.connect.return_value = AsyncMock()
        engine.connect.return_value.__aenter__.return_value = conn_mock
        mock_create.return_value = engine
        yield engine


@pytest.fixture
def client(mock_engine):
    return TimescaleClient("postgresql+asyncpg://user:pass@localhost/db")


def _begin_conn(mock_engine):
    conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = conn
    return conn


def _connect_result(mock_engine, mapping):
    conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = conn
    result = MagicMock()
    row = MagicMock()
    row._mapping = mapping
    result.fetchone.return_value = row if mapping is not None else None
    conn.execute.return_value = result
    return conn


# --------------------------------------------------------------------------- #
# writes target the correct *_v1 tables, idempotent upsert, param mapping
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_save_ledger_metrics_v1(client, mock_engine):
    conn = _begin_conn(mock_engine)
    metrics = dict(
        n_trades=120, total_return=0.05, gross_edge=0.08, cost_burden=0.03,
        max_drawdown=-0.12, win_rate=0.55, profit_factor=1.8, expectancy=0.0006,
        sharpe=2.1, sortino=2.5, calmar=0.4, avg_trade_duration_bars=14,
    )
    await client.save_ledger_metrics_v1(SID, START, END, metrics)

    conn.execute.assert_called_once()
    q = str(conn.execute.call_args[0][0])
    assert "INSERT INTO ledger_metrics_v1" in q
    assert "ON CONFLICT (strategy_id, start_date, end_date) DO UPDATE" in q
    p = conn.execute.call_args[0][1]
    assert p["strategy_id"] == SID
    assert p["max_drawdown"] == -0.12          # FRACTION preserved (no ×100)
    assert p["n_trades"] == 120
    assert p["metrics_version"] == "ledger_metrics_v1"


@pytest.mark.asyncio
async def test_save_strategy_scores_v1(client, mock_engine):
    conn = _begin_conn(mock_engine)
    fitness = dict(
        research_fitness=79.4, deploy_fitness=42.5, Q=0.794, M=0.535,
        perf_Q=0.92, robust_Q=0.605, sig_gate=1.0, overfit_gate=0.8, cost_gate=0.669,
    )
    await client.save_strategy_scores_v1(SID, START, END, fitness)

    conn.execute.assert_called_once()
    q = str(conn.execute.call_args[0][0])
    assert "INSERT INTO strategy_scores_v1" in q
    assert "ON CONFLICT (strategy_id, start_date, end_date) DO UPDATE" in q
    p = conn.execute.call_args[0][1]
    assert p["deploy_fitness"] == 42.5
    assert p["research_fitness"] == 79.4
    assert p["q"] == 0.794 and p["m"] == 0.535      # Q/M mapped to lowercase cols
    assert p["fitness_version"] == "fitness_v1"


@pytest.mark.asyncio
async def test_save_validator_result_v1(client, mock_engine):
    conn = _begin_conn(mock_engine)
    result = dict(
        status="validated", deploy_fitness=42.5, research_fitness=79.4,
        n_trades=120, coverage_complete=True,
    )
    await client.save_validator_result_v1(SID, START, END, result)

    conn.execute.assert_called_once()
    q = str(conn.execute.call_args[0][0])
    assert "INSERT INTO validator_results_v1" in q
    p = conn.execute.call_args[0][1]
    assert p["status_v1"] == "validated"
    assert p["coverage_complete"] is True
    assert p["structural_ok"] is True               # default when omitted
    assert p["policy_version"] == "validator_policy_v1"


@pytest.mark.asyncio
async def test_validator_save_never_touches_strategies_status(client, mock_engine):
    """The authority invariant: writing status_v1 must NOT write strategies.status."""
    conn = _begin_conn(mock_engine)
    await client.save_validator_result_v1(
        SID, START, END, dict(status="elite", deploy_fitness=70, research_fitness=85, n_trades=150, coverage_complete=True)
    )
    q = str(conn.execute.call_args[0][0]).lower()
    assert "update strategies" not in q
    assert "insert into strategies" not in q
    assert " strategies " not in q                  # no reference to the legacy table


# --------------------------------------------------------------------------- #
# reads: correct table + latest-by-end_date
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_ledger_metrics_v1(client, mock_engine):
    conn = _connect_result(mock_engine, {"strategy_id": SID, "sharpe": 2.1, "max_drawdown": -0.12})
    out = await client.get_ledger_metrics_v1(SID)
    q = str(conn.execute.call_args[0][0])
    assert "FROM ledger_metrics_v1" in q and "ORDER BY end_date DESC" in q
    assert out["sharpe"] == 2.1 and out["max_drawdown"] == -0.12


@pytest.mark.asyncio
async def test_get_strategy_scores_v1(client, mock_engine):
    conn = _connect_result(mock_engine, {"strategy_id": SID, "deploy_fitness": 42.5})
    out = await client.get_strategy_scores_v1(SID)
    q = str(conn.execute.call_args[0][0])
    assert "FROM strategy_scores_v1" in q and "ORDER BY end_date DESC" in q
    assert out["deploy_fitness"] == 42.5


@pytest.mark.asyncio
async def test_get_validator_result_v1_none_when_absent(client, mock_engine):
    _connect_result(mock_engine, None)
    assert await client.get_validator_result_v1(SID) is None


# --------------------------------------------------------------------------- #
# ensure_v1_tables: additive + idempotent DDL only
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_ensure_v1_tables_is_additive_and_idempotent(client, mock_engine):
    conn = _begin_conn(mock_engine)
    await client.ensure_v1_tables()

    stmts = [str(c[0][0]).lower() for c in conn.execute.call_args_list]
    joined = "\n".join(stmts)

    # all three tables created, idempotently
    for tbl in ("ledger_metrics_v1", "strategy_scores_v1", "validator_results_v1"):
        assert f"create table if not exists {tbl}" in joined, tbl
    # additive indexes only
    assert joined.count("create index if not exists") == 3
    # NEVER destructive / NEVER alters legacy
    assert "drop table" not in joined and "drop column" not in joined
    assert "alter table backtest_results" not in joined
    assert "alter table strategies" not in joined
    assert "update strategies" not in joined
    # FK references strategies(id) only (soft link), with cascade
    assert "references strategies (id) on delete cascade" in joined
