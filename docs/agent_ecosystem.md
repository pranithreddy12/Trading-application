# ATLAS — Agent Ecosystem Overview

ATLAS operates **70+ agent instances** across 7 layers, organized by specialization.

---

## Layer 1 — Data Ingestion & Features

| Agent | Role |
|-------|------|
| BinanceWebSocketAgent | Real-time crypto market data (trades, depth) |
| BinanceRestAgent | REST-based crypto data fallback |
| PolygonWebSocketAgent | Real-time equity data (quotes, trades, aggregates) |
| PolygonRestAgent | REST-based equity data fallback |
| FeatureAgent | Technical indicator computation |
| PatternRecognitionEngine | Market pattern identification |

---

## Layer 2 — Strategy Generation

| Agent | Role |
|-------|------|
| IdeatorAgent | Strategy idea generation from scout signals |
| IdeatorAgentV2 | Enhanced generation with regime conditioning |
| MutatorAgent | Evolutionary strategy mutation |
| CoderAgent | Strategy code generation |
| CombinerAgent | Strategy combination and blending |

---

## Layer 3 — Backtesting & Validation

| Agent | Role |
|-------|------|
| BacktestRunner | Full historical backtesting engine |
| ValidatorAgent | Strategy validation & scoring |
| WalkForwardAnalyzer | Temporal consistency verification |
| MonteCarloSimulator | Probabilistic outcome simulation |
| OverfittingDetector | Parameter stability analysis |
| RegimeValidator | Cross-regime robustness checking |
| CostStressTester | Transaction cost sensitivity |

---

## Layer 4 — Risk & Capital Management

| Agent | Role |
|-------|------|
| CapitalAllocator | Optimal capital distribution |
| PortfolioIntelligenceEngine | Portfolio risk/return assessment |
| PortfolioEvolutionPressure | Adaptive capital migration |
| PortfolioOptimizer | Mean-variance / risk-parity optimization |
| SystemicRiskEngine | Contagion & systemic risk monitoring |
| StressTestEngine | Scenario-based stress testing |
| CapitalPreservationEngine | Drawdown protection |
| KillSwitch | Emergency system halt |

---

## Layer 5 — Execution

| Agent | Role |
|-------|------|
| ExecutionGateway | Unified order routing |
| CopyTraderAgent | Leader-follower replication |
| CopyDriftEngine | Follower drift detection |
| CopyFailoverManager | Failover between followers |
| CopyCapitalAllocator | Follower capital management |
| ExecutionRealismEngine | Fill/slippage/latency simulation |
| PositionManager | Position tracking and P&L |
| OrderTracker | Order lifecycle tracking |
| DeadLetterManager | Failed order recovery |
| RecoveryManager | Startup reconciliation |
| PositionReconciliationEngine | Broker position alignment |
| BinanceExecutor | Binance broker adapter |
| AlpacaExecutor | Alpaca broker adapter |
| BrokerSandbox | Safe broker simulation |

---

## Layer 6 — Governance & Replay

| Agent | Role |
|-------|------|
| EventStore | Immutable append-only event log |
| AuditLedger | Sequential audit trail |
| ReplayEngine | Deterministic replay with hash verification |
| DeploymentGovernor | Strategy deployment approval |
| LeaderGovernanceEngine | Copy trading governance |

---

## Layer 7 — Meta-Learning & Evolution

| Agent | Role |
|-------|------|
| DominantOrganismTracker | Identifies elite strategies |
| MutationLineageTracker | Tracks evolutionary lineage trees |
| MutationPolicyEngine | Learns optimal mutation strategies |
| RegimeSpecializationEngine | Profiles regime-conditioned fitness |
| ScoutDivergenceEngine | Measures scout signal divergence |
| ScoutSynthesisEngine | Aggregates multi-scout intelligence |
| EconomicEfficiencyEngine | Economic performance analysis |
| EconomicAttributionEngine | Credits scout influence on P&L |
| FeatureImportanceEngine | Ranks feature predictive power |
| HypothesisEngine | Forms/testable hypotheses |
| StrategyRetirementEngine | Retires underperforming strategies |
| SystemHealthEngine | Composite system health scoring |
| EntropyGovernanceEngine | Manages exploration vs exploitation |
| DriftDetectionEngine | Detects feature/strategy drift |
| FailureAnalysisEngine | Root cause analysis of failures |

## Scout Network (12+ sources)

CompetitionScout, CorrelationScout, DiscordScout, ExecutionScout,
HypothesisValidationEngine, LiquidityScout, NewsIntelligenceEngine,
PodcastScout, RedditScout, RegimeScout, SourceReliabilityEngine,
YouTubeScout
