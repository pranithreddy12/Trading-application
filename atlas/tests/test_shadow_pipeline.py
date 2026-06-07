"""P6 T7 — hermetic unit tests for the shadow computation pipeline.

Uses a fake db (no real DB). Proves: correct compute+classify, writes ONLY to the
v1 shadow tables, NEVER touches any legacy surface, and correct skip/batch behavior.
"""
from datetime import datetime, timedelta, timezone

import pytest

from atlas.core.shadow_pipeline import ShadowComputationPipeline, map_advanced

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _mk(pnls, days=30):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        dict(
            pnl_pct=p,
            bars_held=10,
            entry_time=base + timedelta(days=days * i / max(len(pnls), 1)),
            exit_time=base + timedelta(days=days * i / max(len(pnls), 1), minutes=10),
        )
        for i, p in enumerate(pnls)
    ]


GENUINE_GOOD = _mk([0.008 + 0.004 * ((i % 5) / 4) for i in range(120)])
FULL_ADV = dict(
    walk_forward_score=0.6,
    monte_carlo_survival_score=0.7,
    regime_survival_score=0.5,
    overfit_probability=0.1,
)

# Legacy methods the pipeline must NEVER call.
_FORBIDDEN = (
    "update_strategy_status",
    "save_backtest_results",
    "update_strategy_fields",
    "update_strategy_code",
)


class FakeDB:
    def __init__(self, *, window, trades, advanced):
        self._window = window
        self._trades = trades
        self._adv = advanced
        self.saved = {"ledger": [], "scores": [], "validator": []}
        self.forbidden_calls = []

    # reads
    async def get_backtest_result(self, sid):
        return self._window

    async def get_backtest_trades(self, sid):
        return self._trades

    async def get_advanced_validation(self, sid):
        return self._adv

    async def get_strategy_ids_with_backtest_results(self, limit=None):
        ids = ["s1", "s2", "s3", "s4"]
        return ids[:limit] if limit else ids

    async def get_shadow_computed_strategy_ids(self):
        return getattr(self, "_computed", [])

    # v1 writes
    async def save_ledger_metrics_v1(self, sid, s, e, m):
        self.saved["ledger"].append((sid, s, e, m))

    async def save_strategy_scores_v1(self, sid, s, e, f):
        self.saved["scores"].append((sid, s, e, f))

    async def save_validator_result_v1(self, sid, s, e, r):
        self.saved["validator"].append((sid, s, e, r))

    # forbidden legacy writes -> record if ever called
    def __getattr__(self, name):
        if name in _FORBIDDEN:
            def _rec(*a, **k):
                self.forbidden_calls.append(name)
                async def _noop():
                    return None
                return _noop()
            return _rec
        raise AttributeError(name)


def _win():
    return {"start_date": START, "end_date": END, "strategy_id": "s1"}


@pytest.mark.asyncio
async def test_genuine_good_writes_all_three_v1_tables():
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    rec = await ShadowComputationPipeline(db).process_strategy("s1")

    assert rec["written"] is True
    assert rec["status_v1"] == "validated"
    assert rec["deploy_fitness"] > 35.0
    assert len(db.saved["ledger"]) == 1
    assert len(db.saved["scores"]) == 1
    assert len(db.saved["validator"]) == 1
    # written under the legacy window key
    assert db.saved["ledger"][0][1] == START and db.saved["ledger"][0][2] == END
    # ledger metric is a FRACTION (no ×100)
    assert -1.0 <= db.saved["ledger"][0][3]["max_drawdown"] <= 0.0
    # validator row carries shadow status, not strategies.status
    assert db.saved["validator"][0][3]["status"] == "validated"


@pytest.mark.asyncio
async def test_never_touches_legacy_surface():
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    await ShadowComputationPipeline(db).process_strategy("s1")
    assert db.forbidden_calls == []  # no legacy write method called


@pytest.mark.asyncio
async def test_missing_coverage_is_pending_and_still_written():
    adv = dict(FULL_ADV)
    adv["monte_carlo_survival_score"] = None  # coverage gap
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=adv)
    rec = await ShadowComputationPipeline(db).process_strategy("s1")
    assert rec["status_v1"] == "pending_validation"
    assert rec["coverage_complete"] is False
    assert len(db.saved["validator"]) == 1


@pytest.mark.asyncio
async def test_insufficient_trades_skipped_no_writes():
    db = FakeDB(window=_win(), trades=_mk([0.05]), advanced=FULL_ADV)
    rec = await ShadowComputationPipeline(db).process_strategy("s1")
    assert rec["written"] is False
    assert rec["reason"] == "insufficient_trades"
    assert db.saved["ledger"] == [] and db.saved["scores"] == [] and db.saved["validator"] == []


@pytest.mark.asyncio
async def test_no_backtest_result_skipped():
    db = FakeDB(window=None, trades=GENUINE_GOOD, advanced=FULL_ADV)
    rec = await ShadowComputationPipeline(db).process_strategy("s1")
    assert rec["written"] is False and rec["reason"] == "no_backtest_result"
    assert db.saved["ledger"] == []


@pytest.mark.asyncio
async def test_run_batch_summary_counts():
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    summary = await ShadowComputationPipeline(db).run_batch(["s1", "s2", "s3"])
    assert summary["processed"] == 3
    assert summary["written"] == 3
    assert summary["ledger_rows"] == summary["score_rows"] == summary["validator_rows"] == 3
    assert summary["by_status"]["validated"] == 3
    assert summary["failed"] == 0


@pytest.mark.asyncio
async def test_replay_population_uses_enumerator_and_limit():
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    summary = await ShadowComputationPipeline(db).replay_population(limit=1)
    assert summary["population_size"] == 1
    assert summary["processed"] == 1 and summary["written"] == 1


@pytest.mark.asyncio
async def test_replay_resume_skips_already_computed():
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    db._computed = ["s1", "s2"]  # already in validator_results_v1
    summary = await ShadowComputationPipeline(db).replay_population(resume=True)
    assert summary["population_size"] == 4        # enumerated total
    assert summary["resumed_skipped"] == 2        # s1, s2 skipped
    assert summary["processed"] == 2              # only s3, s4 processed
    assert summary["written"] == 2


@pytest.mark.asyncio
async def test_replay_resume_idempotent_second_pass_noop():
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    db._computed = ["s1", "s2", "s3", "s4"]       # everything already done
    summary = await ShadowComputationPipeline(db).replay_population(resume=True)
    assert summary["resumed_skipped"] == 4
    assert summary["processed"] == 0 and summary["written"] == 0


@pytest.mark.asyncio
async def test_progress_callback_invoked():
    db = FakeDB(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    snaps = []
    await ShadowComputationPipeline(db).run_batch(
        ["s1", "s2", "s3"], progress_every=2, progress_cb=snaps.append
    )
    # one tick at processed==2, plus a final snapshot
    assert len(snaps) >= 2
    assert snaps[-1]["processed"] == 3
    assert all(set(s.keys()) == {"processed", "written", "skipped", "failed"} for s in snaps)


def test_map_advanced_key_mapping():
    out = map_advanced(FULL_ADV)
    assert out == {"walk_forward": 0.6, "monte_carlo": 0.7, "regime": 0.5, "overfit": 0.1}
    assert map_advanced(None) == {"walk_forward": None, "monte_carlo": None, "regime": None, "overfit": None}


def test_map_advanced_coerces_decimal():
    """NUMERIC columns arrive as Decimal; map_advanced must coerce to float."""
    from decimal import Decimal
    out = map_advanced(
        dict(
            walk_forward_score=Decimal("0.6"),
            monte_carlo_survival_score=Decimal("0.7"),
            regime_survival_score=Decimal("0.5"),
            overfit_probability=Decimal("0.1"),
        )
    )
    assert all(isinstance(v, float) for v in out.values())


@pytest.mark.asyncio
async def test_process_strategy_handles_decimal_db_values():
    """Regression: real DB returns Decimal for pnl_pct and advanced scores. The
    pipeline must not raise Decimal/float TypeErrors and must still validate."""
    from decimal import Decimal

    dec_trades = [dict(t, pnl_pct=Decimal(str(t["pnl_pct"]))) for t in GENUINE_GOOD]
    dec_adv = dict(
        walk_forward_score=Decimal("0.6"),
        monte_carlo_survival_score=Decimal("0.7"),
        regime_survival_score=Decimal("0.5"),
        overfit_probability=Decimal("0.1"),
    )
    db = FakeDB(window=_win(), trades=dec_trades, advanced=dec_adv)
    rec = await ShadowComputationPipeline(db).process_strategy("s1")
    assert rec["written"] is True
    assert rec["status_v1"] == "validated"


@pytest.mark.asyncio
async def test_batch_isolates_failures():
    # a strategy whose read raises must not abort the batch
    class Boom(FakeDB):
        async def get_backtest_trades(self, sid):
            if sid == "bad":
                raise RuntimeError("read failed")
            return self._trades

    db = Boom(window=_win(), trades=GENUINE_GOOD, advanced=FULL_ADV)
    summary = await ShadowComputationPipeline(db).run_batch(["s1", "bad", "s2"])
    assert summary["processed"] == 3
    assert summary["written"] == 2
    assert summary["failed"] == 1
    assert summary["errors"][0]["strategy_id"] == "bad"
