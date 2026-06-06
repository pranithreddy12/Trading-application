# ATLAS — Demo Walkthrough

## Overview

This walkthrough demonstrates ATLAS as a fully autonomous adaptive trading ecosystem. Total demo time: **~15 minutes**.

---

## Part 1: Architecture Overview (2 min)

Navigate to **`docs/architecture.md`** — show the layered architecture:

- **L1-L2**: Data ingestion → Strategy ideation/mutation
- **L3**: Backtesting & validation
- **L4**: Portfolio intelligence & risk
- **L5**: Execution with dead-letter recovery
- **L6**: Governance, replay, audit
- **L7**: Scouts, meta-learning, specialization

**Key point**: Each layer is independently operational and collectively forms a closed-loop autonomous system.

---

## Part 2: Dashboard Visibility (3 min)

Open **`http://localhost:8000/dashboard/`**

Show:
- **Active organisms** — live count and lifecycle status
- **Replay integrity** — should read 1.0 (perfect)
- **Portfolio allocation** — diversification and concentration
- **Scout activity** — active scouts and signal freshness
- **Mutation families** — lineage tree and performance
- **Dead-letter queue** — should be near-zero

---

## Part 3: Live Coverage Demo (5 min)

```bash
python scripts/phase34_coverage_demo.py --duration-minutes 10
```

Observe:
1. **Ingestion**: Market data flows in
2. **Ideation → Mutation**: New strategies generated
3. **Backtest + Validation**: Strategies scored and filtered
4. **Portfolio allocation**: Capital assigned
5. **Execution**: Trades (simulated) executed
6. **Attribution**: Scout influence recorded
7. **Replay**: Events persisted with hash chain
8. **Retirement**: Weak organisms culled

**Key point**: Full autonomous circulation — no human intervention needed.

---

## Part 4: Key Metrics (3 min)

Show from output:
| Metric | Target | Typical |
|--------|--------|---------|
| Replay integrity | 1.000 | 1.000 |
| Adaptive Quality | >0.85 | 0.95+ |
| Diversification | >0.30 | 0.40-0.60 |
| Drawdown resilience | >0.70 | 0.85+ |
| Recovery quality | >0.60 | 0.90+ |
| Capital migration | >10% | 20-40% |

---

## Part 5: Evolutionary Intelligence (2 min)

**Navigate to `docs/mutation_evolution.md`**

Cover:
- Mutation families driving improvement
- Dominant organisms emerging
- Regime specialization in action
- Scout divergence creating signal diversity

**Key point**: Later-generation organisms consistently outperform early generations.

---

## Script Output Reference

### Phase 34 Demo Output Legend

| Tag | Meaning |
|-----|---------|
| `AQ` | Adaptive Quality score |
| `SQ` | Specialization Quality |
| `AL` | Allocation Quality |
| `ES` | Evolutionary Selection |
| `LH` | Long-Horizon Survivability |
| `orgs` | Active organisms |
| `replay` | Replay integrity |
| `recovery` | Recovery quality |
| `drawdown` | Drawdown resilience |
| `div` | Diversification score |
