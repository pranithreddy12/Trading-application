# PHASE 28G — ATTRIBUTION REPAIR REPORT

## Overview
The L7 `EconomicAttributionEngine` was failing to correlate scout influence to PnL due to a schema drift bug. The system was attempting to select `br.total_return` as a direct column from the `backtest_results` view.

## Corrective Actions
1. **JSONB Extraction**: Verified that `total_return` is serialized inside the `results` JSONB column rather than existing as a standalone numeric column.
2. **SQL Update**: The `LATERAL` join inside `_compute_and_persist_attribution` was updated from:
   `SELECT total_return`
   to:
   `SELECT (results->>'total_return')::numeric as total_return`
3. **Execution**: The attribution flow now successfully joins `scout_influence_log` records with corresponding `backtest_results` to persist true economic attribution data to `scout_economic_attribution`.

## Result
Scout telemetry is now successfully coupled to raw economic performance, allowing ATLAS to compute Sharpe, Win Rate, and Survival survival metrics per Scout dynamically.
