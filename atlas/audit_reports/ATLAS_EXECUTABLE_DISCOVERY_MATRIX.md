# ATLAS Executable Discovery Matrix
**Generated:** 2026-05-18 | **Total Files:** 168

## A. CORE RUNTIME

### A.1 L1 Data Agents
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 1 | `agents/l1_data/binance_ws_agent.py` | `async def main()` | LIVE DATA | market_data_l1,l2,order_flow | Pub/Sub | LIVE |
| 2 | `agents/l1_data/polygon_rest_agent.py` | `async def main()` | LIVE DATA | market_data_l1 | Pub/Sub | LIVE |
| 3 | `agents/l1_data/polygon_ws_agent.py` | `async def main()` | LIVE DATA | market_data_l1,l2,order_flow | Pub/Sub | LIVE |
| 4 | `agents/l1_data/feature_agent.py` | `async def main()` | FEATURE ENGINE | features,features_wide | Pub/Sub | WRITE |
| 5 | `agents/l1_data/historical_backfill.py` | `def main()` | BATCH | market_data_l1 | None | WRITE |
| 6 | `agents/l1_data/binance_examples.py` | `async def main()` | EXAMPLE | market_data_l1 | Pub/Sub | SAFE |
| 7 | `agents/l1_data/examples.py` | `async def main()` | EXAMPLE | market_data_l1 | Pub/Sub | SAFE |

### A.2 L2 Strategy Agents
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 8 | `agents/l2_strategy/ideator_agent.py` | `async def main()` | STRATEGY GEN | strategies,lifecycle_events | Pub/Sub | WRITE |
| 9 | `agents/l2_strategy/ideator_agent_v2.py` | `async def main()` | STRATEGY GEN | strategies,pattern_memory | Pub/Sub | WRITE |
| 10 | `agents/l2_strategy/coder_agent.py` | `async def main()` | CODE GEN | strategies | Pub/Sub | WRITE |
| 11 | `agents/l2_strategy/combiner_agent.py` | class method | HYBRID GEN | strategies,combination_memory | Pub/Sub | WRITE |
| 12 | `agents/l2_strategy/mutator_agent.py` | `async def main()` | MUTATION | strategies,mutation_memory | Pub/Sub | WRITE |
| 13 | `agents/l2_strategy/mutation_pattern_agent.py` | `async def main()` | PATTERN | mutation_memory | None | SAFE |
| 14 | `agents/l2_strategy/condition_parser.py` | Library | PARSER | None | None | SAFE |
| 15 | `agents/l2_strategy/viability_score.py` | Library | SCORING | None | None | SAFE |
| 16 | `agents/l2_strategy/strategy_base.py` | Library | BASE CLASS | None | None | SAFE |
| 17 | `agents/l2_strategy/strategy_normalizer.py` | Library | NORMALIZER | None | None | SAFE |
| 18 | `agents/l2_strategy/mutation_metrics.py` | Library | METRICS | None | None | SAFE |
| 19 | `agents/l2_strategy/test_fix.py` | Unknown | TEST FIX | Unknown | None | SAFE |

### A.3 L3 Backtest Agents
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 20 | `agents/l3_backtest/backtest_runner.py` | `async def main()` | BACKTEST | backtest_results,backtest_trades | Pub/Sub | WRITE |
| 21 | `agents/l3_backtest/validator_agent.py` | `async def main()` | VALIDATION | strategies,backtest_results | None | WRITE |
| 22 | `agents/l3_backtest/short_window_evaluator.py` | Library | TEMPORAL | backtest_results | None | SAFE |

### A.4 L4 Risk
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 23 | `agents/l4_risk/kill_switch.py` | Library | SAFETY | None | Redis keys | WRITE |
| 24 | `agents/l4_risk/risk_controller.py` | Library | RISK MGMT | paper_trades | Pub/Sub | WRITE |

### A.5 L5 Execution
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 25 | `agents/l5_execution/alpaca_executor.py` | Library | BROKER | paper_trades,positions | Redis | LIVE |
| 26 | `agents/l5_execution/binance_executor.py` | Library | BROKER | paper_trades,positions | Redis | LIVE |
| 27 | `agents/l5_execution/broker_adapter.py` | Library | ABSTRACT | None | None | SAFE |
| 28 | `agents/l5_execution/copy_trader.py` | `async def main()` | COPY TRADE | copy tables | Pub/Sub | WRITE |
| 29 | `agents/l5_execution/dead_letter.py` | Library | DLQ | execution_dead_letter | None | WRITE |
| 30 | `agents/l5_execution/execution_gateway.py` | Library | GATEWAY | execution_log | None | WRITE |
| 31 | `agents/l5_execution/order_tracker.py` | Library | TRACKING | paper_trades | None | WRITE |
| 32 | `agents/l5_execution/position_manager.py` | Library | POSITIONS | positions | None | WRITE |
| 33 | `agents/l5_execution/recovery_manager.py` | Library | RECOVERY | execution_log,dead_letter | None | WRITE |

### A.6 L7 Meta
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 34 | `agents/l7_meta/self_improvement_agent.py` | Library | META LEARN | intelligence_briefs | Pub/Sub | WRITE |
| 35 | `agents/l7_meta/pattern_agent.py` | Library | PATTERNS | pattern_memory,strategies | Pub/Sub | WRITE |
| 36 | `agents/l7_meta/intelligence_brief_agent.py` | Library | BRIEFS | intelligence_briefs | Pub/Sub | WRITE |

### A.7 Core
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 37 | `core/agent_base.py` | Library | BASE CLASS | agent_registry | Redis | SAFE |
| 38 | `core/agent_registry.py` | Library | REGISTRY | agent_registry | None | SAFE |
| 39 | `core/claude_client.py` | Library | LLM CLIENT | None | None | SAFE |
| 40 | `core/event_lineage.py` | Library | LINEAGE | lifecycle_events | None | WRITE |
| 41 | `core/execution_cost_intelligence.py` | Library | COST | None | None | SAFE |
| 42 | `core/messaging.py` | Library | MESSAGING | None | Redis | SAFE |
| 43 | `core/meta_orchestrator.py` | Library | ORCH | None | None | SAFE |
| 44 | `core/score_contract.py` | Library | CONTRACT | None | None | SAFE |

### A.8 API
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 45 | `api/main.py` | uvicorn | API SERVER | ALL TABLES | Redis | WRITE |
| 46 | `api/day4_api.py` | uvicorn | LEGACY API | ALL TABLES | Redis | WRITE |
| 47 | `api/contracts/manifest.py` | Library | CONTRACT | None | None | SAFE |
| 48 | `api/contracts/validator.py` | Library | CONTRACT | None | None | SAFE |
| 49 | `api/middleware/auth_middleware.py` | Library | AUTH | api_keys | None | SAFE |
| 50 | `api/routes/copy_status.py` | Library | ROUTE | copy_execution_log | None | SAFE |
| 51 | `api/services/auth_service.py` | Library | SERVICE | api_keys | None | WRITE |
| 52 | `api/services/copy_service.py` | Library | SERVICE | copy tables | None | WRITE |
| 53 | `api/services/health_service.py` | Library | SERVICE | agent_registry | None | SAFE |
| 54 | `api/services/rate_limit_service.py` | Library | SERVICE | api_request_audit | None | WRITE |
| 55 | `api/services/risk_service.py` | Library | SERVICE | paper_trades | None | SAFE |

### A.9 Dashboard
| # | Path | Entry Point | Category | DB Touchpoints | Redis | Risk |
|---|------|-------------|----------|----------------|-------|------|
| 56 | `dashboard/router.py` | Library | DASHBOARD | strategies | None | SAFE |

