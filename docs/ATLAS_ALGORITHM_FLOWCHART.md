# ATLAS — Complete Algorithm Flowchart & System Blueprint

## Executive Summary

**ATLAS** (Adaptive Trading Learning Autonomous System) is a **fully autonomous quantitative trading platform** that operates as a 7-layer AI agent ecosystem. It autonomously generates, tests, evolves, validates, deploys, and monitors algorithmic trading strategies across equities and crypto markets — all without human intervention.

**Core Innovation:** An evolutionary intelligence system where strategies are born (ideation), coded, backtested, validated, mutated, combined, and retired through Darwinian selection pressures — continuously improving the portfolio's edge.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Master Algorithm Flow](#2-master-algorithm-flow)
3. [Layer L1 — Data Ingestion](#3-layer-l1--data-ingestion)
4. [Layer L2 — Strategy Generation](#4-layer-l2--strategy-generation)
5. [Layer L3 — Backtesting & Validation](#5-layer-l3--backtesting--validation)
6. [Layer L4 — Risk Management](#6-layer-l4--risk-management)
7. [Layer L5 — Execution](#7-layer-l5--execution)
8. [Layer L6 — Portfolio Intelligence](#8-layer-l6--portfolio-intelligence)
9. [Layer L7 — Meta-Intelligence](#9-layer-l7--meta-intelligence)
10. [Scout Network](#10-scout-network)
11. [Evolutionary Engine](#11-evolutionary-engine)
12. [Governance & Replay](#12-governance--replay)
13. [Data Architecture](#13-data-architecture)
14. [Complete State Machine](#14-complete-state-machine)
15. [Agent Communication Map](#15-agent-communication-map)
16. [Key Algorithms Reference](#16-key-algorithms-reference)

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ATLAS ECOSYSTEM                                   │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ REDIS    │  │TIMESCALE │  │ FASTAPI  │  │DASHBOARD │               │
│  │(PubSub + │  │    DB     │  │  REST    │  │   HTML   │               │
│  │  Heartbeats)│  │(40+ tables)│  │   API    │  │    UI    │               │
│  └─────┬────┘  └─────┬────┘  └────┬─────┘  └──────────┘               │
│        │              │            │                                     │
│  ══════╪══════════════╪════════════╪═══════════════════════             │
│        │              │            │                                     │
│  ┌─────┴──────────────┴────────────┴───────────────────────┐           │
│  │               META ORCHESTRATOR                          │           │
│  │  (Startup ordering, health monitoring, auto-restart)     │           │
│  └──────────────────────────────────────────────────────────┘           │
│                                                                         │
│  L7 ┌──────────────────────────────────────────────────────────────┐    │
│     │ MetaReasoning │ ReplayEngine │ HypothesisEngine │            │    │
│     │ FailureAnalysis │ MutationPolicy │ PromptEvolution │         │    │
│     │ ScoutSynthesis │ DeploymentGovernor │ SystemHealth │         │    │
│     │ DriftDetection │ RegimeSpecialization │ EconomicAttribution │    │
│     │ AntiPoisoning │ FeatureEvolution │ FeatureImportance │       │    │
│     │ AgentPerformanceGovernor │ StrategyRetirement │              │    │
│     │ DominantOrganismTracker │ MutationLineageTracker │           │    │
│     │ ScoutDivergence │ RegimeStress │ SelfImprovement │          │    │
│     │ CopyAnalytics │ IntelligenceBrief │ MutationPattern │        │    │
│     │ PatternAgent │ EntropyGovernance │ EconomicEfficiency │      │    │
│     └──────────────────────────────────────────────────────────────┘    │
│  L6 ┌──────────────────────────────────────────────────────────────┐    │
│     │ PortfolioIntelligence │ CapitalAllocator │                    │    │
│     │ AdvancedPortfolioOptimizer │ CopyOverlapEngine │              │    │
│     │ CopyCapitalAllocator │ EnsembleExecutionEngine │              │    │
│     │ PortfolioEvolutionPressure │ LeaderGovernanceEngine │         │    │
│     └──────────────────────────────────────────────────────────────┘    │
│  L5 ┌──────────────────────────────────────────────────────────────┐    │
│     │ ExecutionGateway │ CopyTrader │ BrokerAdapter │              │    │
│     │ PositionManager │ OrderTracker │ RecoveryManager │            │    │
│     │ DeadLetterManager │ CopyDriftEngine │                        │    │
│     │ CopyFailoverManager │ PositionReconciliationEngine │         │    │
│     │ ExecutionRealismEngine │ AlpacaExecutor │ BinanceExecutor │  │    │
│     └──────────────────────────────────────────────────────────────┘    │
│  L4 ┌──────────────────────────────────────────────────────────────┐    │
│     │ KillSwitch │ SystemicRiskEngine │ CapitalPreservationEngine │ │    │
│     │ StressTestEngine │ RiskController │                          │    │
│     └──────────────────────────────────────────────────────────────┘    │
│  L3 ┌──────────────────────────────────────────────────────────────┐    │
│     │ BacktestRunner │ ValidatorAgent │ RegimeSelector │            │    │
│     │ ShortWindowEvaluator │ FitnessScorer │                        │    │
│     └──────────────────────────────────────────────────────────────┘    │
│  L2 ┌──────────────────────────────────────────────────────────────┐    │
│     │ IdeatorAgent(×5) │ IdeatorAgentV2 │ CoderAgent │            │    │
│     │ MutatorAgent │ CombinerAgent │ StrategyNormalizer │          │    │
│     │ ConditionParser │ ViabilityScore │ MutationMetrics │          │    │
│     │ MutationPatternAgent │ StrategyBase │                         │    │
│     └──────────────────────────────────────────────────────────────┘    │
│  L1 ┌──────────────────────────────────────────────────────────────┐    │
│     │ PolygonWebSocketAgent │ BinanceRestAgent │ FeatureAgent │    │    │
│     │ HistoricalBackfill │                                         │    │
│     └──────────────────────────────────────────────────────────────┘    │
│  Scout Network                                                         │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ RegimeScout │ LiquidityScout │ CorrelationScout │              │    │
│  │ ExecutionScout │ NewsIntelligence │ RedditScout │               │    │
│  │ DiscordScout │ YouTubeScout │ PodcastScout │                    │    │
│  │ CompetitionScout │ HypothesisValidationEngine │                 │    │
│  │ SourceReliabilityEngine │                                       │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Master Algorithm Flow

This is the complete lifecycle of a strategy from birth to execution:

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    ATLAS MASTER ALGORITHM FLOW                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                         ║
║  ┌─────────────────┐                                                   ║
║  │  MARKET DATA     │  Polygon.io WebSocket (equities)                 ║
║  │  INGESTION       │  Binance REST API (crypto)                       ║
║  │  (L1)            │  → market_data_l1 (1m bars)                      ║
║  └────────┬────────┘  → market_data_l2 (quotes/depth)                  ║
║           │            → order_flow (trades)                            ║
║           ▼                                                             ║
║  ┌─────────────────┐                                                   ║
║  │  FEATURE         │  Computes 20 features per bar:                   ║
║  │  COMPUTATION     │  RSI, MACD, Bollinger, VWAP, EMA spread,        ║
║  │  (L1)            │  relative_volume, trend_strength, etc.            ║
║  └────────┬────────┘  → features table (wide format)                   ║
║           │                                                             ║
║           ▼                                                             ║
║  ┌─────────────────┐                                                   ║
║  │  SCOUT NETWORK   │  12+ scouts continuously monitor:                ║
║  │  (Cross-layer)   │  Regime, Liquidity, Correlation, News,           ║
║  │                  │  Reddit, Discord, YouTube, Podcast                ║
║  └────────┬────────┘  → Scout intelligence feeds ALL layers            ║
║           │                                                             ║
║     ┌─────┼─────────────────────────────────┐                          ║
║     ▼     ▼                                 ▼                          ║
║  ┌────────────┐  ┌────────────┐  ┌────────────────────┐               ║
║  │ IDEATION   │  │ MUTATION   │  │ COMBINATION         │               ║
║  │ (L2)       │  │ (L2)       │  │ (L2)                │               ║
║  │            │  │            │  │                      │               ║
║  │ 5 parallel │  │ Tournament │  │ Tournament-select    │               ║
║  │ Ideator    │  │ select     │  │ 2 top strategies,    │               ║
║  │ Agents     │  │ weak-but-  │  │ Claude hybridizes    │               ║
║  │            │  │ viable     │  │ them                 │               ║
║  │ Claude LLM │  │ candidates │  │                      │               ║
║  │ + local    │  │ for mutation│  │ Every 2 hours       │               ║
║  │ fallback   │  │            │  │                      │               ║
║  │ templates  │  │ Deterministic + Claude mutations     │               ║
║  └─────┬──────┘  └─────┬──────┘  └─────────┬──────────┘               ║
║        │                │                    │                          ║
║        ▼                ▼                    ▼                          ║
║  ┌─────────────────────────────────────────────────┐                   ║
║  │        STRATEGY NORMALIZER                        │                   ║
║  │  • Validates feature names against whitelist      │                   ║
║  │  • Normalizes thresholds (auto-round precision)   │                   ║
║  │  • Rejects raw price conditions                   │                   ║
║  │  • Enforces max 4 conditions                      │                   ║
║  │  • Computes diversity score (feature families)     │                   ║
║  │  • Deduplicates via MD5 signature                 │                   ║
║  └───────────────────────┬─────────────────────────┘                   ║
║                          ▼                                              ║
║  ┌─────────────────────────────────────────────────┐                   ║
║  │  CODER AGENT (L2)                                │                   ║
║  │  • Converts normalized spec → executable Python   │                   ║
║  │  • Generates generate_signals(df) method          │                   ║
║  │  • Includes regime classification logic           │                   ║
║  │  • Position state machine (entry/hold/exit)       │                   ║
║  │  • compile() validation before DB save            │                   ║
║  │  • Sanitizes code (removes imports, comments)     │                   ║
║  │  Status: pending_code → pending_backtest          │                   ║
║  └───────────────────────┬─────────────────────────┘                   ║
║                          ▼                                              ║
║  ┌─────────────────────────────────────────────────┐                   ║
║  │  BACKTEST RUNNER (L3)                            │                   ║
║  │  • exec() the generated code                     │                   ║
║  │  • Load market data + features for best symbol   │                   ║
║  │  • Run generate_signals(df) → signal series      │                   ║
║  │  • State machine trade extraction                │                   ║
║  │  • Dynamic slippage (vol + volume based)         │                   ║
║  │  • Train/Test/Holdout split (60/20/20)           │                   ║
║  │  • Short window mode (<20k bars):                │                   ║
║  │    composite = f(return, PF, WR, DD, trades)     │                   ║
║  │  • Institutional mode (>20k bars):               │                   ║
║  │    full annualized Sharpe, Sortino, Calmar       │                   ║
║  │  • Regime robustness score (multi-regime = good) │                   ║
║  │  • Cost-aware: commission + slippage + spread    │                   ║
║  │  Status: pending_backtest → pending_validation    │                   ║
║  └───────────────────────┬─────────────────────────┘                   ║
║                          ▼                                              ║
║  ┌─────────────────────────────────────────────────┐                   ║
║  │  VALIDATOR AGENT (L3)                            │                   ║
║  │  Phase 1: Structural Sanity Gate                 │                   ║
║  │    • Entry count ≥ threshold                     │                   ║
║  │    • Trade count ≥ minimum                       │                   ║
║  │    • No entry/exit saturation                    │                   ║
║  │  Phase 2: Performance Tests                      │                   ║
║  │    • Composite score (short window OR Sharpe)    │                   ║
║  │    • Drawdown limits                             │                   ║
║  │    • Win rate & profit factor minimums           │                   ║
║  │  Phase 3: Cost Governance                        │                   ║
║  │    • Edge per trade > round-trip cost            │                   ║
║  │    • Cost trap detection                         │                   ║
║  │    • Frequency-dependent thresholds             │                   ║
║  │  Phase 4: Tier Assignment                        │                   ║
║  │    • elite (score ≥ 60-90)                       │                   ║
║  │    • validated (35-60-70)                        │                   ║
║  │    • research_candidate (25-50)                  │                   ║
║  │    • repair_candidate (15-30)                    │                   ║
║  │    • failed_validation (<15-30)                  │                   ║
║  │  Scout-Aware: Adjusts thresholds by liquidity/  │                   ║
║  │    execution regime                              │                   ║
║  └───────────────────────┬─────────────────────────┘                   ║
║                          │                                              ║
║          ┌───────────────┼───────────────────┐                         ║
║          ▼               ▼                   ▼                         ║
║  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐               ║
║  │ ELITE/       │ │ REPAIR       │ │ FAILED            │               ║
║  │ VALIDATED    │ │ CANDIDATE    │ │                   │               ║
║  │              │ │              │ │ → Strategy         │               ║
║  │ → Deploy to  │ │ → Mutator    │ │   Retirement      │               ║
║  │   paper/     │ │   Agent      │ │   Engine          │               ║
║  │   shadow/    │ │              │ │                   │               ║
║  │   live       │ │ → Pattern    │ └──────────────────┘               ║
║  └──────┬───────┘ │   Memory     │                                     ║
║         │         └──────┬───────┘                                     ║
║         │                │                                              ║
║         ▼                ▼                                              ║
║  ┌─────────────────────────────────────────────────┐                   ║
║  │  EVOLUTIONARY ENGINE                             │                   ║
║  │                                                   │                   ║
║  │  Mutation Agent:                                  │                   ║
║  │  • Tournament select 5 from 30 candidates         │                   ║
║  │  • 7+ deterministic micro-mutations:              │                   ║
║  │    - Threshold relaxation (+20%)                  │                   ║
║  │    - Threshold tightening (-20%)                  │                   ║
║  │    - Condition removal                            │                   ║
║  │    - RSI threshold shift (+5)                     │                   ║
║  │    - Hold time adjustment                         │                   ║
║  │    - Cooldown adjustment                          │                   ║
║  │    - Regime filter adjustment                     │                   ║
║  │  • Claude mutation (conservative, 1-3 changes)    │                   ║
║  │  • Viability pre-screening                        │                   ║
║  │  • Anti-clone detection (Jaccard distance)        │                   ║
║  │  • Mutation family taxonomy:                      │                   ║
║  │    repair, refinement, exploration,               │                   ║
║  │    aggression, simplification                     │                   ║
║  │  • Cost efficiency delta tracking                 │                   ║
║  │                                                   │                   ║
║  │  Combiner Agent (every 2h):                       │                   ║
║  │  • Tournament-select 2 parent strategies          │                   ║
║  │  • Claude creates hybrid offspring                │                   ║
║  │  • Records combination lineage                    │                   ║
║  │                                                   │                   ║
║  │  ★ Children re-enter pipeline as pending_code ★   │                   ║
║  └───────────────────────┬─────────────────────────┘                   ║
║                          │                                              ║
║                          ▼                                              ║
║  ┌─────────────────────────────────────────────────┐                   ║
║  │  DEPLOYMENT GOVERNOR (L7)                        │                   ║
║  │  • Tournament-select elite strategies for paper   │                   ║
║  │  • Modes: paper → shadow → partial_live → live   │                   ║
║  │  • Auto-approve paper, manual gate for live       │                   ║
║  │  • Regression detection → auto-rollback           │                   ║
║  │  • Walk-forward + overfitting validation gates    │                   ║
║  └───────────────────────┬─────────────────────────┘                   ║
║                          │                                              ║
║                          ▼                                              ║
║  ┌─────────────────────────────────────────────────┐                   ║
║  │  EXECUTION GATEWAY (L5) — SOLE EXECUTION PATH    │                   ║
║  │                                                   │                   ║
║  │  Flow:                                            │                   ║
║  │  Signal → Idempotency → Kill Switch →             │                   ║
║  │  Scout-Adaptive Sizing → Risk Approval →          │                   ║
║  │  Broker Submit (Alpaca/Binance) → Fill Poll →     │                   ║
║  │  Position Open → Lineage Record                   │                   ║
║  │                                                   │                   ║
║  │  Features:                                        │                   ║
║  │  • Distributed execution locks (Redis lease)      │                   ║
║  │  • Scout-aware: thin liquidity → 50% size cut    │                   ║
║  │  • Scout-aware: dangerous → 75% size cut         │                   ║
║  │  • Dynamic slippage widening                      │                   ║
║  │  • Recovery manager (startup reconciliation)      │                   ║
║  │  • Dead letter queue (failed orders)              │                   ║
║  │  • Partial fill handling                          │                   ║
║  │  • 3-retry submission with exponential backoff    │                   ║
║  └───────────────────────┬─────────────────────────┘                   ║
║                          │                                              ║
║          ┌───────────────┼───────────────────┐                         ║
║          ▼               ▼                   ▼                         ║
║  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐               ║
║  │ COPY TRADER  │ │ POSITIONS    │ │ DEAD LETTER       │               ║
║  │              │ │ MANAGER      │ │ MANAGER            │               ║
║  │ • Watch      │ │              │ │                    │               ║
║  │   leader     │ │ • Track open │ │ • Record failures  │               ║
║  │   fills      │ │ • P&L calc   │ │ • Classify cause   │               ║
║  │ • Mirror     │ │ • Reconcile  │ │ • Auto-retry       │               ║
║  │   to         │ │              │ │ • Resolution log   │               ║
║  │   followers  │ └──────────────┘ └──────────────────┘               ║
║  │ • Capital    │                                                       ║
║  │   allocation │                                                       ║
║  └──────────────┘                                                       ║
║                                                                         ║
║  ┌──────────────────────────────────────────────────────────────┐       ║
║  │  PORTFOLIO INTELLIGENCE (L6)                                  │       ║
║  │                                                                │       ║
║  │  PortfolioIntelligenceEngine (hourly):                         │       ║
║  │  • Covariance matrix across strategies                        │       ║
║  │  • Exposure clustering (archetype + symbol)                   │       ║
║  │  • Capital efficiency scoring                                 │       ║
║  │  • Mean-variance optimization (max 15% per strategy)          │       ║
║  │  • Ensemble survivability scoring                             │       ║
║  │  • Concentration risk (HHI)                                   │       ║
║  │  • Diversification score                                      │       ║
║  │                                                                │       ║
║  │  CapitalAllocator (every 30 min):                             │       ║
║  │  • Kelly fraction (conservative 15%)                          │       ║
║  │  • Volatility targeting (12% annual vol)                      │       ║
║  │  • Risk parity weighting                                      │       ║
║  │  • Regime-conditioned blending                                │       ║
║  │  • Weak organism penalty (70%) / dominant boost (150%)         │       ║
║  │  • Max 15% per strategy, max 40% per asset class              │       ║
║  │                                                                │       ║
║  │  AdvancedPortfolioOptimizer (every 30 min):                   │       ║
║  │  • Equal weight, Risk parity, CVaR, Robust optimization       │       ║
║  │  • Best method selected by diversification + stability        │       ║
║  └──────────────────────────────────────────────────────────────┘       ║
║                                                                         ║
║  ┌──────────────────────────────────────────────────────────────┐       ║
║  │  RISK MANAGEMENT (L4)                                         │       ║
║  │                                                                │       ║
║  │  KillSwitch:                                                   │       ║
║  │  • Redis + DB dual-state persistence                          │       ║
║  │  • FastAPI on port 8001 (/kill, /resume, /status)             │       ║
║  │  • Auto-activates on limit breaches                           │       ║
║  │  • Publishes to ALL channels on activation                    │       ║
║  │  • Slack alerting                                             │       ║
║  │                                                                │       ║
║  │  CapitalPreservationEngine (every 60s):                       │       ║
║  │  • 10% DD → warning, 15% → throttle (50%), 20% → freeze,    │       ║
║  │    25% → emergency deleverage                                 │       ║
║  │                                                                │       ║
║  │  SystemicRiskEngine (every 15 min):                           │       ║
║  │  • Contagion probability, fragility score                     │       ║
║  │  • Correlation regime, concentration risk (HHI)               │       ║
║  │                                                                │       ║
║  │  StressTestEngine (hourly):                                   │       ║
║  │  • 7 historical scenarios: 2008, COVID, Flash Crash,           │       ║
║  │    Liquidity Vacuum, Exchange Outage, Vol Explosion,           │       ║
║  │    Overnight Gap                                              │       ║
║  │  • Survival probability per scenario                          │       ║
║  └──────────────────────────────────────────────────────────────┘       ║
║                                                                         ║
║  ┌──────────────────────────────────────────────────────────────┐       ║
║  │  META-INTELLIGENCE (L7) — THE BRAIN                           │       ║
║  │                                                                │       ║
║  │  ScoutSynthesisEngine:                                         │       ║
║  │  • Aggregates 9+ scout sources                                │       ║
║  │  • Computes agreement/disagreement (Shannon entropy)           │       ║
║  │  • Confidence-weighted market narrative                        │       ║
║  │  • Deterministic or LLM-generated synthesis                   │       ║
║  │                                                                │       ║
║  │  HypothesisEngine:                                             │       ║
║  │  • Generates testable hypotheses from system observations     │       ║
║  │  • Lifecycle: active → weakening → dormant → invalidated      │       ║
║  │  • Confidence decay, evidence/contradiction tracking          │       ║
║  │  • Regime-conditioned reactivation                             │       ║
║  │                                                                │       ║
║  │  FailureAnalysisEngine:                                        │       ║
║  │  • Root cause analysis of strategy failures                   │       ║
║  │  • Systemic pattern detection                                 │       ║
║  │  • Governance recommendations                                 │       ║
║  │                                                                │       ║
║  │  ReplayEngine:                                                 │       ║
║  │  • Event-sourced hash chain verification                      │       ║
║  │  • Deterministic replay of any aggregate                      │       ║
║  │  • Integrity score computation                                 │       ║
║  │  • Divergence detection (replay vs live)                      │       ║
║  │                                                                │       ║
║  │  DeploymentGovernor:                                           │       ║
║  │  • Canary/shadow/paper/live deployment modes                  │       ║
║  │  • Walk-forward + overfitting validation gates                │       ║
║  │  • Regression detection → auto-rollback                       │       ║
║  │                                                                │       ║
║  │  + 20 more L7 meta-agents covering every aspect               │       ║
║  └──────────────────────────────────────────────────────────────┘       ║
║                                                                         ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 3. Layer L1 — Data Ingestion

### PolygonWebSocketAgent (Equities)
```
Polygon.io WS → Q/T/A events → Data Normalizer
  Q (Quote)  → market_data_l2 (bid/ask/size)
  T (Trade)  → order_flow (price/size/exchange)
  A (Agg)    → market_data_l1 (1m OHLCV bars)
```

### BinanceRestAgent (Crypto)
```
Binance REST API (polling)
  Every 5s  → trades → order_flow
  Every 2s  → depth  → market_data_l2
  Every 60s → klines → market_data_l1
```

### FeatureAgent
```
market_data_l1 (bars)
  → compute_features(df):
    • Returns, Log Returns
    • SMA(5, 20), EMA(12, 26)
    • RSI(14), MACD + Signal
    • Bollinger Bands (upper, lower)
    • Rolling Volatility (20)
    • VWAP
    • price_vs_vwap_pct     ← normalized cross-asset
    • ema_spread_pct        ← normalized cross-asset
    • relative_volume       ← normalized cross-asset
    • bollinger_band_position ← normalized cross-asset
    • volatility_regime     ← normalized cross-asset
    • trend_strength        ← normalized cross-asset
  → features table (wide format via materialized view)
```

---

## 4. Layer L2 — Strategy Generation

### Ideation Pipeline (5 parallel agents + V2 grammar path)
```
IdeatorAgent_0: equity + momentum     (temp=0.4)
IdeatorAgent_1: crypto + mean_reversion (temp=0.6)
IdeatorAgent_2: equity + breakout     (temp=0.7)
IdeatorAgent_3: crypto + trend_following (temp=0.85)
IdeatorAgent_4: equity + volatility_regime (temp=1.0)
```

### IdeatorAgentV2 — Grammar-Based Generation Path
```
V2 uses a DUAL-PATH architecture (deterministic grammar + LLM):

1. FEATURE DISTRIBUTION ANALYSIS:
   • Query actual feature percentiles (p10/p50/p90) from DB
   • Build per-feature distribution stats (min/max/mean/std)

2. THRESHOLD MEMORY (from winning strategies):
   • Compute weighted mean threshold per feature from validated strategies
   • Store as seed priors for new strategy generation

3. GRAMMAR-BASED CANDIDATE GENERATION:
   • Select templates from predefined grammar (archetype × feature pairs)
   • Resolve thresholds using _apply_threshold_memory() → clamp to realistic ranges
   • Apply _constrain_conditions_to_reality() → reject impossible thresholds

4. REGIME-WEIGHTED STRATEGY RANKING:
   • Fetch top strategies by regime affinity (RegimeSelector)
   • Feed regime rankings into Claude prompt as proven winners

5. LLM ADVISORY ENRICHMENT (optional):
   • Claude refines grammar-generated candidates
   • Adds hypothesis, reasoning, and metadata

V2 ADVANTAGE: Guarantees signal generation (grammar templates always produce
valid conditions) while LLM adds creative edge.
```

### Ideation Algorithm (V1 — Claude-first path)
```
1. BUILD CONTEXT:
   • Fetch latest features (live market snapshot)
   • Detect regime (RSI, vol, trend → regime label)
   • Fetch failed patterns (learn from mistakes)
   • Fetch successful patterns (emulate winners)
   • Fetch feature blacklist (proven losers)
   • Fetch recent names (dedup)
   • Fetch bar counts (calibrate trade frequency)

2. GENERATE STRATEGY:
   IF circuit breaker OPEN → use local templates
   ELSE → Claude Sonnet (3000 token budget, chain-of-thought):
     • Analyze market conditions
     • Reason about inefficiency
     • Design 2-4 entry/exit conditions
     • Validate against feature ranges
     • Output JSON spec

3. NORMALIZE:
   • Validate feature names (whitelist)
   • Reject raw price thresholds (close > 700)
   • Auto-round overprecise numbers
   • Compute strategy signature (MD5)
   • Deduplicate against existing strategies

4. SAVE:
   • Status: pending_code
   • Publish to STRATEGY_SIGNALS channel
```

### Mutation Algorithm
```
1. FETCH candidates (repair_candidate + research_candidate, limit 30)
2. TOURNAMENT SELECT 5 (tournament_size=7, by Sharpe)
3. FOR EACH candidate:
   a. STRUCTURAL FILTER:
      • entry_count ≥ 1, total_trades ≥ 1
   b. DETERMINISTIC MICRO-MUTATIONS (7-12 variants):
      • Economic: hold_time ±5, cooldown ±3, regime prune/expand
      • Structural: threshold relaxation (×0.8), tightening (×1.2)
      • Condition removal (most restrictive)
      • RSI threshold shift (+5)
   c. CLAUDE MUTATION (1 attempt):
      • Conservative: change 1-3 parameters
      • Allowed types: threshold, period, condition, exit, hold, cooldown, regime
   d. QUALITY GATES:
      • Viability score ≥ 0.15
      • Anti-clone check (Jaccard distance > 0.05)
      • Structural validation
   e. SAVE mutations as pending_code (re-enter pipeline)
   f. RECORD mutation lineage (parent → child, type, complexity delta)
```

---

## 5. Layer L3 — Backtesting & Validation

### Backtest Algorithm
```
1. LOAD generated code → exec() → find Strategy class
2. SELECT symbol (most bars available)
3. FETCH market_data_l1 + features_wide (joined on time)
4. VALIDATE features (≥50% of required features present)
5. RUN generate_signals(df) → signal series (1=entry, -1=exit, 0=hold)
6. IF zero entries → apply momentum fallback (close > prev close)
7. STATE MACHINE trade extraction:
   FLAT → ENTRY(1) → LONG(1) → EXIT(-1) → FLAT(0)
   Track: entry_time, exit_time, entry_price, exit_price, bars_held
8. COMPUTE DYNAMIC SLIPPAGE:
   vol_mult = rolling_volatility / median_vol
   volume_mult = 1 / relative_volume
   combined = sqrt(vol_mult × volume_mult) → clipped [0.5x, 3x]
9. SPLIT: Train(60%) | Test(20%) | Holdout(20%)
10. SHORT WINDOW MODE (<20k bars):
    composite = 0.30×return_score + 0.25×PF_score + 0.20×WR_score
              + 0.15×DD_score + 0.10×trade_count_score
11. INSTITUTIONAL MODE (>20k bars):
    Full annualized Sharpe, Sortino, Calmar, Profit Factor
12. REGIME SCORE: Count distinct regimes at entry points (0-1)
13. SAVE: backtest_results, update strategies.metrics
```

### Validation Algorithm
```
PHASE 1 — STRUCTURAL SANITY GATE:
  • entry_count ≥ 2 (dev: 1)
  • total_trades ≥ 2 (dev: 1)
  • entry_pct < 60% of bars
  • exit_pct < 95% of bars

PHASE 2 — PERFORMANCE TESTS (short window):
  • composite_score ≥ 10 (dev) / 20 (prod)
  • drawdown > -80%
  • trades ≥ 1 (dev) / 2 (prod)
  • win_rate ≥ 0.05 (dev) / 0.15 (prod)
  • profit_factor ≥ 0.05 (dev) / 0.30 (prod)

PHASE 3 — COST GOVERNANCE:
  • edge_per_trade_bps > min_edge for trade frequency
  • win_rate > frequency-dependent threshold
  • profit_factor > frequency-dependent threshold

PHASE 4 — TIER ASSIGNMENT:
  Dev/Staging:     elite≥60, validated≥35, research≥25, repair≥15
  Production:      elite≥90, validated≥70, research≥50, repair≥30
```

---

## 6. Layer L4 — Risk Management

### Kill Switch Cascade
```
LIMIT BREACH → PubSub → KillSwitch.run()
  → activate_kill_switch():
    1. Set risk_state.halted = TRUE (DB)
    2. HSET kill_switch:state (Redis)
    3. UPDATE agent_registry
    4. Publish to ALL channels
    5. Log CRITICAL
    6. POST Slack alert
```

### Capital Preservation Ladder
```
Drawdown  0-10%  → none
Drawdown 10-15%  → warning (exposure × 0.8)
Drawdown 15-20%  → throttle (exposure × 0.5)
Drawdown 20-25%  → freeze (no new positions)
Drawdown 25%+    → emergency deleverage + kill switch
```

---

## 7. Layer L5 — Execution

### Execution Flow (Sole Approved Path)
```
┌─────────────┐
│ Signal from  │
│ Strategy     │
└──────┬──────┘
       ▼
┌─────────────┐
│ Idempotency │  Check Redis set (order_key → processed)
│ Gate         │  Skip if already processed
└──────┬──────┘
       ▼
┌─────────────┐
│ Distributed  │  Redis SET NX with TTL lease
│ Lock         │  Only one instance can execute
└──────┬──────┘
       ▼
┌─────────────┐
│ Kill Switch  │  Check risk_state.halted (DB)
│ Check        │  Block if active
└──────┬──────┘
       ▼
┌─────────────┐
│ Scout-Aware  │  thin → qty × 0.5
│ Sizing       │  dangerous → qty × 0.25
└──────┬──────┘
       ▼
┌─────────────┐
│ Risk         │  RiskController.approve_trade()
│ Approval     │  Check position limits, exposure
└──────┬──────┘
       ▼
┌─────────────┐
│ Broker       │  AlpacaExecutor or BinanceExecutor
│ Submit       │  3 retries, exponential backoff
└──────┬──────┘
       ▼
┌─────────────┐
│ Fill Poll    │  Wait up to 30s for fill
│              │  Handle partial fills
└──────┬──────┘
       ▼
┌─────────────┐
│ Position     │  Open in positions table
│ Open         │  Write to paper_trades
└──────┬──────┘
       ▼
┌─────────────┐
│ Lineage      │  Event store record
│ Record       │  Trace ID for replay
└─────────────┘
```

---

## 8. Layer L6 — Portfolio Intelligence

### Capital Allocation Algorithm
```
1. KELLY FRACTION per strategy:
   kelly = avg_return / variance
   conservative = min(15%, kelly × 15%)

2. VOLATILITY TARGETING:
   weight = 0.12 / (strategy_std × regime_multiplier)

3. RISK PARITY:
   weight_i = (1/std_i) / Σ(1/std_j)

4. COMBINE (regime-conditioned blend):
   High vol:  20% Kelly + 40% Vol + 30% Parity + 10% Portfolio
   Low vol:   40% Kelly + 20% Vol + 20% Parity + 20% Portfolio
   Normal:    30% Kelly + 30% Vol + 25% Parity + 15% Portfolio

5. APPLY CONSTRAINTS:
   • Max 15% per strategy
   • Max 40% per asset class
   • Normalize to sum = 1.0

6. SELECTION ADJUSTMENTS:
   • Weak (≤20th percentile): weight × 0.70
   • Dominant (≥80th percentile): weight × 1.50
```

---

## 9. Layer L7 — Meta-Intelligence

### Scout Synthesis Algorithm
```
1. GATHER signals from 9+ sources
2. FETCH dynamic trust weights from source_performance_log
3. COMPUTE agreement metrics:
   • Map signals to directions: bullish=1, bearish=-1, neutral=0
   • Weighted mean direction
   • Agreement score = 1 - mean(|deviation from mean|)
   • Shannon entropy of disagreement
   • Consensus reliability = mean(trust_weights)
4. SYNTHESIZE narrative (deterministic or LLM):
   • risk_on / risk_off / transitioning / uncertain
   • Confidence = agreement × 0.8
5. PERSIST to scout_synthesis_log
```

### Hypothesis Lifecycle
```
                    ┌──────────┐
                    │ generated │
                    └─────┬────┘
                          ▼
                    ┌──────────┐
              ┌─────│  active   │─────┐
              │     └──────────┘     │
              ▼                      ▼
        ┌──────────┐          ┌──────────┐
        │weakening │          │confirmed │
        └─────┬────┘          └──────────┘
              ▼
        ┌──────────┐
        │ dormant  │←──── (reactivate if confidence↑)
        └─────┬────┘
              ▼
        ┌──────────────┐
        │ invalidated  │ (archived, never deleted)
        └──────────────┘

Confidence decay: -2% per 24h without confirmation
Evidence: +5% per supporting signal
Contradiction: -8% per contradicting signal
```

---

## 10. Scout Network

```
┌────────────────────────────────────────────────────────────────┐
│                     SCOUT NETWORK                               │
│                                                                  │
│  INTERNAL SCOUTS (market microstructure):                        │
│  ┌────────────┐  Every 60s   Volatility, Trend, Compression,   │
│  │RegimeScout │────────────→ Liquidity regime classification    │
│  └────────────┘              → market_regime_memory             │
│                                                                  │
│  ┌────────────┐  Every 120s  Spread, Depth imbalance,          │
│  │Liquidity   │────────────→ Slippage risk, Liquidity regime   │
│  │Scout       │              → liquidity_intelligence            │
│  └────────────┘                                                   │
│                                                                  │
│  ┌────────────┐  Every 300s  Pairwise correlations,            │
│  │Correlation │────────────→ Clustering, Spike detection       │
│  │Scout       │              → correlation_memory               │
│  └────────────┘                                                   │
│                                                                  │
│  ┌────────────┐  Every 120s  Fill quality, Slippage bps,       │
│  │Execution   │────────────→ Execution regime                   │
│  │Scout       │              → execution_intelligence            │
│  └────────────┘                                                   │
│                                                                  │
│  EXTERNAL SCOUTS (alternative data):                             │
│  ┌────────────┐  Every 30min Yahoo Finance RSS → sentiment      │
│  │NewsIntel   │────────────→ macro_news / asset_news            │
│  └────────────┘              → external_scout_memory             │
│                                                                  │
│  ┌────────────┐  Every 60min Reddit wsb/investing → sentiment   │
│  │RedditScout │────────────→ crowd_sentiment                    │
│  └────────────┘              → external_scout_memory             │
│                                                                  │
│  ┌────────────┐  Every 60min Discord trading channels           │
│  │DiscordScout│────────────→ community_sentiment                │
│  └────────────┘              → external_scout_memory             │
│                                                                  │
│  ┌────────────┐  Every 2h    YouTube finance videos             │
│  │YouTubeScout│────────────→ creator_sentiment                  │
│  └────────────┘              → external_scout_memory             │
│                                                                  │
│  ┌────────────┐  Every 4h    Podcast transcripts                │
│  │PodcastScout│────────────→ expert_sentiment                   │
│  └────────────┘              → external_scout_memory             │
│                                                                  │
│  CROSS-CUTTING:                                                  │
│  ┌─────────────────────┐  Dynamic trust scoring                 │
│  │SourceReliability     │  per source based on                  │
│  │Engine                │  prediction accuracy                  │
│  └─────────────────────┘                                        │
│                                                                  │
│  ┌─────────────────────┐  Validates external                    │
│  │HypothesisValidation  │  scout claims against                 │
│  │Engine                │  market outcomes                      │
│  └─────────────────────┘                                        │
│                                                                  │
│  ALL scouts feed into ScoutSynthesisEngine which produces        │
│  a unified market narrative consumed by ALL other layers.        │
└────────────────────────────────────────────────────────────────┘
```

---

## 11. Evolutionary Engine

### Strategy Lifecycle State Machine
```
                         ┌─────────────┐
                         │  GENERATED   │ ← Ideator
                         │ pending_code │
                         └──────┬──────┘
                                │ CoderAgent
                                ▼
                         ┌─────────────┐
                         │   CODED      │
                         │pending_back- │
                         │   test       │
                         └──────┬──────┘
                                │ BacktestRunner
                                ▼
                         ┌─────────────┐
                    ┌────│  BACKTESTED  │────┐
                    │    │pending_valid-│    │
                    │    │   ation      │    │
                    │    └──────────────┘    │
                    │                        │
            ValidatorAgent              Backtest Failed
                    │                        │
         ┌──────────┼──────────┐             ▼
         ▼          ▼          ▼      ┌──────────────┐
  ┌──────────┐ ┌──────────┐ ┌──────┐ │code_failed /  │
  │  elite   │ │validated │ │repair│ │backtest_failed│
  │          │ │          │ │_cand.│ └──────┬───────┘
  └────┬─────┘ └────┬─────┘ └──┬───┘        │
       │             │          │             │
       │             │          ▼             │
       │             │   ┌──────────┐         │
       │             │   │ MUTATION │─────────┘
       │             │   │ (re-enter│  (children get
       │             │   │ pipeline)│   pending_code)
       │             │   └──────────┘
       │             │
       ▼             ▼
  ┌──────────────────────┐
  │  DEPLOYMENT GOVERNOR  │
  │                       │
  │  paper → shadow →     │
  │  partial_live → live  │
  │                       │
  │  Regression detected  │
  │  → auto-rollback      │
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐     ┌────────────────┐
  │  EXECUTION GATEWAY    │────→│  LIVE TRADING   │
  │  (paper/live)         │     │                 │
  └──────────────────────┘     └────────┬───────┘
                                        │
                              ┌─────────┼─────────┐
                              ▼         ▼         ▼
                         ┌────────┐ ┌────────┐ ┌────────┐
                         │PERFORM │ │DRIFT   │ │RETIRE  │
                         │WELL    │ │DETECTED│ │MENT    │
                         │        │ │        │ │        │
                         │Boost   │ │Rebalance│ │Archive │
                         │weight  │ │or kill │ │        │
                         └────────┘ └────────┘ └────────┘
```

---

## 12. Governance & Replay

### Event Sourcing
```
Every action emits an immutable event:
  event_id | event_type | trace_id | aggregate_id | data |
  hash_prev | hash_self | sequence | created_at

Hash chain: SHA-256(content) → hash_self
            hash_prev links to previous event in aggregate
            → Tamper-evident audit trail
```

### Replay Integrity
```
1. Load all events for an aggregate
2. Verify hash chain: hash_prev[i] == hash_self[i-1]
3. Verify self-hash: SHA-256(content) == hash_self
4. Score: valid_aggregates / total_aggregates × 100
5. Persist to replay_integrity table
```

---

## 13. Data Architecture

### Core Tables (40+)
```
MARKET DATA:
  market_data_l1     — 1m OHLCV bars (TimescaleDB hypertable)
  market_data_l2     — Quotes, orderbook snapshots
  order_flow         — Individual trade prints
  features           — Long-format feature values
  features_wide      — Materialized view (wide format)

STRATEGY LIFECYCLE:
  strategies         — Master strategy table (spec, code, status, metrics)
  backtest_results   — Backtest output per strategy
  lifecycle_events   — Stage/status transitions per trace
  deployment_governance — Deployment proposals and approvals

EXECUTION:
  paper_trades       — Simulated/paper trade log
  positions          — Open position tracking
  execution_log      — Full execution audit trail
  execution_dead_letter — Failed order queue
  copy_execution_log — Copy trade mirror log

SCOUT INTELLIGENCE:
  market_regime_memory    — Regime classifications
  liquidity_intelligence  — Liquidity assessments
  correlation_memory      — Correlation analysis
  execution_intelligence  — Execution quality metrics
  external_scout_memory   — Reddit/Discord/News/YouTube/Podcast
  scout_signals           — Internal scout signal log

META-INTELLIGENCE:
  event_store             — Immutable event log (hash-chained)
  audit_ledger            — Full audit trail
  hypothesis_registry     — Research hypotheses with lifecycle
  failure_analysis        — Root cause analysis records
  pattern_memory          — Detected strategy patterns
  mutation_memory         — Parent-child mutation tracking
  mutation_families       — Mutation family performance
  dominant_organisms      — Dominant strategy tracking
  regime_specialization   — Per-strategy regime affinity

PORTFOLIO:
  portfolio_intelligence  — Covariance, clustering, allocations
  capital_allocation      — Target capital weights
  portfolio_evolution_log — Evolution tracking
  capital_preservation_state — Drawdown protection state

RISK:
  risk_state              — Kill switch state (halted/reason)
  systemic_risk           — Systemic risk assessments
  stress_test_results     — Historical scenario stress tests

GOVERNANCE:
  prompt_templates        — Evolving prompt templates
  mutation_policy_state   — Learned mutation policies
  agent_governance_state  — Agent performance assessments
  replay_integrity        — Hash chain integrity scores
  monitoring_metrics      — System health metrics
  anomaly_observations    — Detected anomalies
  source_performance_log  — Scout reliability tracking
```

---

## 14. Complete State Machine

### Strategy Status Flow
```
pending_code → pending_backtest → pending_validation
  → elite / validated / research_candidate / repair_candidate
  → failed_validation / code_failed / backtest_failed

repair_candidate → (mutator_agent) → pending_code (★ EVOLUTIONARY CYCLE ★)
research_candidate → (mutator_agent) → pending_code (★ EVOLUTIONARY CYCLE ★)

The MutatorAgent is the EVOLUTIONARY ENGINE:
  • Polls for repair_candidate + research_candidate every 5 minutes
  • Tournament-selects 5 candidates from 30
  • Generates 7-12 deterministic micro-mutations + 1 Claude mutation
  • Children get status=pending_code → re-enter coder → backtest → validator
  • This creates an INFINITE IMPROVEMENT LOOP until strategies retire

elite/validated → (deployment_governor via tournament select) → paper → shadow → partial_live → live
live → (regression detected) → rolled_back → paper
live → (strategy_retirement_engine) → retired
live → (drift_detection_engine) → monitored → possible rollback
```

### Order Execution State Machine
```
SIGNAL_RECEIVED → RISK_APPROVED → BROKER_ACK → FILLED
                ↘ KILL_SWITCH_BLOCKED
                ↘ RISK_REJECTED
                                             ↘ PARTIALLY_FILLED → DEAD_LETTER
                                  BROKER_ACK ↘ FILL_TIMEOUT → CANCELLED
                                            ↘ DEAD_LETTER (unhandled exception)
```

---

## 15. Agent Communication Map

```
Redis PubSub Channels:
  market_data         — L1 → L2, L3
  strategy_signals    — L2 → L3, L5
  risk_alerts         — L4 → all
  execution_fills     — L5 → CopyTrader
  system_events       — all → dashboard
  portfolio_intelligence_updates — L6 → all
  capital_allocation_updates     — L6 → L5

Redis Keys:
  agent:{id}          — Heartbeat (TTL 30s)
  kill_switch:state   — Kill switch status
  capital:freeze      — Capital freeze flag
  capital:throttle    — Capital throttle flag
  scout:*_summary     — Cached scout summaries
  metrics:{id}        — Agent metrics (TTL 5min)
  copy:processed_*    — Idempotency sets
  order_lock:*        — Distributed execution locks
```

---

## 16. Key Algorithms Reference

### Composite Short Window Score
```python
score = (
    0.30 × normalize(total_return) +    # Return component
    0.25 × normalize(profit_factor) +   # Edge quality
    0.20 × normalize(win_rate) +        # Consistency
    0.15 × normalize(max_drawdown) +    # Capital preservation
    0.10 × normalize(trade_count)       # Statistical significance
) × 100
```

### Tournament Selection
```python
for _ in range(n_select):
    tournament = random.sample(candidates, tournament_size)
    winner = max(tournament, key=fitness_score)
    selected.append(winner)
```

### Cost Governance Thresholds
```
Trades < 10:    min_edge = 0.5 × round_trip_cost
Trades 10-50:   min_edge = 1.5 × round_trip_cost
Trades 50-100:  min_edge = 2.5 × round_trip_cost
Trades > 100:   min_edge = 4.0 × round_trip_cost
```

### Dynamic Slippage
```python
vol_mult = rolling_volatility / median_volatility
volume_mult = 1.0 / relative_volume
combined = sqrt(vol_mult × volume_mult)
slippage_multiplier = clip(combined, 0.5, 3.0)
```

### Scout-Aware Validation Adjustment
```
dangerous liquidity  → thresholds × 0.7
thin liquidity       → thresholds × 0.85
unstable execution   → thresholds × 0.6
stressed execution   → thresholds × 0.8
panic correlation    → thresholds × 0.75
```

---

*Generated by comprehensive analysis of the ATLAS codebase.*
*Last updated: June 1, 2026*
*Total agents: 70+ across 7 layers + scout network*
*Total database tables: 40+*
*Total API endpoints: 30+*
