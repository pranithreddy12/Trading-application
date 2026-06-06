# ATLAS — Mutation & Evolution

ATLAS uses **evolutionary strategy generation** where strategies compete, mutate, and are selected by economic fitness — analogous to natural selection.

---

## Evolutionary Lifecycle

```
                    ┌─────────────────────────┐
                    │   Seed Strategies (L2)   │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │     Mutation (L2)        │
                    │  Parameter tweaks        │
                    │  Code variations         │
                    │  Strategy blending       │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   Backtest (L3)          │
                    │  Score by composite      │
                    │  fitness                 │
                    └───────────┬─────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
        ┌─────────────────┐          ┌─────────────────┐
        │   Elite / Live   │          │  Rejected / Dead │
        │  (top fitness)   │          │  (low fitness)   │
        └────────┬────────┘          └─────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │   Mutate again   │
        │  (next gen)      │
        └─────────────────┘
```

---

## Mutation Types

| Type | Description |
|------|-------------|
| **Parameter** | Adjust indicator periods, thresholds, stop-loss levels |
| **Code** | Modify strategy logic (entry/exit conditions) |
| **Blend** | Combine two strategies into hybrid |
| **Regime-adaptive** | Add regime detection and conditional logic |
| **Risk profile** | Vary position sizing, risk limits |

---

## Lineage Tracking

The **MutationLineageTracker** builds evolutionary trees:

```
Strategy A (parent)
├── Mutation A1 (child)
│   ├── Mutation A1a
│   └── Mutation A1b
├── Mutation A2
│   └── Mutation A2a (dominant — highest fitness)
└── Mutation A3 (retired — low fitness)
```

**Key metrics tracked:**
- Sharpe delta (improvement over parent)
- Score delta (fitness change)
- Survival rate per mutation type
- Lineage depth and breadth

---

## Selection Pressure

| Mechanism | Effect |
|-----------|--------|
| **Composite fitness** | Strategies ranked by weighted: Sharpe, Sortino, Calmar, expectancy |
| **Retirement** | Bottom 20% by fitness retired automatically |
| **Capital migration** | Capital shifted from weak to strong strategies |
| **Dominant boost** | Top strategies receive amplified capital allocation |
| **Scout influence** | Scout-aligned strategies favored |

---

## Regime Specialization

Strategies evolve **regime-specific expertise**:

| Regime | Characteristics |
|--------|----------------|
| **Bull** | Long-biased, momentum-following |
| **Bear** | Short-biased, mean-reversion |
| **Ranging** | Mean-reversion, range-bound |
| **High volatility** | Wide stops, trend-following |
| **Low liquidity** | Smaller positions, wider spreads |

The **RegimeSpecializationEngine** profiles each strategy across regimes and identifies organisms suited to specific market conditions.

---

## Scout-Driven Evolution

The **scout network** influences evolution by:
1. Detecting regime shifts (RegimeScout)
2. Assessing liquidity conditions (LiquidityScout)
3. Monitoring execution quality (ExecutionScout)
4. Tracking sentiment (RedditScout, NewsIntelligence)
5. Identifying correlations (CorrelationScout)

High-alignment scouts get higher weight in ideation and attribution.
