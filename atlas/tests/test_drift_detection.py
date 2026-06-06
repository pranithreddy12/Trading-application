"""Tests for DriftDetectionEngine — event-driven trigger, time-gated polling, importance CV fallback."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import numpy as np

from atlas.agents.l7_meta.drift_detection_engine import DriftDetectionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dummy_report(**overrides):
    """Minimal valid drift report for tests that don't need real DB data."""
    report = {
        "id": str(uuid.uuid4()),
        "detected_at": datetime.now(timezone.utc),
        "feature_drift": {"drift_detected": False, "drift_score": 0.0, "n_features_analyzed": 0},
        "strategy_drift": {"drift_detected": False, "drift_score": 0.0, "per_strategy": [], "n_strategies_analyzed": 0},
        "regime_drift": {"drift_detected": False, "drift_score": 0.0},
        "execution_drift": {"drift_detected": False, "drift_score": 0.0},
        "composite_severity": 0.0,
        "retirement_candidates": [],
        "retrain_recommendations": [],
        "n_strategies_monitored": 0,
        "data_status": {},
    }
    report.update(overrides)
    return report


def _mock_db_rows(mock_db, rows):
    """Configure the mock DB engine to return the given rows for its first query.

    NOTE: engine.connect() is a synchronous call in SQLAlchemy async
    (returns an async context manager), so we use MagicMock for engine.connect.
    """
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_connect_cm = AsyncMock()
    mock_connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_connect_cm.__aexit__ = AsyncMock(return_value=None)
    # Synchronous call in production — use MagicMock to avoid returning a coroutine
    mock_db.engine = MagicMock()
    mock_db.engine.connect = MagicMock(return_value=mock_connect_cm)


def _make_drift_engine(mock_redis, mock_db, **kwargs):
    """Factory helper — creates a DriftDetectionEngine with persisted drift disabled by default."""
    kwargs.setdefault("run_interval", 1800)
    engine = DriftDetectionEngine(redis_client=mock_redis, db_client=mock_db, **kwargs)
    # Disable persistence/publish side effects by default; individual tests opt in.
    engine._persist_drift = AsyncMock()
    engine._publish_drift = AsyncMock()
    return engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    # Default pub/sub: no incoming messages
    # NOTE: redis.pubsub() is a synchronous call in production (returns a PubSub object),
    # so we use MagicMock instead of AsyncMock to avoid returning a coroutine.
    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)
    redis.pubsub = MagicMock(return_value=mock_pubsub)
    return redis


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db._execute_insert = AsyncMock()
    # Default: empty result set
    _mock_db_rows(db, [])
    return db


# ===================================================================
# 1. Event-Driven Trigger (direct trigger() method)
# ===================================================================

class TestEventDrivenTrigger:
    """Tests for the public trigger() method — the primary external agent call path."""

    @pytest.mark.asyncio
    async def test_trigger_returns_report(self, mock_redis, mock_db):
        """trigger() computes drift and returns a valid report dict."""
        engine = _make_drift_engine(mock_redis, mock_db)
        engine._compute_drift_report = AsyncMock(return_value=_dummy_report())

        report = await engine.trigger("test_reason")

        assert report is not None
        assert report["id"] is not None
        engine._compute_drift_report.assert_called_once()
        engine._persist_drift.assert_called_once()
        engine._publish_drift.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_does_not_set_trigger_requested(self, mock_redis, mock_db):
        """trigger() runs inline and must NOT set _trigger_requested (avoids double-compute)."""
        engine = _make_drift_engine(mock_redis, mock_db)
        engine._compute_drift_report = AsyncMock(return_value=_dummy_report())

        await engine.trigger("feature_importance_updated")

        assert not engine._trigger_requested, (
            "_trigger_requested must remain False to prevent the run() loop "
            "from running a redundant computation"
        )

    @pytest.mark.asyncio
    async def test_trigger_no_db_returns_none(self, mock_redis):
        """trigger() returns None when no DB is configured."""
        engine = DriftDetectionEngine(redis_client=mock_redis, db_client=None)
        report = await engine.trigger("test_reason")
        assert report is None

    @pytest.mark.asyncio
    async def test_trigger_sets_reason(self, mock_redis, mock_db):
        """trigger() stores the reason string on the engine for logging."""
        engine = _make_drift_engine(mock_redis, mock_db)
        engine._compute_drift_report = AsyncMock(return_value=_dummy_report())

        await engine.trigger("feature_importance_updated")

        assert engine._trigger_reason == "feature_importance_updated"

    @pytest.mark.asyncio
    async def test_trigger_publishes_to_redis(self, mock_redis, mock_db):
        """trigger() publishes drift_detection_updates after computing."""
        engine = _make_drift_engine(mock_redis, mock_db)
        engine._publish_drift = AsyncMock()
        engine._compute_drift_report = AsyncMock(return_value=_dummy_report())

        await engine.trigger("test")

        engine._publish_drift.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_persists_to_db(self, mock_redis, mock_db):
        """trigger() persists the drift report to the database."""
        engine = _make_drift_engine(mock_redis, mock_db)
        engine._persist_drift = AsyncMock()
        engine._compute_drift_report = AsyncMock(return_value=_dummy_report())

        await engine.trigger("test")

        engine._persist_drift.assert_called_once()


# ===================================================================
# 2. Time-Gated Polling (run() loop)
# ===================================================================

class TestTimeGatedPolling:
    """Tests for the run() loop — periodic and event-driven drift computation."""

    @pytest.mark.asyncio
    async def test_run_computes_drift_at_least_once(self, mock_redis, mock_db):
        """run() computes drift on the first iteration (initial trigger)."""
        engine = DriftDetectionEngine(
            redis_client=mock_redis,
            db_client=mock_db,
            run_interval=0.1,
        )
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        compute_count = 0

        async def mock_compute():
            nonlocal compute_count
            compute_count += 1
            engine.status = "stopped"
            return _dummy_report()

        engine._compute_drift_report = mock_compute

        engine.status = "running"  # BaseAgent starts as "stopped" — must set before calling run()
        await engine.run()

        assert compute_count >= 1, "run() should compute drift at least once"

    @pytest.mark.asyncio
    async def test_run_persists_and_publishes(self, mock_redis, mock_db):
        """run() persists and publishes the computed drift report."""
        engine = DriftDetectionEngine(
            redis_client=mock_redis,
            db_client=mock_db,
            run_interval=0.1,
        )
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        async def mock_compute():
            engine.status = "stopped"
            return _dummy_report()

        engine._compute_drift_report = mock_compute

        engine.status = "running"  # BaseAgent starts as "stopped" — must set before calling run()
        await engine.run()

        engine._persist_drift.assert_called_once()
        engine._publish_drift.assert_called_once()

    @pytest.mark.asyncio
    async def test_pubsub_cleanup_on_stop(self, mock_redis, mock_db):
        """run() unsubscribes from event channels on exit."""
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = AsyncMock(return_value=None)
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        engine = DriftDetectionEngine(
            redis_client=mock_redis,
            db_client=mock_db,
            run_interval=0.05,
        )
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        async def mock_compute():
            engine.status = "stopped"
            return _dummy_report()

        engine._compute_drift_report = mock_compute

        engine.status = "running"  # BaseAgent starts as "stopped" — must set before calling run()
        await engine.run()

        mock_pubsub.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_responds_to_event_channel_message(self, mock_redis, mock_db):
        """run() triggers a drift check when a pub/sub event arrives."""
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = AsyncMock(side_effect=[
            None,  # first poll — no event (time-gate triggers this cycle)
            {"channel": b"feature_importance_updates", "data": b"{}"},  # second poll — event triggers
            None,
        ])
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        engine = DriftDetectionEngine(
            redis_client=mock_redis,
            db_client=mock_db,
            run_interval=3600,  # long — second call must be event-driven
        )
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        compute_count = 0

        async def mock_compute():
            nonlocal compute_count
            compute_count += 1
            if compute_count >= 2:
                engine.status = "stopped"
            return _dummy_report()

        engine._compute_drift_report = mock_compute

        engine.status = "running"  # BaseAgent starts as "stopped" — must set before calling run()
        await engine.run()

        # First call: initial time-gate trigger. Second call: event trigger.
        assert compute_count >= 2, (
            f"Expected 2+ drift computations (initial + event), got {compute_count}"
        )


# ===================================================================
# 3. Importance CV Fallback
# ===================================================================

class TestImportanceCVFallback:
    """The core fix for 'shows 0% when feature importance data exists'."""

    @pytest.mark.asyncio
    async def test_cv_fallback_when_all_decay_is_1(self, mock_redis, mock_db):
        """All decay=1.0 → uses importance CV → produces non-zero drift."""
        now = datetime.now(timezone.utc)
        rows = [
            ("rsi", 0.95, 1.0, 50, now),
            ("macd", 0.80, 1.0, 45, now),
            ("bband", 0.60, 1.0, 30, now),
            ("volume", 0.40, 1.0, 25, now),
            ("sma_cross", 0.25, 1.0, 20, now),
            ("atr", 0.10, 1.0, 15, now),
        ]
        engine = _make_drift_engine(mock_redis, mock_db)
        _mock_db_rows(mock_db, rows)

        report = await engine._compute_drift_report()

        fd = report["feature_drift"]
        assert fd["method_used"] == "importance_cv", "Should pick CV fallback"
        assert fd["drift_score"] > 0, "Should produce non-zero drift from importance CV"
        assert fd["n_features_analyzed"] == 6

    @pytest.mark.asyncio
    async def test_cv_fallback_too_few_features(self, mock_redis, mock_db):
        """< 3 features with positive importance → CV fallback returns 0 drift."""
        now = datetime.now(timezone.utc)
        rows = [
            ("rsi", 0.95, 1.0, 10, now),
            ("macd", 0.80, 1.0, 8, now),
        ]
        engine = _make_drift_engine(mock_redis, mock_db)
        _mock_db_rows(mock_db, rows)

        report = await engine._compute_drift_report()

        fd = report["feature_drift"]
        # All decay identical but only 2 positive-importance features → no CV
        assert fd["drift_score"] == 0

    @pytest.mark.asyncio
    async def test_cv_fallback_zero_mean_importance(self, mock_redis, mock_db):
        """All importance scores are 0 → mean=0 → CV=0 → drift=0."""
        now = datetime.now(timezone.utc)
        rows = [
            ("feat_a", 0.0, 1.0, 0, now),
            ("feat_b", 0.0, 1.0, 0, now),
            ("feat_c", 0.0, 1.0, 0, now),
            ("feat_d", 0.0, 1.0, 0, now),
        ]
        engine = _make_drift_engine(mock_redis, mock_db)
        _mock_db_rows(mock_db, rows)

        report = await engine._compute_drift_report()

        fd = report["feature_drift"]
        # imp_scores will be empty (filtered > 0) → no CV fallback → drift_score = 0
        assert fd["drift_score"] == 0

    @pytest.mark.asyncio
    async def test_decay_based_method_when_decay_varies(self, mock_redis, mock_db):
        """Varying decay scores → uses decay method, not CV."""
        now = datetime.now(timezone.utc)
        rows = [
            ("rsi", 0.90, 0.75, 50, now),
            ("macd", 0.80, 0.82, 45, now),
            ("bband", 0.60, 0.95, 30, now),
            ("volume", 0.40, 1.0, 25, now),
        ]
        engine = _make_drift_engine(mock_redis, mock_db)
        _mock_db_rows(mock_db, rows)

        report = await engine._compute_drift_report()

        fd = report["feature_drift"]
        assert fd["method_used"] == "decay", "Should pick decay method"
        assert len(fd["decaying_features"]) > 0
        assert fd["avg_feature_decay"] < 1.0


# ===================================================================
# 4. Edge Cases
# ===================================================================

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_no_db_returns_none(self, mock_redis):
        """Without db_client, _compute_drift_report returns None."""
        engine = DriftDetectionEngine(redis_client=mock_redis, db_client=None)
        report = await engine._compute_drift_report()
        assert report is None

    @pytest.mark.asyncio
    async def test_empty_features_table(self, mock_redis, mock_db):
        """Empty feature_importance table → feature_drift shows no drift / insufficient_data."""
        _mock_db_rows(mock_db, [])  # No rows
        engine = _make_drift_engine(mock_redis, mock_db)

        report = await engine._compute_drift_report()

        assert report is not None
        assert report["feature_drift"]["drift_detected"] is False
        assert report["feature_drift"]["n_features_analyzed"] == 0
        assert report["data_status"]["feature_drift"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_db_query_failure_is_handled(self, mock_redis, mock_db):
        """Exception in DB query returns a safe fallback dict, not a crash."""
        engine = DriftDetectionEngine(redis_client=mock_redis, db_client=mock_db)
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        # Override connect to raise
        mock_bad_conn = AsyncMock()
        mock_bad_conn.execute = AsyncMock(side_effect=Exception("connection lost"))
        mock_bad_cm = AsyncMock()
        mock_bad_cm.__aenter__ = AsyncMock(return_value=mock_bad_conn)
        mock_bad_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db.engine = MagicMock()
        mock_db.engine.connect = MagicMock(return_value=mock_bad_cm)

        report = await engine._compute_drift_report()

        # Report should still be generated (other dimensions may work)
        assert report is not None

        # Feature drift should contain the error
        fd = report["feature_drift"]
        assert fd["drift_detected"] is False
        assert fd["drift_score"] == 0
        assert "error" in fd

    @pytest.mark.asyncio
    async def test_composite_severity_calculation(self, mock_redis, mock_db):
        """_compute_composite_severity combines four drift dimensions with weights."""
        engine = DriftDetectionEngine(redis_client=mock_redis, db_client=mock_db)
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        # Mock all four drift methods to return known values
        engine._detect_feature_drift = AsyncMock(return_value={
            "drift_detected": True, "drift_score": 0.5
        })
        engine._detect_strategy_drift = AsyncMock(return_value={
            "drift_detected": True, "drift_score": 0.4
        })
        engine._detect_regime_drift = AsyncMock(return_value={
            "drift_detected": True, "drift_score": 0.3
        })
        engine._detect_execution_drift = AsyncMock(return_value={
            "drift_detected": True, "drift_score": 0.2
        })

        report = await engine._compute_drift_report()

        # Weights: feature=0.2, strategy=0.35, regime=0.25, execution=0.2
        # Each detected drift has a 0.1 floor, so:
        # max(0.5, 0.1)*0.2 + max(0.4, 0.1)*0.35 + max(0.3, 0.1)*0.25 + max(0.2, 0.1)*0.2
        # = 0.5*0.2 + 0.4*0.35 + 0.3*0.25 + 0.2*0.2
        # = 0.10 + 0.14 + 0.075 + 0.04 = 0.355
        expected = round(0.5 * 0.2 + 0.4 * 0.35 + 0.3 * 0.25 + 0.2 * 0.2, 4)
        assert report["composite_severity"] == expected

    @pytest.mark.asyncio
    async def test_retirement_candidates_identified(self, mock_redis, mock_db):
        """_identify_retirement_candidates flags strategies decaying beyond 30%."""
        engine = _make_drift_engine(mock_redis, mock_db)
        strategy_drift = {
            "per_strategy": [
                {"strategy_id": "s1", "strategy_name": "strat_a",
                 "drift_pct": -0.40, "recent_score": 50, "avg_prior_score": 80,
                 "direction": "decaying"},
                {"strategy_id": "s2", "strategy_name": "strat_b",
                 "drift_pct": -0.20, "recent_score": 70, "avg_prior_score": 85,
                 "direction": "decaying"},
                {"strategy_id": "s3", "strategy_name": "strat_c",
                 "drift_pct": 0.15, "recent_score": 90, "avg_prior_score": 80,
                 "direction": "improving"},
            ]
        }
        candidates = engine._identify_retirement_candidates(strategy_drift)
        assert len(candidates) == 1
        assert candidates[0]["strategy_id"] == "s1"
        assert candidates[0]["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_retirement_severity_high_when_drift_exceeds_50pct(self, mock_redis, mock_db):
        """Retirement severity is 'high' when drift exceeds 50%."""
        engine = _make_drift_engine(mock_redis, mock_db)
        strategy_drift = {
            "per_strategy": [
                {"strategy_id": "s1", "strategy_name": "strat_a",
                 "drift_pct": -0.60, "recent_score": 30, "avg_prior_score": 75,
                 "direction": "decaying"},
            ]
        }
        candidates = engine._identify_retirement_candidates(strategy_drift)
        assert len(candidates) == 1
        assert candidates[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_no_retirement_for_improving_strategies(self, mock_redis, mock_db):
        """Improving strategies never appear in retirement candidates."""
        engine = _make_drift_engine(mock_redis, mock_db)
        strategy_drift = {
            "per_strategy": [
                {"strategy_id": "s1", "strategy_name": "strat_a",
                 "drift_pct": 0.50, "recent_score": 90, "avg_prior_score": 60,
                 "direction": "improving"},
            ]
        }
        candidates = engine._identify_retirement_candidates(strategy_drift)
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_no_retirement_for_small_decay(self, mock_redis, mock_db):
        """Decaying strategies under 30% threshold are not flagged."""
        engine = _make_drift_engine(mock_redis, mock_db)
        strategy_drift = {
            "per_strategy": [
                {"strategy_id": "s1", "strategy_name": "strat_a",
                 "drift_pct": -0.25, "recent_score": 65, "avg_prior_score": 80,
                 "direction": "decaying"},
            ]
        }
        candidates = engine._identify_retirement_candidates(strategy_drift)
        assert len(candidates) == 0


# ===================================================================
# 5. Retrain Recommendation Logic
# ===================================================================

class TestRetrainRecommendations:

    @pytest.mark.asyncio
    async def test_high_severity_generates_recommendation(self, mock_redis, mock_db):
        """Drift > 0.4 produces 'high' severity retrain recommendation."""
        engine = _make_drift_engine(mock_redis, mock_db)
        drifts = [
            {"drift_detected": True, "drift_score": 0.5},  # feature — high
            {"drift_detected": False, "drift_score": 0.0},  # strategy
            {"drift_detected": True, "drift_score": 0.3},   # regime — medium
            {"drift_detected": False, "drift_score": 0.0},  # execution
        ]
        recs = engine._generate_retrain_recommendations(drifts)

        assert len(recs) == 2
        assert recs[0]["component"] == "feature_importance"
        assert recs[0]["severity"] == "high"
        assert recs[1]["component"] == "regime_classifier"
        assert recs[1]["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_no_drift_no_recommendations(self, mock_redis, mock_db):
        """No drift detected → empty recommendations."""
        engine = _make_drift_engine(mock_redis, mock_db)
        drifts = [
            {"drift_detected": False, "drift_score": 0.0},
            {"drift_detected": False, "drift_score": 0.0},
            {"drift_detected": False, "drift_score": 0.0},
            {"drift_detected": False, "drift_score": 0.0},
        ]
        recs = engine._generate_retrain_recommendations(drifts)
        assert len(recs) == 0


# ===================================================================
# 6. Run() Loop Edge Cases
# ===================================================================

class TestRunLoopEdgeCases:

    @pytest.mark.asyncio
    async def test_no_redis_no_pubsub(self, mock_db):
        """run() works without Redis (pub/sub is None) — no subscriptions, periodic polling only."""
        engine = DriftDetectionEngine(
            redis_client=None,
            db_client=mock_db,
            run_interval=0.05,
        )
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        async def mock_compute():
            engine.status = "stopped"
            return _dummy_report()

        engine._compute_drift_report = mock_compute

        engine.status = "running"  # BaseAgent starts as "stopped" — must set before calling run()
        await engine.run()

    @pytest.mark.asyncio
    async def test_pubsub_subscribe_failure_does_not_crash(self, mock_redis, mock_db):
        """If pub/sub subscribe fails, run() continues with polling-only mode."""
        mock_redis.pubsub.side_effect = Exception("redis down")

        engine = DriftDetectionEngine(
            redis_client=mock_redis,
            db_client=mock_db,
            run_interval=0.05,
        )
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        async def mock_compute():
            engine.status = "stopped"
            return _dummy_report()

        engine._compute_drift_report = mock_compute

        engine.status = "running"  # BaseAgent starts as "stopped" — must set before calling run()
        await engine.run()

    @pytest.mark.asyncio
    async def test_programmatic_trigger_flag_picked_up_by_run(self, mock_redis, mock_db):
        """Setting _trigger_requested=True causes run() to compute drift on next cycle."""
        engine = DriftDetectionEngine(
            redis_client=mock_redis,
            db_client=mock_db,
            run_interval=3600,  # long — won't trigger by time after first check
        )
        engine._persist_drift = AsyncMock()
        engine._publish_drift = AsyncMock()

        compute_calls = 0

        async def mock_compute():
            nonlocal compute_calls
            compute_calls += 1
            if compute_calls >= 1:
                # On the first call, set the programmatic trigger flag for the next cycle
                engine._trigger_requested = True
            if compute_calls >= 2:
                engine.status = "stopped"
            return _dummy_report()

        engine._compute_drift_report = mock_compute

        engine.status = "running"  # BaseAgent starts as "stopped" — must set before calling run()
        await engine.run()

        # First call: initial time-gate trigger.
        # Second call: the programmatic trigger flag we set during first call.
        assert compute_calls >= 2, (
            f"Expected 2+ drift computations (initial + trigger flag), got {compute_calls}"
        )
