"""
Seed script: populate ALL dashboard-relevant tables with realistic demo data.

Run:  python scripts/seed_dashboard_data.py
"""

import asyncio
import json
import random
import uuid
from datetime import datetime, timezone, timedelta

random.seed(42)


async def seed():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from atlas.config.settings import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    # First, create tables that are expected but missing
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                key_hash TEXT NOT NULL,
                label TEXT,
                revoked_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS copy_execution_log (
                id SERIAL PRIMARY KEY,
                status TEXT,
                strategy_id UUID,
                symbol TEXT,
                side TEXT,
                quantity NUMERIC,
                price NUMERIC,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS copy_leader_accounts (
                id SERIAL PRIMARY KEY,
                leader_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                total_pnl NUMERIC DEFAULT 0,
                win_rate NUMERIC DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS copy_follower_accounts (
                id SERIAL PRIMARY KEY,
                follower_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                allocated_capital NUMERIC DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ensemble_execution (
                id SERIAL PRIMARY KEY,
                executed_at TIMESTAMPTZ DEFAULT NOW(),
                n_signals_processed INTEGER DEFAULT 0,
                n_trades_generated INTEGER DEFAULT 0
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS risk_state (
                id SERIAL PRIMARY KEY,
                scope TEXT,
                halted BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

    async with engine.begin() as conn:
        # ── 1. api_keys ──
        await conn.execute(text("""
            INSERT INTO api_keys (key_hash, label)
            SELECT 'demo_hash_abc123', 'Demo API Key'
            WHERE NOT EXISTS (SELECT 1 FROM api_keys LIMIT 1)
        """))

        # ── 2. Strategies (20 strategies across statuses) ──
        statuses = ["generated", "coded", "backtested", "validated", "failed_validation", "no_signal_strategy", "deployed"]
        archetypes = ["momentum", "mean_reversion", "breakout", "volatility", "stat_arb", "ml_regime", "option_spread", "macro_trend"]
        authors = ["IdeatorV2", "MutatorAgent", "CombinerAgent", "CoderAgent", "HypothesisEngine", "ScoutNetwork"]

        strategy_ids = []
        for i in range(20):
            sid = str(uuid.uuid4())
            strategy_ids.append(sid)
            status = random.choice(statuses)
            name = f"{random.choice(archetypes).title()}_{random.choice(['v1','v2','v3','alpha','beta','gamma','delta'])}"
            trace_id = str(uuid.uuid4())
            await conn.execute(
                text("""
                    INSERT INTO strategies (id, name, status, author_agent, strategy_signature,
                                            mutation_type, lifecycle_state, age_bars, trace_id,
                                            generation_batch, code, parameters, deployment_mode, created_at)
                    VALUES (:id, :name, :status, :author, :sig,
                            :mutation, :lifecycle, :age, :trace,
                            :batch, :code, :params, :dep_mode, :created)
                """),
                {
                    "id": sid,
                    "name": name,
                    "status": status,
                    "author": random.choice(authors),
                    "sig": f"sig_{sid}",
                    "mutation": random.choice(["crossover", "parameter_shift", "ensemble_blend", "feature_add", None]),
                    "lifecycle": status,
                    "age": random.randint(10, 500),
                    "trace": trace_id,
                    "code": f"# demo strategy code for {name}",
                    "params": json.dumps({"lookback": random.randint(5, 50), "threshold": round(random.uniform(0.5, 2.0), 2)}),
                    "dep_mode": random.choice(["paper", "live", "shadow"]),
                    "batch": f"batch_{random.randint(1,5)}",
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72)),
                }
            )

        # ── 3. Backtest results ──
        for sid in strategy_ids[:15]:
            sharpe = round(random.uniform(-0.5, 3.5), 2)
            end_date = datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 24))
            start_date = end_date - timedelta(days=random.randint(30, 365))
            await conn.execute(
                text("""
                    INSERT INTO backtest_results (strategy_id, start_date, end_date, sharpe, win_rate, total_trades,
                                                  composite_fitness_score, sortino_ratio,
                                                  calmar_ratio, expectancy, created_at)
                    VALUES (:sid, :start, :end, :sharpe, :win_rate, :trades, :fitness, :sortino, :calmar, :exp, :created)
                """),
                {
                    "sid": sid,
                    "start": start_date,
                    "end": end_date,
                    "sharpe": sharpe,
                    "win_rate": round(random.uniform(0.3, 0.8), 2),
                    "trades": random.randint(20, 500),
                    "fitness": round(random.uniform(20, 95), 1),
                    "sortino": round(sharpe * random.uniform(1.1, 1.5), 2),
                    "calmar": round(sharpe * random.uniform(0.5, 0.9), 2),
                    "exp": round(random.uniform(-50, 200), 2),
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48)),
                }
            )

        # ── 4. Lifecycle events (200+) ──
        stages = ["ideation", "coding", "backtest", "validation", "risk_check", "deployment", "monitoring"]
        status_vals = ["completed", "failed", "running", "pending", "skipped"]
        for _ in range(200):
            await conn.execute(
                text("""
                    INSERT INTO lifecycle_events (id, trace_id, stage, status, actor, strategy_id, metadata, created_at)
                    VALUES (:id, :trace, :stage, :status, :actor, :sid, :meta, :created)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "trace": random.choice(strategy_ids),
                    "stage": random.choice(stages),
                    "status": random.choice(status_vals),
                    "actor": random.choice(authors),
                    "sid": random.choice(strategy_ids),
                    "meta": json.dumps({"source": "seed", "reason": "demo data"}),
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 72), minutes=random.randint(0, 59)),
                }
            )

        # ── 5. Paper trades (100) ──
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "SPY", "QQQ", "IWM"]
        sides = ["buy", "sell"]
        trade_statuses = ["filled", "open", "cancelled"]
        for i in range(100):
            price = round(random.uniform(50, 500), 2)
            qty = random.randint(10, 2000)
            pnl = round(random.uniform(-500, 1500), 2) if random.random() > 0.2 else None
            trace_id = str(uuid.uuid4())
            await conn.execute(
                text("""
                    INSERT INTO paper_trades (strategy_id, symbol, side, quantity, price, fill_price,
                                              status, pnl, trace_id, feature_snapshot_id, time)
                    VALUES (:sid, :sym, :side, :qty, :price, :fill, :status, :pnl, :tid, :fsid, :time)
                """),
                {
                    "sid": random.choice(strategy_ids),
                    "tid": trace_id,
                    "fsid": str(uuid.uuid4()),
                    "sym": random.choice(symbols),
                    "side": random.choice(sides),
                    "qty": qty,
                    "price": price,
                    "fill": round(price * random.uniform(0.998, 1.002), 2),
                    "status": random.choice(trade_statuses),
                    "pnl": pnl,
                    "time": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48), minutes=random.randint(0, 59)),
                }
            )

        # ── 6. Pattern memory (30) ──
        pattern_types = ["momentum_continuation", "mean_reversion_signal", "breakout_confirmation",
                         "volatility_regime", "correlation_cluster", "regime_shift_detected"]
        for i in range(30):
            await conn.execute(
                text("""
                    INSERT INTO pattern_memory (pattern_type, archetype, composite_score_avg,
                                                confidence_score, recommendation, detected_at)
                    VALUES (:type, :arch, :score, :conf, :rec, :detected)
                """),
                {
                    "type": random.choice(pattern_types),
                    "arch": random.choice(archetypes),
                    "score": round(random.uniform(30, 95), 1),
                    "conf": round(random.uniform(0.3, 0.99), 2),
                    "rec": random.choice(["Hold", "Increase allocation", "Reduce exposure", "Monitor closely", "Consider entry"]),
                    "detected": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48)),
                }
            )

        # ── 7. Scout signals (60) ──
        scout_sources = ["regime_scout", "liquidity_scout", "correlation_scout", "execution_scout",
                         "sentiment_scout", "volume_scout"]
        signal_types = ["regime_change", "liquidity_warning", "correlation_break", "execution_quality",
                        "sentiment_shift", "volume_anomaly"]
        for i in range(60):
            await conn.execute(
                text("""
                    INSERT INTO scout_signals (source, symbol, signal_type, confidence_score,
                                               signal_data, created_at)
                    VALUES (:src, :sym, :stype, :conf, :data, :created)
                """),
                {
                    "src": random.choice(scout_sources),
                    "sym": random.choice(symbols + [""]),
                    "stype": random.choice(signal_types),
                    "conf": round(random.uniform(0.1, 0.95), 2),
                    "data": json.dumps({"details": "seed demo signal", "value": round(random.uniform(-1, 1), 3)}),
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48)),
                }
            )

        # ── 8. External scout memory (40) ──
        ext_sources = ["reddit_scout", "discord_scout", "youtube_scout", "twitter_scout", "podcast_scout"]
        for i in range(40):
            await conn.execute(
                text("""
                    INSERT INTO external_scout_memory (source, timestamp, sentiment, hypothesis_score,
                                                       signal_direction, mentioned_tickers)
                    VALUES (:src, :ts, :sent, :score, :dir, :tickers)
                """),
                {
                    "src": random.choice(ext_sources),
                    "ts": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48)),
                    "sent": round(random.uniform(-1, 1), 2),
                    "score": round(random.uniform(0, 1), 2),
                    "dir": random.choice(["bullish", "bearish", "neutral"]),
                    "tickers": json.dumps(random.sample(symbols, k=random.randint(1, 3))),
                }
            )

        # ── 9. Portfolio intelligence ──
        await conn.execute(
            text("""
                INSERT INTO portfolio_intelligence (computed_at, n_strategies, diversification_score,
                                                    concentration_risk, ensemble_survivability_score,
                                                    optimal_allocations)
                VALUES (:ts, :n, :div, :conc, :surv, :alloc)
            """),
            {
                "ts": datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 120)),
                "n": random.randint(8, 20),
                "div": round(random.uniform(0.4, 0.9), 2),
                "conc": round(random.uniform(0.1, 0.4), 2),
                "surv": round(random.uniform(0.6, 0.95), 2),
                "alloc": json.dumps({str(s): round(random.uniform(0.01, 0.15), 3) for s in random.sample(strategy_ids, 5)}),
            }
        )

        # ── 10. Capital allocation ──
        await conn.execute(
            text("""
                INSERT INTO capital_allocation (computed_at, method, total_exposure, n_strategies)
                VALUES (:ts, :method, :exp, :n)
            """),
            {
                "ts": datetime.now(timezone.utc) - timedelta(minutes=random.randint(10, 120)),
                "method": random.choice(["risk_parity", "sharpe_weighted", "equal_weight", "dynamic_kelly"]),
                "exp": round(random.uniform(0.3, 0.9), 2),
                "n": random.randint(5, 15),
            }
        )

        # ── 11. Drift detection ──
        await conn.execute(
            text("""
                INSERT INTO drift_detection (detected_at, feature_drift_score, strategy_drift_score,
                                             regime_drift_score, composite_severity,
                                             retrain_recommendations, retirement_candidates)
                VALUES (:ts, :feat, :strat, :regime, :comp, :rec, :cand)
            """),
            {
                "ts": datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 60)),
                "feat": round(random.uniform(0.1, 0.6), 2),
                "strat": round(random.uniform(0.1, 0.5), 2),
                "regime": round(random.uniform(0.1, 0.4), 2),
                "comp": round(random.uniform(10, 60), 1),
                "rec": json.dumps({"retrain": True, "priority": "medium"}),
                "cand": json.dumps(random.sample(strategy_ids, k=3)),
            }
        )

        # ── 12. Strategy retirement ──
        await conn.execute(
            text("""
                INSERT INTO strategy_retirement (analyzed_at, n_strategies_analyzed, n_retired,
                                                 n_monitor, n_retirement_pending)
                VALUES (:ts, :analyzed, :retired, :monitor, :pending)
            """),
            {
                "ts": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 12)),
                "analyzed": len(strategy_ids),
                "retired": random.randint(1, 4),
                "monitor": random.randint(2, 6),
                "pending": random.randint(1, 3),
            }
        )

        # ── 13. Execution realism (5 rows) ──
        for i in range(5):
            await conn.execute(
                text("""
                    INSERT INTO execution_realism (simulated_at, n_trades_simulated, avg_fill_probability,
                                                   avg_expected_slippage_bps, avg_simulated_latency_ms,
                                                   execution_degradation_score)
                    VALUES (:ts, :n, :fill, :slip, :lat, :degrad)
                """),
                {
                    "ts": datetime.now(timezone.utc) - timedelta(hours=i * 2),
                    "n": random.randint(50, 500),
                    "fill": round(random.uniform(0.85, 0.99), 2),
                    "slip": round(random.uniform(0.5, 3.5), 1),
                    "lat": round(random.uniform(5, 50), 1),
                    "degrad": round(random.uniform(0.01, 0.15), 3),
                }
            )

        # ── 14. Copy execution log (30 rows) ──
        copy_statuses = ["executed", "pending", "failed", "partial"]
        for i in range(30):
            await conn.execute(
                text("""
                    INSERT INTO copy_execution_log (status, strategy_id, symbol, side, quantity, price, created_at)
                    VALUES (:status, :sid, :sym, :side, :qty, :price, :created)
                """),
                {
                    "status": random.choice(copy_statuses),
                    "sid": random.choice(strategy_ids),
                    "sym": random.choice(symbols),
                    "side": random.choice(sides),
                    "qty": random.randint(10, 1000),
                    "price": round(random.uniform(50, 500), 2),
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48)),
                }
            )

        # ── 15. Validation analytics (12 strategies) ──
        for sid in strategy_ids[:12]:
            wf_score = round(random.uniform(40, 95), 1)
            mc_score = round(random.uniform(30, 90), 1)
            of_prob = round(random.uniform(5, 70), 1)
            rv_score = round(random.uniform(40, 95), 1)
            cs_score = round(random.uniform(40, 95), 1)
            ts = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48))

            await conn.execute(text("""INSERT INTO walk_forward_analysis (strategy_id, walk_forward_score, temporal_consistency, regime_survival_score, n_windows_survived, n_windows_total, analyzed_at) VALUES (:sid, :wf, :tc, :rs, :surv, :total, :ts)"""), {"sid": sid, "wf": wf_score, "tc": round(random.uniform(50, 95), 1), "rs": round(random.uniform(40, 90), 1), "surv": random.randint(3, 10), "total": 12, "ts": ts})
            await conn.execute(text("""INSERT INTO monte_carlo_analysis (strategy_id, monte_carlo_survival_score, expected_tail_drawdown, probabilistic_sharpe, n_simulations, simulated_at) VALUES (:sid, :surv, :tail, :sharpe, :n, :ts)"""), {"sid": sid, "surv": mc_score, "tail": round(random.uniform(-0.4, -0.05), 3), "sharpe": round(random.uniform(0.5, 3.0), 2), "n": random.randint(500, 5000), "ts": ts})
            await conn.execute(text("""INSERT INTO overfitting_analysis (strategy_id, overfit_probability, robustness_score, parameter_stability_score, analyzed_at) VALUES (:sid, :of, :rob, :stab, :ts)"""), {"sid": sid, "of": of_prob, "rob": round(random.uniform(40, 95), 1), "stab": round(random.uniform(50, 95), 1), "ts": ts})
            await conn.execute(text("""INSERT INTO regime_validation (strategy_id, regime_survival_score, regime_dependency_score, n_regimes_survived, over_specialized, validated_at) VALUES (:sid, :surv, :dep, :n, :spec, :ts)"""), {"sid": sid, "surv": rv_score, "dep": round(random.uniform(0.1, 0.7), 2), "n": random.randint(2, 6), "spec": random.random() < 0.2, "ts": ts})
            await conn.execute(text("""INSERT INTO cost_stress_analysis (strategy_id, cost_survival_score, max_survivable_multiplier, passes_min_survival, fragile_scalper_detected, tested_at) VALUES (:sid, :surv, :mult, :pass, :fragile, :ts)"""), {"sid": sid, "surv": cs_score, "mult": round(random.uniform(1.5, 8.0), 1), "pass": random.random() > 0.2, "fragile": random.random() < 0.15, "ts": ts})

        # ── 16. Feature importance (20 features) ──
        feature_names = ["rsi_14", "macd_signal", "bb_width", "volume_ratio", "atr_14",
                         "sma_50_200_cross", "momentum_20", "vwap_distance", "iv_percentile",
                         "put_call_ratio", "skew_delta", "term_structure", "correlation_spy",
                         "volume_profile", "market_regime", "liquidity_score", "fvg_gap_ratio",
                         "orderflow_imbalance", "delta_velocity", "gamma_exposure"]
        for name in feature_names:
            await conn.execute(
                text("""INSERT INTO feature_importance (feature_name, feature_importance_score, n_uses, survival_rate, dominant_archetype) VALUES (:name, :score, :uses, :surv, :arch)"""),
                {"name": name, "score": round(random.uniform(0.1, 0.95), 3), "uses": random.randint(5, 200), "surv": round(random.uniform(0.3, 0.85), 2), "arch": random.choice(archetypes + [""])}
            )

        # ── 17. Governance tables ──
        # System health
        await conn.execute(
            text("""INSERT INTO system_health (id, checked_at, composite_score, system_mode, degraded_subsystems, n_degraded, n_total) VALUES (:id, :ts, :score, :mode, :degraded, :n_degraded, :n_total)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 30)), "score": round(random.uniform(70, 98), 1), "mode": "normal", "degraded": json.dumps([]), "n_degraded": random.randint(0, 2), "n_total": 22}
        )

        # Event store (50 immutable events)
        for _ in range(50):
            await conn.execute(
                text("""INSERT INTO event_store (id, aggregate_type, event_type, aggregate_id, trace_id, created_at) VALUES (:id, :agg_type, :event_type, :agg_id, :trace, :created)"""),
                {"id": str(uuid.uuid4()), "agg_type": random.choice(["strategy", "trade", "risk", "scout", "deployment"]), "event_type": random.choice(["created", "updated", "validated", "deployed", "archived"]), "agg_id": str(uuid.uuid4()), "trace": random.choice(strategy_ids), "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 72))}
            )

        # Audit ledger (30 entries)
        for _ in range(30):
            await conn.execute(
                text("""INSERT INTO audit_ledger (id, event_type, actor, action, target_id, trace_id, created_at) VALUES (:id, :event, :actor, :action, :target, :trace, :created)"""),
                {"id": str(uuid.uuid4()), "event": random.choice(["system", "user", "automated", "governance"]), "actor": random.choice(["MetaOrchestrator", "DeploymentGovernor", "RiskManager", "admin"]), "action": random.choice(["approved", "rejected", "deployed", "halted", "restarted"]), "target": random.choice(strategy_ids), "trace": random.choice(strategy_ids), "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 72))}
            )

        # Deployment governance (10)
        for _ in range(10):
            await conn.execute(
                text("""INSERT INTO deployment_governance (id, strategy_id, mode, status, approved_by, proposed_at, activated_at) VALUES (:id, :sid, :mode, :status, :approver, :proposed, :activated)"""),
                {"id": str(uuid.uuid4()), "sid": random.choice(strategy_ids), "mode": random.choice(["paper", "live", "dry_run"]), "status": random.choice(["approved", "pending", "rejected", "halted"]), "approver": "DeploymentGovernor", "proposed": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48)), "activated": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 24)) if random.random() > 0.3 else None}
            )

        # Replay integrity
        await conn.execute(
            text("""INSERT INTO replay_integrity (id, checked_at, n_aggregates_checked, integrity_score, n_violations) VALUES (:id, :ts, :n, :score, :violations)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 60)), "n": random.randint(50, 200), "score": round(random.uniform(90, 100), 1), "violations": random.randint(0, 3)}
        )

        # Risk state (for kill switch check)
        await conn.execute(
            text("""INSERT INTO risk_state (scope, halted) VALUES ('portfolio', FALSE) ON CONFLICT DO NOTHING""")
        )

        # ── 18. Risk tables (Phase 14) ──
        await conn.execute(text("""INSERT INTO systemic_risk (id, assessed_at, systemic_risk_score, contagion_probability, portfolio_fragility) VALUES (:id, :ts, :score, :contagion, :fragility)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 60)), "score": round(random.uniform(0.1, 0.5), 2), "contagion": round(random.uniform(0.05, 0.3), 2), "fragility": round(random.uniform(0.05, 0.25), 2)})

        await conn.execute(text("""INSERT INTO stress_test_results (id, tested_at, n_scenarios, worst_scenario, min_survival_probability, max_drawdown) VALUES (:id, :ts, :n, :worst, :surv, :dd)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24)), "n": random.randint(5, 20), "worst": random.choice(["2008 Crisis", "2020 Covid", "2022 Rate Hike", "1987 Flash Crash"]), "surv": round(random.uniform(0.4, 0.9), 2), "dd": round(random.uniform(-0.4, -0.1), 3)})

        await conn.execute(text("""INSERT INTO capital_preservation_state (id, checked_at, drawdown_pct, action_taken, total_exposure) VALUES (:id, :ts, :dd, :action, :exp)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 60)), "dd": round(random.uniform(0.01, 0.08), 3), "action": random.choice(["none", "reduced_exposure", "halted_new_entries"]), "exp": round(random.uniform(0.3, 0.85), 2)})

        await conn.execute(text("""INSERT INTO advanced_portfolio_optimization (id, optimized_at, method_used, n_strategies) VALUES (:id, :ts, :method, :n)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24)), "method": random.choice(["markowitz_mvo", "black_litterman", "risk_parity", "hrp"]), "n": random.randint(5, 15)})

        # ── 19. Meta-learning tables (Phase 15) ──
        prompt_types = ["ideator", "coder", "mutator", "combiner", "validator", "risk"]
        for ptype in prompt_types:
            await conn.execute(text("""INSERT INTO prompt_templates (id, prompt_type, prompt_text, archetype, status, effectiveness_score, generation_count) VALUES (:id, :type, :text, :arch, :status, :eff, :gen)"""),
                {"id": str(uuid.uuid4()), "type": ptype, "text": f"Generate a {ptype} strategy prompt", "arch": random.choice(archetypes), "status": random.choice(["active", "evolving", "deprecated"]), "eff": round(random.uniform(0.3, 0.95), 2), "gen": random.randint(3, 20)})

        await conn.execute(text("""INSERT INTO mutation_policy_state (id, learned_at, n_observations) VALUES (:id, :ts, :n)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 12)), "n": random.randint(50, 500)})

        await conn.execute(text("""INSERT INTO agent_governance_state (id, assessed_at, n_agents_assessed, agent_scores, throttled_agents) VALUES (:id, :ts, :n, :scores, :throttled)"""),
            {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 6)), "n": random.randint(15, 30), "scores": json.dumps({f"Agent_{i}": round(random.uniform(0.5, 1.0), 2) for i in range(random.randint(10, 20))}),            "throttled": json.dumps(random.sample([f"Agent_{i}" for i in range(20)], k=random.randint(0, 3)))})

        # ── 20. Observability tables (Phase 17) ──
        for i in range(20):
            await conn.execute(
                text("""INSERT INTO monitoring_metrics (id, recorded_at, counters, latencies) VALUES (:id, :ts, :counters, :latencies)"""),
                {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(minutes=i * 5), "counters": json.dumps({"api_requests": random.randint(50, 500), "strategies_generated": random.randint(0, 10), "backtests_run": random.randint(0, 5), "errors": random.randint(0, 3)}), "latencies": json.dumps({"p50_ms": round(random.uniform(20, 100), 1), "p95_ms": round(random.uniform(100, 500), 1), "p99_ms": round(random.uniform(200, 1000), 1)})}
            )
        for i in range(10):
            await conn.execute(
                text("""INSERT INTO anomaly_observations (id, observed_at, n_anomalies, severity) VALUES (:id, :ts, :n, :sev)"""),
                {"id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc) - timedelta(minutes=i * 15), "n": random.randint(0, 5), "sev": round(random.uniform(0.1, 0.8), 2)}
            )

        # ── 21. Copy trading tables ──
        await conn.execute(text("""INSERT INTO copy_leader_accounts (leader_name, is_active, total_pnl, win_rate, created_at) VALUES ('AlphaTrader', TRUE, 12500.00, 0.68, NOW() - interval '30 days') ON CONFLICT DO NOTHING"""))
        await conn.execute(text("""INSERT INTO copy_leader_accounts (leader_name, is_active, total_pnl, win_rate, created_at) VALUES ('SigmaQuant', TRUE, 8900.00, 0.72, NOW() - interval '25 days') ON CONFLICT DO NOTHING"""))
        await conn.execute(text("""INSERT INTO copy_leader_accounts (leader_name, is_active, total_pnl, win_rate, created_at) VALUES ('GammaFund', TRUE, 4500.00, 0.61, NOW() - interval '20 days') ON CONFLICT DO NOTHING"""))
        await conn.execute(text("""INSERT INTO copy_follower_accounts (follower_name, is_active, allocated_capital, created_at) VALUES ('Follower_01', TRUE, 50000.00, NOW() - interval '20 days') ON CONFLICT DO NOTHING"""))
        await conn.execute(text("""INSERT INTO copy_follower_accounts (follower_name, is_active, allocated_capital, created_at) VALUES ('Follower_02', TRUE, 75000.00, NOW() - interval '15 days') ON CONFLICT DO NOTHING"""))
        await conn.execute(text("""INSERT INTO copy_follower_accounts (follower_name, is_active, allocated_capital, created_at) VALUES ('Follower_03', TRUE, 25000.00, NOW() - interval '10 days') ON CONFLICT DO NOTHING"""))

        # ── 22. Ensemble execution (10 rows) ──
        for i in range(10):
            await conn.execute(
                text("""INSERT INTO ensemble_execution (executed_at, n_signals_processed, n_trades_generated) VALUES (:ts, :signals, :trades)"""),
                {"ts": datetime.now(timezone.utc) - timedelta(minutes=i * 30), "signals": random.randint(5, 50), "trades": random.randint(1, 15)}
            )

        # ── 23. Mutation memory ──
        mutation_types = ["crossover", "parameter_shift", "ensemble_blend", "feature_add", "threshold_tweak"]
        for _ in range(40):
            parent_sid = random.choice(strategy_ids)
            # Pick a child different from parent
            child_options = [s for s in strategy_ids if s != parent_sid]
            child_sid = random.choice(child_options) if child_options else parent_sid
            parent_score = round(random.uniform(20, 80), 1)
            child_score = round(random.uniform(20, 95), 1)
            score_delta = round(child_score - parent_score, 1)
            improved = score_delta > 0
            await conn.execute(
                text("""INSERT INTO mutation_memory (parent_strategy_id, child_strategy_id, mutation_type,
                    changed_fields, parent_sharpe, child_sharpe, sharpe_delta,
                    parent_composite_score, child_composite_score, score_delta, improved,
                    parent_entry_count, child_entry_count, parent_trades, child_trades, created_at)
                    VALUES (:parent, :child, :mtype, :fields, :p_sharpe, :c_sharpe, :s_delta,
                            :p_score, :c_score, :sc_delta, :impr,
                            :p_entries, :c_entries, :p_trades, :c_trades, :created)"""),
                {
                    "parent": parent_sid, "child": child_sid,
                    "mtype": random.choice(mutation_types),
                    "fields": random.sample(["lookback", "threshold", "stop_loss", "take_profit", "position_size"], k=random.randint(1, 3)),
                    "p_sharpe": round(random.uniform(0.5, 2.5), 2),
                    "c_sharpe": round(random.uniform(0.5, 3.0), 2),
                    "s_delta": round(random.uniform(-0.5, 1.5), 2),
                    "p_score": parent_score,
                    "c_score": child_score,
                    "sc_delta": score_delta,
                    "impr": improved,
                    "p_entries": random.randint(10, 100),
                    "c_entries": random.randint(10, 100),
                    "p_trades": random.randint(20, 200),
                    "c_trades": random.randint(20, 200),
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 72)),
                }
            )

        # ── 24. Execution dead letter (10 sample records) ──
        failure_reasons = ["Connection timeout to broker", "Rate limit exceeded", "Insufficient funds", "Symbol not found", "Order rejected by exchange"]
        severities = ["low", "medium", "high"]
        for _ in range(10):
            resolved = random.random() < 0.5
            await conn.execute(
                text("""INSERT INTO execution_dead_letter (order_key, strategy_id, symbol, side, quantity,
                    failure_reason, last_state, severity, resolved, resolution, resolved_at, retry_count, created_at)
                    VALUES (:okey, :sid, :sym, :side, :qty, :reason, :state, :sev, :resolved, :resolution, :resolved_at, :retries, :created)"""),
                {
                    "okey": f"ord_{uuid.uuid4().hex[:8]}",
                    "sid": random.choice(strategy_ids),
                    "sym": random.choice(symbols),
                    "side": random.choice(sides),
                    "qty": random.randint(10, 500),
                    "reason": random.choice(failure_reasons),
                    "state": random.choice(["pending", "submitted", "timeout", "rejected"]),
                    "sev": random.choice(severities),
                    "resolved": resolved,
                    "resolution": "Auto-retry succeeded" if resolved else None,
                    "resolved_at": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24)) if resolved else None,
                    "retries": random.randint(0, 3),
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48)),
                }
            )

        # ── 25. Positions (a few sample open positions) ──
        for _ in range(5):
            await conn.execute(
                text("""INSERT INTO positions (strategy_id, symbol, side, qty, avg_price, current_price,
                    unrealized_pnl, realized_pnl, status, broker, trace_id, created_at, updated_at)
                    VALUES (:sid, :sym, :side, :qty, :avg_p, :cur_p, :unrl, :real, :status, :broker, :tid, :created, :updated)"""),
                {
                    "sid": random.choice(strategy_ids),
                    "sym": random.choice(symbols),
                    "side": random.choice(["buy", "sell"]),
                    "qty": random.randint(10, 500),
                    "avg_p": round(random.uniform(100, 400), 2),
                    "cur_p": round(random.uniform(100, 400), 2),
                    "unrl": round(random.uniform(-200, 500), 2),
                    "real": 0,
                    "status": "open",
                    "broker": "paper",
                    "tid": str(uuid.uuid4()),
                    "created": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5)),
                    "updated": datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 60)),
                }
            )

    print("✅ Seed complete — all dashboard-relevant tables populated with demo data.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
