"""
phase31_db_migration.py — Phase 31: Create all required database tables.

Creates:
  - dominant_organism_log
  - mutation_lineage_log
  - organism_regime_profile
  - regime_specialization_aggregate
  - scout_divergence_log
  - portfolio_evolution_log
  - phase31_specialization_metrics
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.config.settings import settings


async def create_tables():
    """Create all Phase 31 database tables."""
    db_url = settings.database_url
    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        # ─── 31A: Dominant Organism Log ───
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS dominant_organism_log (
                id VARCHAR(64) PRIMARY KEY,
                tracked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                n_organisms_total INT DEFAULT 0,
                n_dominant_identified INT DEFAULT 0,
                dominant_organisms JSONB,
                lifespan_rankings JSONB,
                efficiency_rankings JSONB,
                expectancy_rankings JSONB,
                regime_specialists JSONB,
                mutation_family_resilience JSONB,
                recovery_scores JSONB,
                retirement_cause_distribution JSONB,
                ecosystem_health JSONB,
                metadata JSONB
            )
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_dominant_log_tracked_at
            ON dominant_organism_log (tracked_at DESC)
        """))

        # ─── 31B: Mutation Lineage Log ───
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS mutation_lineage_log (
                id VARCHAR(64) PRIMARY KEY,
                tracked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                n_mutations_analyzed INT DEFAULT 0,
                n_lineages_identified INT DEFAULT 0,
                n_dominant_lineages INT DEFAULT 0,
                lineages JSONB,
                survival_rates JSONB,
                regime_specialization JSONB,
                drawdown_behavior JSONB,
                dominant_lineages JSONB,
                ecosystem_stats JSONB,
                metadata JSONB
            )
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_lineage_log_tracked_at
            ON mutation_lineage_log (tracked_at DESC)
        """))

        # ─── 31C: Organism Regime Profile ───
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS organism_regime_profile (
                id VARCHAR(64) PRIMARY KEY,
                strategy_id VARCHAR(64) NOT NULL,
                profiled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                bull_survivability FLOAT DEFAULT 0,
                bear_survivability FLOAT DEFAULT 0,
                ranging_survivability FLOAT DEFAULT 0,
                volatility_tolerance FLOAT DEFAULT 0,
                liquidity_sensitivity FLOAT DEFAULT 0,
                archetype_regime_alignment FLOAT DEFAULT 0.5,
                primary_affinity VARCHAR(32) DEFAULT 'unknown',
                profile_confidence FLOAT DEFAULT 0,
                archetype VARCHAR(64) DEFAULT 'unknown',
                metadata JSONB
            )
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_regime_profile_strategy
            ON organism_regime_profile (strategy_id)
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_regime_profile_time
            ON organism_regime_profile (profiled_at DESC)
        """))

        # ─── 31C: Regime Specialization Aggregate ───
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS regime_specialization_aggregate (
                id VARCHAR(64) PRIMARY KEY,
                computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                n_organisms_profiled INT DEFAULT 0,
                affinity_scores JSONB,
                ecosystem_specialization JSONB,
                metadata JSONB
            )
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_regime_agg_time
            ON regime_specialization_aggregate (computed_at DESC)
        """))

        # ─── 31D: Scout Divergence Log ───
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS scout_divergence_log (
                id VARCHAR(64) PRIMARY KEY,
                tracked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                n_attributions_analyzed INT DEFAULT 0,
                n_scouts_tracked INT DEFAULT 0,
                profit_contribution JSONB,
                failure_contribution JSONB,
                regime_usefulness JSONB,
                contradiction_penalties JSONB,
                attribution_quality JSONB,
                divergence_scores JSONB,
                ecosystem_scout_health JSONB,
                metadata JSONB
            )
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_scout_divergence_time
            ON scout_divergence_log (tracked_at DESC)
        """))

        # ─── 31E: Portfolio Evolution Log ───
        await conn.execute(sa_text("DROP TABLE IF EXISTS portfolio_evolution_log CASCADE"))
        await conn.execute(sa_text("""
            CREATE TABLE portfolio_evolution_log (
                id VARCHAR(64) PRIMARY KEY,
                tracked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                portfolio_id TEXT,
                diversification_score FLOAT DEFAULT 0,
                correlation_collapse_risk FLOAT DEFAULT 0,
                contagion_exposure FLOAT DEFAULT 0,
                concentration_risk FLOAT DEFAULT 0,
                portfolio_survivability FLOAT DEFAULT 0,
                drawdown_recovery_speed FLOAT DEFAULT 0,
                active_strategies INT DEFAULT 0,
                n_organisms_analyzed INT DEFAULT 0,
                n_dominant_organisms INT DEFAULT 0,
                stress_active BOOLEAN DEFAULT FALSE,
                organism_strength_scores JSONB,
                correlation_penalties JSONB,
                diversification_rewards JSONB,
                pressured_allocations JSONB,
                migration_signals JSONB,
                evolution_pressure_stats JSONB,
                metadata JSONB
            )
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_evolution_time
            ON portfolio_evolution_log (tracked_at DESC)
        """))

        # ─── 31G: Phase 31 Specialization Metrics ───
        await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS phase31_specialization_metrics (
                id SERIAL PRIMARY KEY,
                recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                runtime_minutes INT,
                
                -- Population dynamics
                strategies_generated INT,
                validated_organisms INT,
                active_organisms INT,
                pending_backtest INT,
                pending_validation INT,
                pending_code INT,
                
                -- Trade density
                trades_executed INT,
                trade_throughput_24h INT,
                avg_trades_per_strategy FLOAT,
                
                -- Dominant organisms
                n_dominant_identified INT,
                n_dominant_lineages INT,
                dominant_concentration FLOAT,
                
                -- Mutation ecology
                mutation_candidates INT,
                mutation_family_count INT,
                mutation_accept_rate FLOAT,
                lineages_identified INT,
                lineage_depth_avg FLOAT,
                
                -- Regime specialization
                regime_specialization_count INT,
                regime_specialization_diversity FLOAT,
                regime_affinity_bull FLOAT,
                regime_affinity_bear FLOAT,
                regime_affinity_ranging FLOAT,
                
                -- Portfolio evolution
                portfolio_diversification FLOAT,
                concentration_risk FLOAT,
                capital_migrated_pct FLOAT,
                n_weak_penalized INT,
                n_dominant_boosted INT,
                retirement_count INT,
                
                -- Scout divergence
                scout_divergence_count INT,
                scout_trust_divergence FLOAT,
                n_high_value_scouts INT,
                n_contradictory_scouts INT,
                
                -- Stress testing
                active_perturbations INT,
                stress_level FLOAT,
                n_survivors INT,
                n_collapsed INT,
                
                -- Execution realism
                execution_degradation FLOAT,
                avg_slippage_bps FLOAT,
                avg_fill_probability FLOAT,
                
                -- Composite scores
                dominant_emergence_score FLOAT,
                lineage_evolution_score FLOAT,
                regime_adaptation_score FLOAT,
                scout_predictive_divergence FLOAT,
                portfolio_evolution_pressure FLOAT,
                stress_survival_score FLOAT,
                
                metadata JSONB
            )
        """))
        await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_phase31_metrics_time
            ON phase31_specialization_metrics (recorded_at DESC)
        """))

    logger.info("All Phase 31 tables created successfully")
    await engine.dispose()


async def main():
    logger.info("Starting Phase 31 DB migration...")
    await create_tables()
    logger.info("Phase 31 DB migration complete")


if __name__ == "__main__":
    asyncio.run(main())
