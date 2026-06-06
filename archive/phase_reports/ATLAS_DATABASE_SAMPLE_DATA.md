# ATLAS Database — Complete Sample Data Dump

> **Generated:** Automated dump from PostgreSQL TimescaleDB container
> **Database:** `atlas` | **Container:** `atlas_timescaledb`
> **Format:** Expanded display — 2 sample rows per table with column details

---

## 1. `advanced_portfolio_optimization`

- **Row count:** 0
- **Columns (7):**
  - `id (text)`
  - `optimized_at (timestamp with time zone)`
  - `method_used (text)`
  - `n_strategies (integer)`
  - `final_allocations (jsonb)`
  - `method_scores (jsonb)`
  - `details (jsonb)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 2. `agent_governance_state`

- **Row count:** 164
- **Columns (5):**
  - `id (text)`
  - `assessed_at (timestamp with time zone)`
  - `n_agents_assessed (integer)`
  - `agent_scores (jsonb)`
  - `throttled_agents (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                | 59318f9085fb4641
assessed_at       | 2026-05-22 07:13:24.679132+00
n_agents_assessed | 69
agent_scores      | {"CoderAgent": 0.748, "RegimeScout": 0.5, "MutatorAgent": 0.5, "ReplayEngine": 0.5, "IdeatorV2_0_R": 0.9849999999999999, "BacktestRunner": 0.5, "ExecutionScout": 0.5, "LiquidityScout": 0.5, "ValidatorAgent": 0.5, "RegimeValidator": 0.5, "CapitalAllocator": 0.5, "CorrelationScout": 0.5, "CostStressTester": 0.5, "ExecutionGateway": 0.5, "StressTestEngine": 0.5, "DeploymentGoverno... [TRUNCATED]
throttled_agents  | []
-[ RECORD 2 ]-----+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                | e0a5ea4b59b44115
assessed_at       | 2026-05-22 07:21:39.355686+00
n_agents_assessed | 72
agent_scores      | {"CoderAgent": 0.862, "RegimeScout": 0.5, "MutatorAgent": 0.5, "ReplayEngine": 0.5, "IdeatorV2_0_R": 0.9909999999999999, "BacktestRunner": 0.5, "ExecutionScout": 0.5, "LiquidityScout": 0.5, "ValidatorAgent": 0.5, "RegimeValidator": 0.5, "CapitalAllocator": 0.5, "CorrelationScout": 0.5, "CostStressTester": 0.5, "ExecutionGateway": 0.5, "StressTestEngine": 0.5, "DeploymentGoverno... [TRUNCATED]
throttled_agents  | []


```

---

## 3. `agent_registry`

- **Row count:** 0
- **Columns (9):**
  - `id (uuid)`
  - `name (text)`
  - `type (text)`
  - `layer (text)`
  - `status (text)`
  - `pid (integer)`
  - `last_heartbeat (timestamp with time zone)`
  - `created_at (timestamp with time zone)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 4. `anomaly_observations`

- **Row count:** 0
- **Columns (5):**
  - `id (text)`
  - `observed_at (timestamp with time zone)`
  - `n_anomalies (integer)`
  - `anomalies (jsonb)`
  - `severity (numeric)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 5. `api_keys`

- **Row count:** 133
- **Columns (17):**
  - `id (uuid)`
  - `key_hash (character varying)`
  - `key_prefix (character varying)`
  - `user_id (character varying)`
  - `team_id (uuid)`
  - `role (character varying)`
  - `scopes (jsonb)`
  - `rate_limit_per_min (integer)`
  - `is_active (boolean)`
  - `created_at (timestamp with time zone)`
  - `created_by (character varying)`
  - `last_used_at (timestamp with time zone)`
  - `revoked_at (timestamp with time zone)`
  - `revoke_reason (character varying)`
  - `revoked_by (character varying)`
  - `description (character varying)`
  - `expires_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]------+-------------------------------------------------------------
id                 | 28995a27-259b-4ee3-960a-e64e2e9b5f8b
key_hash           | $2b$12$eaZGPPe3qWiY3W7t0AmOaeGOjWuR.M0tGXvPJ1v9wQCNDpygAHkcq
key_prefix         | atlas_
user_id            | rate_limit_test
team_id            |
role               | read_only
scopes             | []
rate_limit_per_min | 2
is_active          | t
created_at         | 2026-05-17 07:39:51.627399+00
created_by         | live_validation
last_used_at       |
revoked_at         | 2026-05-17 07:40:03.512511+00
revoke_reason      | Rate limit test complete
revoked_by         | live_validation
description        | Rate limit test key (2/min)
expires_at         | 2026-05-18 02:09:51.626191+00
-[ RECORD 2 ]------+-------------------------------------------------------------
id                 | cc90a095-40bd-4952-ba53-f1eff8170b3d
key_hash           | $2b$12$tc0XWobXIvFhehDuZMOKV.GghxQyVZFhYMhsXdzVVFahPYArR1qEC
key_prefix         | atlas_
user_id            | revoked_test
team_id            |
role               | read_only
scopes             | []
rate_limit_per_min | 100
is_active          | t
created_at         | 2026-05-17 07:59:00.93511+00
created_by         | live_validation
last_used_at       |
revoked_at         | 2026-05-17 07:59:00.944195+00
revoke_reason      | Security matrix test
revoked_by         | live_validation
description        | Will be revoked for security matrix test
expires_at         | 2026-05-18 02:29:00.933868+00


```

---

## 6. `api_request_audit`

- **Row count:** 397
- **Columns (12):**
  - `id (uuid)`
  - `api_key_id (uuid)`
  - `user_id (character varying)`
  - `endpoint (character varying)`
  - `method (character varying)`
  - `status_code (integer)`
  - `latency_ms (integer)`
  - `ip_hash (character varying)`
  - `user_agent_hash (character varying)`
  - `error_message (character varying)`
  - `resource_id (character varying)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---+-------------------------------------
id              | 539d4176-06d5-4086-9dca-e88dbc134389
api_key_id      |
user_id         |
endpoint        | /health
method          | GET
status_code     | 401
latency_ms      | 483
ip_hash         | 12ca17b49af22894
user_agent_hash |
error_message   |
resource_id     |
created_at      | 2026-05-16 09:15:02.842592+00
-[ RECORD 2 ]---+-------------------------------------
id              | f0a0228f-a947-45d0-be06-a69cfad08136
api_key_id      |
user_id         |
endpoint        | /copy/status
method          | GET
status_code     | 401
latency_ms      | 2
ip_hash         | 12ca17b49af22894
user_agent_hash |
error_message   |
resource_id     |
created_at      | 2026-05-16 09:15:02.888291+00


```

---

## 7. `audit_ledger`

- **Row count:** 5301
- **Columns (17):**
  - `id (text)`
  - `event_type (text)`
  - `actor (text)`
  - `target_id (text)`
  - `action (text)`
  - `data_hash (text)`
  - `previous_hash (text)`
  - `trace_id (text)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`
  - `resource_type (text)`
  - `resource_id (text)`
  - `details (jsonb)`
  - `severity (text)`
  - `hash_prev (text)`
  - `hash_self (text)`
  - `sequence (integer)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-+------------------------------------------------------------------------------
id            | ebd270cefdfd44ac
event_type    | strategy_created
actor         | IdeatorV2_4_L
target_id     |
action        | Created strategy 'trend_following_equity_tmpl_063125'
data_hash     |
previous_hash |
trace_id      | 7f754bbd420c438f
metadata      | {}
created_at    | 2026-05-18 01:01:25.427085+00
resource_type | strategy
resource_id   | 4a89b372-3299-4e1f-82a5-af77e1188284
details       | {"name": "trend_following_equity_tmpl_063125", "status": "failed_validation"}
severity      | info
hash_prev     |
hash_self     | 5978ed5fd3087ab724448829e7f9aa341531f367e1ad489e656207441cfb188d
sequence      | 1
-[ RECORD 2 ]-+------------------------------------------------------------------------------
id            | 35cb9dd1e11a484b
event_type    | code_generated
actor         | CoderAgent
target_id     |
action        | Generated code for strategy 'trend_following_equity_tmpl_063125'
data_hash     |
previous_hash |
trace_id      | 7f754bbd420c438f
metadata      | {}
created_at    | 2026-05-18 01:01:25.427085+00
resource_type | strategy
resource_id   | 4a89b372-3299-4e1f-82a5-af77e1188284
details       | {"status": "failed_validation"}
severity      | info
hash_prev     | 5978ed5fd3087ab724448829e7f9aa341531f367e1ad489e656207441cfb188d
hash_self     | 8b643b258b5ec9ebe751ef2f5706a2146301644324fc01a6e69873572e54b4e5
sequence      | 2


```

---

## 8. `audit_logs`

- **Row count:** 166
- **Columns (13):**
  - `id (uuid)`
  - `timestamp (timestamp with time zone)`
  - `action (character varying)`
  - `resource_type (character varying)`
  - `resource_id (uuid)`
  - `actor_id (character varying)`
  - `actor_type (character varying)`
  - `status (character varying)`
  - `reason (character varying)`
  - `old_value (jsonb)`
  - `new_value (jsonb)`
  - `status_code (integer)`
  - `error_reason (character varying)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-+-------------------------------------------------------------------------------------------------
id            | 38b50dd0-319b-495c-8441-20b4231f6049
timestamp     | 2026-05-16 09:14:29.294624+00
action        | migration_applied
resource_type | schema
resource_id   |
actor_id      |
actor_type    | system
status        | success
reason        | Day 5 auth schema applied
old_value     |
new_value     | {"tables": ["api_keys", "api_request_audit", "audit_logs"], "migration": "day5_auth_schema.sql"}
status_code   |
error_reason  |
-[ RECORD 2 ]-+-------------------------------------------------------------------------------------------------
id            | 06d27609-faa0-4ae1-b375-86480c5eb348
timestamp     | 2026-05-16 09:14:52.015908+00
action        | migration_applied
resource_type | schema
resource_id   |
actor_id      |
actor_type    | system
status        | success
reason        | Day 5 auth schema applied
old_value     |
new_value     | {"tables": ["api_keys", "api_request_audit", "audit_logs"], "migration": "day5_auth_schema.sql"}
status_code   |
error_reason  |


```

---

## 9. `backtest_results`

- **Row count:** 2518
- **Columns (22):**
  - `strategy_id (uuid)`
  - `start_date (timestamp with time zone)`
  - `end_date (timestamp with time zone)`
  - `sharpe (numeric)`
  - `cagr (numeric)`
  - `max_drawdown (numeric)`
  - `win_rate (numeric)`
  - `total_trades (integer)`
  - `passed_validation (boolean)`
  - `results (jsonb)`
  - `entry_count (integer)`
  - `exit_count (integer)`
  - `bars_processed (integer)`
  - `short_window_score (numeric)`
  - `score_7d (numeric)`
  - `score_14d (numeric)`
  - `score_30d (numeric)`
  - `created_at (timestamp with time zone)`
  - `composite_fitness_score (numeric)`
  - `sortino_ratio (numeric)`
  - *... and 2 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
strategy_id             | 7160c8f7-ac57-438f-b91c-b308ebf56a76
start_date              | 2026-05-06 13:30:00+00
end_date                | 2026-05-18 13:44:47.818507+00
sharpe                  | 0
cagr                    | 0
max_drawdown            | 0
win_rate                | 0
total_trades            | 0
passed_validation       | f
results                 | {"cagr": 0.0, "win_rate": 0.0, "exit_count": 2, "expectancy": 0.0, "gross_edge": 0.0, "cost_burden": 0.0, "entry_count": 2, "test_sharpe": 0.0, "calmar_ratio": 0.0, "max_drawdown": 0.0, "regime_score": 0.0, "sharpe_ratio": 0.0, "total_return": 0.0, "total_trades": 0, "train_sharpe": 0.0, "profit_factor": 1.0, "sortino_ratio": 0.0, "bars_processed": 3165, "holdout_sharpe":... [TRUNCATED]
entry_count             | 2
exit_count              | 2
bars_processed          | 3165
short_window_score      | 35
score_7d                |
score_14d               |
score_30d               |
created_at              | 2026-05-28 04:25:54.603773+00
composite_fitness_score | 35
sortino_ratio           | 0
calmar_ratio            | 0
expectancy              | 0
-[ RECORD 2 ]-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
strategy_id             | c139289c-718a-4356-8ed6-4e846c3e0b94
start_date              | 2026-05-06 13:30:00+00
end_date                | 2026-05-18 13:44:47.818507+00
sharpe                  | 0
cagr                    | 0
max_drawdown            | 0
win_rate                | 0
total_trades            | 0
passed_validation       | f
results                 | {"cagr": 0.0, "win_rate": 0.0, "exit_count": 5, "expectancy": 0.0, "gross_edge": 0.0, "cost_burden": 0.0, "entry_count": 5, "test_sharpe": 0.0, "calmar_ratio": 0.0, "max_drawdown": 0.0, "regime_score": 0.0, "sharpe_ratio": 0.0, "total_return": 0.0, "total_trades": 0, "train_sharpe": 0.0, "profit_factor": 1.0, "sortino_ratio": 0.0, "bars_processed": 3165, "holdout_sharpe":... [TRUNCATED]
entry_count             | 5
exit_count              | 5
bars_processed          | 3165
short_window_score      | 35
score_7d                |
score_14d               |
score_30d               |
created_at              | 2026-05-28 04:25:55.235927+00
composite_fitness_score | 35
sortino_ratio           | 0
calmar_ratio            | 0
expectancy              | 0


```

---

## 10. `backtest_trades`

- **Row count:** 1519981
- **Columns (12):**
  - `id (uuid)`
  - `strategy_id (uuid)`
  - `symbol (text)`
  - `entry_time (timestamp with time zone)`
  - `exit_time (timestamp with time zone)`
  - `entry_price (numeric)`
  - `exit_price (numeric)`
  - `side (text)`
  - `pnl (numeric)`
  - `pnl_pct (numeric)`
  - `bars_held (integer)`
  - `exit_reason (text)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------------------------------------------------------------
id          | 441a5d82-f6e5-4d2e-931a-5480f472a2d9
strategy_id | 62bce0f3-1662-486f-b8f9-de2e5ba01100
symbol      | NVDA
entry_time  | 2026-05-06 13:30:00+00
exit_time   | 2026-05-06 14:06:00+00
entry_price | 198.9199066200000061144237406551837921142578125
exit_price  | 203.220001220000000330401235260069370269775390625
side        | short
pnl         | -4.30009460000000043322643250576220452785491943359375
pnl_pct     | -0.021617219999999999491269164764162269420921802520751953125
bars_held   | 35
exit_reason | signal
-[ RECORD 2 ]-------------------------------------------------------------------
id          | 4bd02d8b-3c1c-4026-b4de-339624ca98cc
strategy_id | 62bce0f3-1662-486f-b8f9-de2e5ba01100
symbol      | NVDA
entry_time  | 2026-05-06 14:07:00+00
exit_time   | 2026-05-06 14:08:00+00
entry_price | 203.98500060999998595434590242803096771240234375
exit_price  | 203.88999939000001404565409757196903228759765625
side        | short
pnl         | 0.09500121999999999733432787252240814268589019775390625
pnl_pct     | 0.0004657299999999999742979206462933916554902680218219757080078125
bars_held   | 0
exit_reason | signal


```

---

## 11. `capital_allocation`

- **Row count:** 31
- **Columns (13):**
  - `id (uuid)`
  - `computed_at (timestamp with time zone)`
  - `n_strategies (integer)`
  - `method (text)`
  - `final_allocations (jsonb)`
  - `total_exposure (numeric)`
  - `kelly_weights (jsonb)`
  - `vol_target_weights (jsonb)`
  - `risk_parity_weights (jsonb)`
  - `redistribution_signals (jsonb)`
  - `regime_applied (jsonb)`
  - `leverage_cap_applied (numeric)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                     | 89655028-61e4-41c9-832a-282a00e426f8
computed_at            | 2026-05-22 07:21:39.066165+00
n_strategies           | 50
method                 | kelly_vol_target_risk_parity_ensemble
final_allocations      | [{"score": 40.2, "sharpe": 0.0, "weight": 0.0302, "archetype": "trend_following", "asset_class": "equity", "strategy_id": "69885aed-9c59-4e95-9a2c-bfe3521ef488", "strategy_name": "trend_following_equity_tmpl_072630"}, {"score": 40.2, "sharpe": 0.0, "weight": 0.0302, "archetype": "trend_following", "asset_class": "equity", "strategy_id": "8d3be794-913d-49d3-8b5b-f0b8d7d8e6b... [TRUNCATED]
total_exposure         | 1.00150000000000005684341886080801486968994140625
kelly_weights          | [{"win_rate": 0.5311, "kelly_raw": 0.25, "strategy_id": "b8de7f09-dc7a-498d-9da7-d62b79d1047e", "strategy_name": "nvda_bb_rsi_vwap_momentum_v2", "avg_return_pct": 0.0001, "kelly_conservative": 0.0625}, {"win_rate": 0.5264, "kelly_raw": 0.25, "strategy_id": "dcb3c6cb-fc65-4488-b3e0-7b48547361f6", "strategy_name": "btc_rsi_bb_meanrev_v5", "avg_return_pct": 0.0001, "kelly_con... [TRUNCATED]
vol_target_weights     | [{"strategy_id": "b8de7f09-dc7a-498d-9da7-d62b79d1047e", "strategy_name": "nvda_bb_rsi_vwap_momentum_v2", "vol_target_weight": 0.3, "annualized_vol_estimate": 0.02}, {"strategy_id": "dcb3c6cb-fc65-4488-b3e0-7b48547361f6", "strategy_name": "btc_rsi_bb_meanrev_v5", "vol_target_weight": 0.3, "annualized_vol_estimate": 0.02}, {"strategy_id": "5f892d98-7f0d-451d-b4c9-3c03cf5cbb... [TRUNCATED]
risk_parity_weights    | [{"strategy_id": "b8de7f09-dc7a-498d-9da7-d62b79d1047e", "strategy_name": "nvda_bb_rsi_vwap_momentum_v2", "risk_parity_weight": 0.02}, {"strategy_id": "dcb3c6cb-fc65-4488-b3e0-7b48547361f6", "strategy_name": "btc_rsi_bb_meanrev_v5", "risk_parity_weight": 0.02}, {"strategy_id": "5f892d98-7f0d-451d-b4c9-3c03cf5cbbcb", "strategy_name": "btc_rsi_bb_meanrev_v5", "risk_parity_we... [TRUNCATED]
redistribution_signals | []
regime_applied         | {"vol": 0.142358, "liq_regime": "dangerous", "vol_regime": "high_vol", "corr_regime": "diversified"}
leverage_cap_applied   | 1
metadata               | {"method": "kelly_vol_target_risk_parity_ensemble"}
-[ RECORD 2 ]----------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                     | b66127de-5500-4812-899a-126ceade449f
computed_at            | 2026-05-22 07:27:42.420855+00
n_strategies           | 50
method                 | kelly_vol_target_risk_parity_ensemble
final_allocations      | [{"score": 40.2, "sharpe": 0.0, "weight": 0.0302, "archetype": "trend_following", "asset_class": "equity", "strategy_id": "69885aed-9c59-4e95-9a2c-bfe3521ef488", "strategy_name": "trend_following_equity_tmpl_072630"}, {"score": 40.2, "sharpe": 0.0, "weight": 0.0302, "archetype": "trend_following", "asset_class": "equity", "strategy_id": "8d3be794-913d-49d3-8b5b-f0b8d7d8e6b... [TRUNCATED]
total_exposure         | 1.00150000000000005684341886080801486968994140625
kelly_weights          | [{"win_rate": 0.5311, "kelly_raw": 0.25, "strategy_id": "b8de7f09-dc7a-498d-9da7-d62b79d1047e", "strategy_name": "nvda_bb_rsi_vwap_momentum_v2", "avg_return_pct": 0.0001, "kelly_conservative": 0.0625}, {"win_rate": 0.5264, "kelly_raw": 0.25, "strategy_id": "dcb3c6cb-fc65-4488-b3e0-7b48547361f6", "strategy_name": "btc_rsi_bb_meanrev_v5", "avg_return_pct": 0.0001, "kelly_con... [TRUNCATED]
vol_target_weights     | [{"strategy_id": "b8de7f09-dc7a-498d-9da7-d62b79d1047e", "strategy_name": "nvda_bb_rsi_vwap_momentum_v2", "vol_target_weight": 0.3, "annualized_vol_estimate": 0.02}, {"strategy_id": "dcb3c6cb-fc65-4488-b3e0-7b48547361f6", "strategy_name": "btc_rsi_bb_meanrev_v5", "vol_target_weight": 0.3, "annualized_vol_estimate": 0.02}, {"strategy_id": "5f892d98-7f0d-451d-b4c9-3c03cf5cbb... [TRUNCATED]
risk_parity_weights    | [{"strategy_id": "b8de7f09-dc7a-498d-9da7-d62b79d1047e", "strategy_name": "nvda_bb_rsi_vwap_momentum_v2", "risk_parity_weight": 0.02}, {"strategy_id": "dcb3c6cb-fc65-4488-b3e0-7b48547361f6", "strategy_name": "btc_rsi_bb_meanrev_v5", "risk_parity_weight": 0.02}, {"strategy_id": "5f892d98-7f0d-451d-b4c9-3c03cf5cbbcb", "strategy_name": "btc_rsi_bb_meanrev_v5", "risk_parity_we... [TRUNCATED]
redistribution_signals | []
regime_applied         | {"vol": 0.142358, "liq_regime": "dangerous", "vol_regime": "high_vol", "corr_regime": "diversified"}
leverage_cap_applied   | 1
metadata               | {"method": "kelly_vol_target_risk_parity_ensemble"}


```

---

## 12. `capital_preservation_state`

- **Row count:** 1496
- **Columns (9):**
  - `id (text)`
  - `checked_at (timestamp with time zone)`
  - `drawdown_pct (numeric)`
  - `action_taken (text)`
  - `exposure_cut_ratio (numeric)`
  - `peak_value (numeric)`
  - `current_value (numeric)`
  - `total_pnl (numeric)`
  - `total_exposure (numeric)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]------+------------------------------
id                 | 5125f64540604283
checked_at         | 2026-05-22 07:21:38.754027+00
drawdown_pct       | 0
action_taken       | none
exposure_cut_ratio | 1
peak_value         | 100000
current_value      | 100000
total_pnl          | 0
total_exposure     | 0
-[ RECORD 2 ]------+------------------------------
id                 | fa9a9699b3814d05
checked_at         | 2026-05-22 07:22:38.821687+00
drawdown_pct       | 0
action_taken       | none
exposure_cut_ratio | 1
peak_value         | 100000
current_value      | 100000
total_pnl          | 0
total_exposure     | 0


```

---

## 13. `combination_memory`

- **Row count:** 0
- **Columns (10):**
  - `id (uuid)`
  - `parent_a (uuid)`
  - `parent_b (uuid)`
  - `child_id (uuid)`
  - `combination_type (text)`
  - `parent_a_sharpe (numeric)`
  - `parent_b_sharpe (numeric)`
  - `child_sharpe (numeric)`
  - `sharpe_delta (numeric)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 14. `copy_drift_log`

- **Row count:** 0
- **Columns (17):**
  - `id (text)`
  - `trace_id (text)`
  - `leader_id (text)`
  - `follower_id (text)`
  - `drift_score (numeric)`
  - `drift_severity (text)`
  - `exposure_drift (numeric)`
  - `pnl_drift (numeric)`
  - `leverage_drift (numeric)`
  - `symbol_allocation_drift (numeric)`
  - `execution_timing_drift_ms (integer)`
  - `slippage_amplification (numeric)`
  - `partial_fill_divergence (numeric)`
  - `sync_quality_score (numeric)`
  - `repair_recommendation (text)`
  - `metadata (jsonb)`
  - `detected_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 15. `copy_execution_log`

- **Row count:** 7
- **Columns (14):**
  - `id (uuid)`
  - `leader_order_id (uuid)`
  - `follower_order_id (uuid)`
  - `leader_id (uuid)`
  - `follower_id (uuid)`
  - `symbol (text)`
  - `side (text)`
  - `leader_qty (numeric)`
  - `follower_qty (numeric)`
  - `latency_ms (bigint)`
  - `status (text)`
  - `failure_reason (text)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----+-------------------------------------
id                | e216c18c-486f-4998-bb9a-859d70ca5c5d
leader_order_id   | e0075e50-1b45-460b-82ca-3ec11561d0f5
follower_order_id | c6de20b5-1789-405f-83a9-4ddcf38031d0
leader_id         |
follower_id       | 7416c767-c7e7-401b-90c7-e4e5b242b3ca
symbol            | NVDA
side              | buy
leader_qty        | 10
follower_qty      | 5
latency_ms        | 97
status            | filled
failure_reason    |
metadata          |
created_at        | 2026-05-16 07:52:23.63819+00
-[ RECORD 2 ]-----+-------------------------------------
id                | 4b41c7f4-26e5-4fc9-93e6-656b79a41793
leader_order_id   | 1fd3c072-bccb-4a66-bd85-6c9548b2c135
follower_order_id | 58dff452-707f-4d8d-87a5-2acc8480b6e6
leader_id         |
follower_id       | 7416c767-c7e7-401b-90c7-e4e5b242b3ca
symbol            | AAPL
side              | buy
leader_qty        | 100
follower_qty      | 50
latency_ms        | 96
status            | filled
failure_reason    |
metadata          |
created_at        | 2026-05-16 07:52:57.334321+00


```

---

## 16. `copy_failover_events`

- **Row count:** 0
- **Columns (11):**
  - `id (text)`
  - `trace_id (text)`
  - `follower_id (text)`
  - `leader_id (text)`
  - `event_type (text)`
  - `previous_mode (text)`
  - `new_mode (text)`
  - `trigger_reason (text)`
  - `recovery_action (text)`
  - `metadata (jsonb)`
  - `occurred_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 17. `copy_follower_accounts`

- **Row count:** 2
- **Columns (9):**
  - `follower_id (uuid)`
  - `leader_id (uuid)`
  - `broker (text)`
  - `account_ref (text)`
  - `allocation_ratio (numeric)`
  - `max_position_pct (numeric)`
  - `is_active (boolean)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----+-------------------------------------
follower_id      | 7416c767-c7e7-401b-90c7-e4e5b242b3ca
leader_id        | 87bf6ffa-d639-4403-9c6b-fa24235c05b5
broker           | local
account_ref      | SIM_FOLLOWER_001
allocation_ratio | 0.5000
max_position_pct | 0.1000
is_active        | t
metadata         |
created_at       | 2026-05-16 07:50:19.778002+00
-[ RECORD 2 ]----+-------------------------------------
follower_id      | 855249b2-6376-4d5c-886e-ad349ab72337
leader_id        | 069cb59a-11de-476c-b802-c55f08964997
broker           | alpaca_paper
account_ref      | follower_atlas_001
allocation_ratio | 1.0000
max_position_pct | 0.1000
is_active        | t
metadata         |
created_at       | 2026-05-17 07:45:22.853282+00


```

---

## 18. `copy_leader_accounts`

- **Row count:** 2
- **Columns (6):**
  - `leader_id (uuid)`
  - `broker (text)`
  - `account_ref (text)`
  - `is_active (boolean)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------------------------------
leader_id   | 87bf6ffa-d639-4403-9c6b-fa24235c05b5
broker      | local
account_ref | SIM_LEADER_001
is_active   | t
metadata    |
created_at  | 2026-05-16 07:50:19.769676+00
-[ RECORD 2 ]-------------------------------------
leader_id   | 069cb59a-11de-476c-b802-c55f08964997
broker      | alpaca_paper
account_ref | leader_atlas_001
is_active   | t
metadata    |
created_at  | 2026-05-17 07:45:22.853282+00


```

---

## 19. `copy_overlap_metrics`

- **Row count:** 0
- **Columns (12):**
  - `id (text)`
  - `trace_id (text)`
  - `follower_id (text)`
  - `overlap_score (numeric)`
  - `concentration_risk (numeric)`
  - `diversification_penalty (numeric)`
  - `duplicated_exposure (jsonb)`
  - `correlated_leaders (jsonb)`
  - `hidden_concentration (jsonb)`
  - `n_leaders_analyzed (integer)`
  - `metadata (jsonb)`
  - `analyzed_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 20. `copy_position_state`

- **Row count:** 0
- **Columns (19):**
  - `id (text)`
  - `trace_id (text)`
  - `leader_id (text)`
  - `follower_id (text)`
  - `symbol (text)`
  - `leader_qty (numeric)`
  - `follower_qty (numeric)`
  - `leader_avg_entry (numeric)`
  - `follower_avg_entry (numeric)`
  - `leader_exposure (numeric)`
  - `follower_exposure (numeric)`
  - `leader_unrealized_pnl (numeric)`
  - `follower_unrealized_pnl (numeric)`
  - `leader_realized_pnl (numeric)`
  - `follower_realized_pnl (numeric)`
  - `execution_latency_ms (integer)`
  - `sync_quality_score (numeric)`
  - `metadata (jsonb)`
  - `snapshot_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 21. `copy_quality_metrics`

- **Row count:** 564
- **Columns (15):**
  - `id (text)`
  - `trace_id (text)`
  - `leader_id (text)`
  - `follower_id (text)`
  - `replication_latency_ms (numeric)`
  - `sync_quality_score (numeric)`
  - `slippage_amplification (numeric)`
  - `execution_divergence (numeric)`
  - `pnl_divergence (numeric)`
  - `replay_integrity (numeric)`
  - `drift_accumulation (numeric)`
  - `follower_survivability (numeric)`
  - `n_events_analyzed (integer)`
  - `metadata (jsonb)`
  - `measured_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------+-------------------------------------------------------------
id                     | ec632308-2824-4336-be98-f3f1b89ca34b
trace_id               | c7435285-3ad2-49dd-803a-b94e6c074526
leader_id              | 87bf6ffa-d639-4403-9c6b-fa24235c05b5
follower_id            | 7416c767-c7e7-401b-90c7-e4e5b242b3ca
replication_latency_ms | 0
sync_quality_score     | 1
slippage_amplification | 0.05000000000000000277555756156289135105907917022705078125
execution_divergence   | 0.0200000000000000004163336342344337026588618755340576171875
pnl_divergence         | 0
replay_integrity       | 0.979999999999999982236431605997495353221893310546875
drift_accumulation     | 0.1000000000000000055511151231257827021181583404541015625
follower_survivability | 0.90000000000000002220446049250313080847263336181640625
n_events_analyzed      | 0
metadata               | {"agent": "CopyAnalyticsEngine"}
measured_at            | 2026-05-27 06:59:49.504808+00
-[ RECORD 2 ]----------+-------------------------------------------------------------
id                     | 2a6b0ce0-82c0-47cd-850a-f0b6f3f5c7b2
trace_id               | 0a9331cd-6872-4998-beba-f94f2ab938ee
leader_id              | 069cb59a-11de-476c-b802-c55f08964997
follower_id            | 855249b2-6376-4d5c-886e-ad349ab72337
replication_latency_ms | 0
sync_quality_score     | 1
slippage_amplification | 0.05000000000000000277555756156289135105907917022705078125
execution_divergence   | 0.0200000000000000004163336342344337026588618755340576171875
pnl_divergence         | 0
replay_integrity       | 0.979999999999999982236431605997495353221893310546875
drift_accumulation     | 0.1000000000000000055511151231257827021181583404541015625
follower_survivability | 0.90000000000000002220446049250313080847263336181640625
n_events_analyzed      | 0
metadata               | {"agent": "CopyAnalyticsEngine"}
measured_at            | 2026-05-27 06:59:49.543645+00


```

---

## 22. `copy_replay_events`

- **Row count:** 0
- **Columns (19):**
  - `id (text)`
  - `trace_id (text)`
  - `event_type (text)`
  - `leader_id (text)`
  - `follower_id (text)`
  - `leader_order_id (text)`
  - `follower_order_id (text)`
  - `symbol (text)`
  - `side (text)`
  - `leader_qty (numeric)`
  - `follower_qty (numeric)`
  - `leader_price (numeric)`
  - `follower_price (numeric)`
  - `slippage_bps (numeric)`
  - `execution_latency_ms (integer)`
  - `drift_at_execution (numeric)`
  - `event_data (jsonb)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 23. `correlation_memory`

- **Row count:** 318
- **Columns (11):**
  - `id (uuid)`
  - `timestamp (timestamp with time zone)`
  - `cluster_name (text)`
  - `avg_pairwise_corr (numeric)`
  - `dominant_factor (text)`
  - `risk_state (text)`
  - `symbols_analyzed (ARRAY)`
  - `top_correlated_pairs (jsonb)`
  - `correlation_spike_detected (boolean)`
  - `metadata (jsonb)`
  - `correlation_value (numeric)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------------+-----------------------------------------------------------------------------------------------------------------
id                         | 7f53da99-6f3e-461e-b393-de0b9340dbf3
timestamp                  | 2026-05-19 15:21:07.945384+00
cluster_name               | tech_heavy
avg_pairwise_corr          | 0.2351999999999999924060745115639292635023593902587890625
dominant_factor            | SPY
risk_state                 | diversified
symbols_analyzed           | {BTCUSDT,ETHUSDT,SOLUSDT,SPY,QQQ,AAPL,MSFT,NVDA}
top_correlated_pairs       | {"SPY_QQQ": 0.8488, "QQQ_NVDA": 0.7698, "SPY_NVDA": 0.6888, "BTCUSDT_ETHUSDT": 0.8381, "BTCUSDT_SOLUSDT": 0.774}
correlation_spike_detected | f
metadata                   | {}
correlation_value          |
-[ RECORD 2 ]--------------+-----------------------------------------------------------------------------------------------------------------
id                         | e6bb020d-80e7-4e32-bc91-1f9b74b69fe6
timestamp                  | 2026-05-22 06:33:54.84593+00
cluster_name               | tech_heavy
avg_pairwise_corr          | 0.2351999999999999924060745115639292635023593902587890625
dominant_factor            | SPY
risk_state                 | diversified
symbols_analyzed           | {BTCUSDT,ETHUSDT,SOLUSDT,SPY,QQQ,AAPL,MSFT,NVDA}
top_correlated_pairs       | {"SPY_QQQ": 0.8488, "QQQ_NVDA": 0.7698, "SPY_NVDA": 0.6888, "BTCUSDT_ETHUSDT": 0.8381, "BTCUSDT_SOLUSDT": 0.774}
correlation_spike_detected | f
metadata                   | {}
correlation_value          |


```

---

## 24. `cost_stress_analysis`

- **Row count:** 0
- **Columns (9):**
  - `id (uuid)`
  - `strategy_id (uuid)`
  - `cost_survival_score (numeric)`
  - `max_survivable_multiplier (numeric)`
  - `profit_factor_degradation (numeric)`
  - `expectancy_degradation (numeric)`
  - `passes_min_survival (boolean)`
  - `fragile_scalper_detected (boolean)`
  - `tested_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 25. `deployment_governance`

- **Row count:** 0
- **Columns (11):**
  - `id (text)`
  - `strategy_id (text)`
  - `mode (text)`
  - `status (text)`
  - `proposed_by (text)`
  - `approved_by (text)`
  - `proposed_at (timestamp with time zone)`
  - `approved_at (timestamp with time zone)`
  - `activated_at (timestamp with time zone)`
  - `metadata (jsonb)`
  - `updated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 26. `dominant_organism_log`

- **Row count:** 492
- **Columns (14):**
  - `id (character varying)`
  - `tracked_at (timestamp with time zone)`
  - `n_organisms_total (integer)`
  - `n_dominant_identified (integer)`
  - `dominant_organisms (jsonb)`
  - `lifespan_rankings (jsonb)`
  - `efficiency_rankings (jsonb)`
  - `expectancy_rankings (jsonb)`
  - `regime_specialists (jsonb)`
  - `mutation_family_resilience (jsonb)`
  - `recovery_scores (jsonb)`
  - `retirement_cause_distribution (jsonb)`
  - `ecosystem_health (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                            | ddab4f65-cd06-4c59-b0fb-3a0ba73cdf52
tracked_at                    | 2026-05-25 14:18:24.478494+00
n_organisms_total             | 10
n_dominant_identified         | 5
dominant_organisms            | [{"status": "emerging", "efficiency": 0.0, "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "lifespan_bars": 0, "strategy_name": "volatility_regime_crypto_local_082258", "dominance_score": 105, "specializations": [], "composite_expectancy": -0.0033, "dominance_categories": ["longevity", "capital_efficiency", "expectancy"], "specialization_score": 0}, {"status"... [TRUNCATED]
lifespan_rankings             | [{"status": "emerging", "strategy_id": "2b9ff3af-7d8f-499d-a039-a3b842b1e3e6", "lifespan_bars": 0, "strategy_name": "volatility_regime_crypto_local_082310"}, {"status": "emerging", "strategy_id": "c14f10be-692a-4672-87c0-86a7cf9365cb", "lifespan_bars": 0, "strategy_name": "mean_reversion_crypto_local_082309"}, {"status": "emerging", "strategy_id": "f69702f6-03d3-45d... [TRUNCATED]
efficiency_rankings           | [{"efficiency": 0.0, "strategy_id": "2b9ff3af-7d8f-499d-a039-a3b842b1e3e6", "max_drawdown": -0.0944, "total_trades": 0, "strategy_name": "volatility_regime_crypto_local_082310", "composite_score": 0.0}, {"efficiency": 0.0, "strategy_id": "c14f10be-692a-4672-87c0-86a7cf9365cb", "max_drawdown": -0.1163, "total_trades": 1, "strategy_name": "mean_reversion_crypto_local_... [TRUNCATED]
expectancy_rankings           | [{"win_rate": 0.4889, "expectancy": 0.0, "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "total_trades": 3, "strategy_name": "volatility_regime_crypto_local_082258", "avg_return_pct": 0.0, "composite_expectancy_score": -0.0033}, {"win_rate": 0.4889, "expectancy": 0.0, "strategy_id": "75387203-1fc4-4bed-b6dd-dfc65caddd5f", "total_trades": 3, "strategy_name": "... [TRUNCATED]
regime_specialists            | []
mutation_family_resilience    | []
recovery_scores               | [{"strategy_id": "2b9ff3af-7d8f-499d-a039-a3b842b1e3e6", "max_drawdown": 0.09, "total_trades": 0, "current_score": 0.0, "current_state": "emerging", "strategy_name": "volatility_regime_crypto_local_082310", "recovery_potential": 0.0}, {"strategy_id": "c14f10be-692a-4672-87c0-86a7cf9365cb", "max_drawdown": 0.12, "total_trades": 1, "current_score": 0.0, "current_state... [TRUNCATED]
retirement_cause_distribution | {}
ecosystem_health              | {"n_retired": 0, "n_degraded": 0, "avg_lifespan_bars": 0.0, "n_surviving_organisms": 9, "dominant_concentration": 0.5}
metadata                      | {"method": "multi_metric_cross_reference"}
-[ RECORD 2 ]-----------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                            | 7c19b580-182f-4c82-aa86-ec5b75a481f0
tracked_at                    | 2026-05-25 14:18:39.74299+00
n_organisms_total             | 10
n_dominant_identified         | 5
dominant_organisms            | [{"status": "emerging", "efficiency": 0.0, "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "lifespan_bars": 0, "strategy_name": "volatility_regime_crypto_local_082258", "dominance_score": 105, "specializations": [], "composite_expectancy": -0.0033, "dominance_categories": ["longevity", "capital_efficiency", "expectancy"], "specialization_score": 0}, {"status"... [TRUNCATED]
lifespan_rankings             | [{"status": "emerging", "strategy_id": "2b9ff3af-7d8f-499d-a039-a3b842b1e3e6", "lifespan_bars": 0, "strategy_name": "volatility_regime_crypto_local_082310"}, {"status": "emerging", "strategy_id": "c14f10be-692a-4672-87c0-86a7cf9365cb", "lifespan_bars": 0, "strategy_name": "mean_reversion_crypto_local_082309"}, {"status": "emerging", "strategy_id": "f69702f6-03d3-45d... [TRUNCATED]
efficiency_rankings           | [{"efficiency": 0.0, "strategy_id": "2b9ff3af-7d8f-499d-a039-a3b842b1e3e6", "max_drawdown": -0.0944, "total_trades": 0, "strategy_name": "volatility_regime_crypto_local_082310", "composite_score": 0.0}, {"efficiency": 0.0, "strategy_id": "c14f10be-692a-4672-87c0-86a7cf9365cb", "max_drawdown": -0.1163, "total_trades": 1, "strategy_name": "mean_reversion_crypto_local_... [TRUNCATED]
expectancy_rankings           | [{"win_rate": 0.4889, "expectancy": 0.0, "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "total_trades": 3, "strategy_name": "volatility_regime_crypto_local_082258", "avg_return_pct": 0.0, "composite_expectancy_score": -0.0033}, {"win_rate": 0.4889, "expectancy": 0.0, "strategy_id": "75387203-1fc4-4bed-b6dd-dfc65caddd5f", "total_trades": 3, "strategy_name": "... [TRUNCATED]
regime_specialists            | []
mutation_family_resilience    | []
recovery_scores               | [{"strategy_id": "2b9ff3af-7d8f-499d-a039-a3b842b1e3e6", "max_drawdown": 0.09, "total_trades": 0, "current_score": 0.0, "current_state": "emerging", "strategy_name": "volatility_regime_crypto_local_082310", "recovery_potential": 0.0}, {"strategy_id": "c14f10be-692a-4672-87c0-86a7cf9365cb", "max_drawdown": 0.12, "total_trades": 1, "current_score": 0.0, "current_state... [TRUNCATED]
retirement_cause_distribution | {}
ecosystem_health              | {"n_retired": 0, "n_degraded": 0, "avg_lifespan_bars": 0.0, "n_surviving_organisms": 9, "dominant_concentration": 0.5}
metadata                      | {"method": "multi_metric_cross_reference"}


```

---

## 27. `drift_detection`

- **Row count:** 459
- **Columns (11):**
  - `id (uuid)`
  - `detected_at (timestamp with time zone)`
  - `feature_drift_score (numeric)`
  - `strategy_drift_score (numeric)`
  - `regime_drift_score (numeric)`
  - `execution_drift_score (numeric)`
  - `composite_severity (numeric)`
  - `n_strategies_monitored (integer)`
  - `retirement_candidates (jsonb)`
  - `retrain_recommendations (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------+-------------------------------------------------------------------
id                      | b7445e11-0130-4677-963b-075ce7fd3cea
detected_at             | 2026-05-22 07:13:24.379557+00
feature_drift_score     | 0.0079000000000000007716050021144837955944240093231201171875
strategy_drift_score    | 0
regime_drift_score      | 0.0205000000000000008604228440844963188283145427703857421875
execution_drift_score   | 0
composite_severity      | 0.006700000000000000226207941267375645111314952373504638671875
n_strategies_monitored  | 0
retirement_candidates   | []
retrain_recommendations | []
metadata                | {"method": "psi_and_trend_analysis"}
-[ RECORD 2 ]-----------+-------------------------------------------------------------------
id                      | 9def5c33-7110-4ac1-a70f-1712849d45e3
detected_at             | 2026-05-22 07:21:39.070684+00
feature_drift_score     | 0.0079000000000000007716050021144837955944240093231201171875
strategy_drift_score    | 0
regime_drift_score      | 0.0004000000000000000191686944095437183932517655193805694580078125
execution_drift_score   | 0
composite_severity      | 0.00169999999999999990528409821166633264510892331600189208984375
n_strategies_monitored  | 0
retirement_candidates   | []
retrain_recommendations | []
metadata                | {"method": "psi_and_trend_analysis"}


```

---

## 28. `economic_efficiency_analysis`

- **Row count:** 565
- **Columns (27):**
  - `id (text)`
  - `analyzed_at (timestamp with time zone)`
  - `expectancy (numeric)`
  - `win_loss_asymmetry (numeric)`
  - `slippage_adjusted_edge (numeric)`
  - `risk_adjusted_return (numeric)`
  - `return_per_drawdown (numeric)`
  - `capital_velocity (numeric)`
  - `strategy_half_life_hours (numeric)`
  - `mutation_survival_rate (numeric)`
  - `regime_persistence (numeric)`
  - `drawdown_persistence_hours (numeric)`
  - `recovery_efficiency (numeric)`
  - `cascading_failure_risk (numeric)`
  - `concentration_instability (numeric)`
  - `portfolio_contagion_risk (numeric)`
  - `dominant_mutation_family (text)`
  - `collapsing_families (jsonb)`
  - `exploration_ratio (numeric)`
  - `top_scout (text)`
  - *... and 7 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                          | 1fa59c5346734e81
analyzed_at                 | 2026-05-24 11:26:44.987567+00
expectancy                  | 0
win_loss_asymmetry          | 0
slippage_adjusted_edge      | 0
risk_adjusted_return        | 0
return_per_drawdown         | 0
capital_velocity            | 0
strategy_half_life_hours    | 0
mutation_survival_rate      | 0
regime_persistence          | 0
drawdown_persistence_hours  | 0
recovery_efficiency         | 1
cascading_failure_risk      | 0
concentration_instability   | 0.000100000000000000004792173602385929598312941379845142364501953125
portfolio_contagion_risk    | 0
dominant_mutation_family    | none
collapsing_families         | []
exploration_ratio           | 0.5
top_scout                   | ideator_archetype_momentum
worst_scout                 | none
predictive_divergence       | 0
execution_degradation       | 0
spread_sensitivity          | 0
liquidity_degradation_trend | 0
composite_analysis          | {"scout_quality": {"n_scouts_analyzed": 30, "contradiction_rate": 0.0, "signal_to_noise_ratio": -1.0, "predictive_contribution": 0.0, "economic_attribution_quality": 0.0}, "trade_quality": {"expectancy": 0.0, "trade_clustering": 0.0, "n_trades_analyzed": 0, "win_loss_asymmetry": 0.0, "risk_adjusted_return": 0.0, "avg_holding_efficiency": 0.0, "slippage_adjusted_edge":... [TRUNCATED]
metadata                    | {"agent": "EconomicEfficiencyEngine", "domains": ["trade_quality", "capital_efficiency", "survival_quality", "scout_quality", "capital_preservation", "regime_specialization", "mutation_fitness", "scout_predictive_value", "execution_realism"], "n_domains_analyzed": 7}
-[ RECORD 2 ]---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                          | 5d37ca48a14c4072
analyzed_at                 | 2026-05-24 11:28:57.167677+00
expectancy                  | 0
win_loss_asymmetry          | 0
slippage_adjusted_edge      | 0
risk_adjusted_return        | 0
return_per_drawdown         | 0
capital_velocity            | 0
strategy_half_life_hours    | 0
mutation_survival_rate      | 0
regime_persistence          | 0
drawdown_persistence_hours  | 0
recovery_efficiency         | 1
cascading_failure_risk      | 0
concentration_instability   | 0.000100000000000000004792173602385929598312941379845142364501953125
portfolio_contagion_risk    | 0
dominant_mutation_family    | none
collapsing_families         | []
exploration_ratio           | 0.5
top_scout                   | ideator_archetype_momentum
worst_scout                 | none
predictive_divergence       | 0
execution_degradation       | 0
spread_sensitivity          | 0
liquidity_degradation_trend | 0
composite_analysis          | {"scout_quality": {"n_scouts_analyzed": 32, "contradiction_rate": 0.0, "signal_to_noise_ratio": -1.0, "predictive_contribution": 0.0, "economic_attribution_quality": 0.0}, "trade_quality": {"expectancy": 0.0, "trade_clustering": 0.0, "n_trades_analyzed": 0, "win_loss_asymmetry": 0.0, "risk_adjusted_return": 0.0, "avg_holding_efficiency": 0.0, "slippage_adjusted_edge":... [TRUNCATED]
metadata                    | {"agent": "EconomicEfficiencyEngine", "domains": ["trade_quality", "capital_efficiency", "survival_quality", "scout_quality", "capital_preservation", "regime_specialization", "mutation_fitness", "scout_predictive_value", "execution_realism"], "n_domains_analyzed": 7}


```

---

## 29. `economic_fitness_windows`

- **Row count:** 1458
- **Columns (17):**
  - `id (uuid)`
  - `window_hours (integer)`
  - `computed_at (timestamp with time zone)`
  - `n_strategies (integer)`
  - `avg_composite_fitness (numeric)`
  - `avg_sharpe (numeric)`
  - `avg_sortino (numeric)`
  - `avg_calmar (numeric)`
  - `avg_expectancy (numeric)`
  - `median_composite_fitness (numeric)`
  - `top_decile_fitness (numeric)`
  - `bottom_decile_fitness (numeric)`
  - `fitness_trend (numeric)`
  - `mutation_survival_rate (numeric)`
  - `scout_attribution_quality (numeric)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------+--------------------------------------
id                        | fdd53879-cf02-43f6-9158-e8a4ac860677
window_hours              | 1
computed_at               | 2026-05-26 05:47:17.476009+00
n_strategies              | 0
avg_composite_fitness     | 0
avg_sharpe                | 0
avg_sortino               | 0
avg_calmar                | 0
avg_expectancy            | 0
median_composite_fitness  | 0
top_decile_fitness        | 0
bottom_decile_fitness     | 0
fitness_trend             | 0
mutation_survival_rate    | 0
scout_attribution_quality | 0
metadata                  | {"agent": "EconomicEfficiencyEngine"}
created_at                | 2026-05-26 05:47:17.489424+00
-[ RECORD 2 ]-------------+--------------------------------------
id                        | 92db0bbd-78db-4c01-b1d3-985107db9e8f
window_hours              | 6
computed_at               | 2026-05-26 05:47:17.476009+00
n_strategies              | 0
avg_composite_fitness     | 0
avg_sharpe                | 0
avg_sortino               | 0
avg_calmar                | 0
avg_expectancy            | 0
median_composite_fitness  | 0
top_decile_fitness        | 0
bottom_decile_fitness     | 0
fitness_trend             | 0
mutation_survival_rate    | 0
scout_attribution_quality | 0
metadata                  | {"agent": "EconomicEfficiencyEngine"}
created_at                | 2026-05-26 05:47:17.51989+00


```

---

## 30. `ensemble_execution`

- **Row count:** 0
- **Columns (8):**
  - `id (uuid)`
  - `executed_at (timestamp with time zone)`
  - `n_signals_processed (integer)`
  - `n_trades_generated (integer)`
  - `consensus_trades (jsonb)`
  - `strategy_weights_used (jsonb)`
  - `regime_context (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 31. `event_snapshots`

- **Row count:** 1307
- **Columns (5):**
  - `id (text)`
  - `aggregate_id (text)`
  - `version (integer)`
  - `state (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id           | 566c2065c3814657
aggregate_id | 000aa349-7efa-4865-aacb-97ed55a36d21
version      | 1
state        | {"cagr": 0.0, "sharpe": 0.0, "win_rate": 0.14285714285714285, "strategy_id": "000aa349-7efa-4865-aacb-97ed55a36d21", "max_drawdown": -0.09769602896262386, "total_trades": 2, "backtest_status": "failed", "passed_validation": false}
created_at   | 2026-05-20 11:17:22.690048+00
-[ RECORD 2 ]+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id           | 5fea0b733e5c46da
aggregate_id | 005ec4eb-1d17-4c18-abc4-75ede2e7cbe9
version      | 1
state        | {"cagr": 0.0, "sharpe": 0.0, "win_rate": 0.0, "strategy_id": "005ec4eb-1d17-4c18-abc4-75ede2e7cbe9", "max_drawdown": 0.0, "total_trades": 0, "backtest_status": "failed", "passed_validation": false}
created_at   | 2026-05-20 11:17:22.690048+00


```

---

## 32. `event_store`

- **Row count:** 4457
- **Columns (14):**
  - `id (text)`
  - `aggregate_id (text)`
  - `aggregate_type (text)`
  - `event_type (text)`
  - `event_version (integer)`
  - `data (jsonb)`
  - `trace_id (text)`
  - `parent_event_id (text)`
  - `created_at (timestamp with time zone)`
  - `sequence (integer)`
  - `version (text)`
  - `metadata (jsonb)`
  - `hash_prev (text)`
  - `hash_self (text)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---+----------------------------------------------------------------------------------------------------------------------------------------------------------------
id              | 71aed18ded63401c
aggregate_id    | 0017d39c6e9848e6
aggregate_type  | strategy
event_type      | ideator
event_version   | 1
data            | {"actor": "MutatorAgent", "stage": "ideator", "status": "completed", "strategy_id": "9c18524a-fde5-4e3d-b690-dc8b56141aca", "lifecycle_id": "c18fffc1c8d246d2"}
trace_id        | 0017d39c6e9848e6
parent_event_id |
created_at      | 2026-05-18 10:22:35.25925+00
sequence        | 1
version         | 1.0
metadata        | {"mode": "unknown", "status": "pending_code", "strategy_name": "trend_following_equity_tmpl_063225_m1"}
hash_prev       |
hash_self       | 84493c563bcb63ecdfd8cfb83c33c0ca515c984fbfafda223ba2773d20af75f9
-[ RECORD 2 ]---+----------------------------------------------------------------------------------------------------------------------------------------------------------------
id              | cbd5818998ed48c2
aggregate_id    | 0017d39c6e9848e6
aggregate_type  | strategy
event_type      | coder
event_version   | 1
data            | {"actor": "CoderAgent", "stage": "coder", "status": "completed", "strategy_id": "9c18524a-fde5-4e3d-b690-dc8b56141aca", "lifecycle_id": "0c1f66dd44944312"}
trace_id        | 0017d39c6e9848e6
parent_event_id |
created_at      | 2026-05-18 10:48:21.171519+00
sequence        | 2
version         | 1.0
metadata        | {"code_len": 1000, "strategy_name": "trend_following_equity_tmpl_063225_m1"}
hash_prev       | 84493c563bcb63ecdfd8cfb83c33c0ca515c984fbfafda223ba2773d20af75f9
hash_self       | ffb3311c8b4073beba2de67cdc720cd70426d7708a6f699a2947c7d745559faf


```

---

## 33. `execution_dead_letter`

- **Row count:** 16
- **Columns (17):**
  - `id (uuid)`
  - `order_key (text)`
  - `strategy_id (uuid)`
  - `symbol (text)`
  - `side (text)`
  - `quantity (numeric)`
  - `failure_reason (text)`
  - `last_state (text)`
  - `broker_order_id (text)`
  - `client_order_id (text)`
  - `severity (text)`
  - `resolved (boolean)`
  - `resolution (text)`
  - `retry_count (integer)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`
  - `resolved_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---+---------------------------------------
id              | a9dbb589-96e7-4f1f-9d3a-27c731e69f51
order_key       | a8762355:UNKNOWN:buy:4dc4e722:20260525
strategy_id     | a8762355-ffc4-48f6-b318-b3de08e0b5cd
symbol          | UNKNOWN
side            | buy
quantity        | 10
failure_reason  | submission_exhausted
last_state      | risk_approved
broker_order_id |
client_order_id | atlas_311efbd5bd4eb131
severity        | high
resolved        | f
resolution      |
retry_count     | 0
metadata        |
created_at      | 2026-05-25 03:41:35.723798+00
resolved_at     |
-[ RECORD 2 ]---+---------------------------------------
id              | 111aab98-b72d-4560-99ce-877ba772f654
order_key       | 5d1fc873:UNKNOWN:buy:d75ccfc6:20260525
strategy_id     | 5d1fc873-f927-4845-85d8-b75724fcb39f
symbol          | UNKNOWN
side            | buy
quantity        | 10
failure_reason  | submission_exhausted
last_state      | risk_approved
broker_order_id |
client_order_id | atlas_0a6e9e8a1110b63c
severity        | high
resolved        | f
resolution      |
retry_count     | 0
metadata        |
created_at      | 2026-05-25 03:41:46.551328+00
resolved_at     |


```

---

## 34. `execution_intelligence`

- **Row count:** 1
- **Columns (11):**
  - `id (uuid)`
  - `timestamp (timestamp with time zone)`
  - `symbol (text)`
  - `broker (text)`
  - `avg_slippage_bps (numeric)`
  - `fill_latency_ms (numeric)`
  - `rejection_rate (numeric)`
  - `fill_quality_score (numeric)`
  - `execution_regime (text)`
  - `sample_size (integer)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]------+--------------------------------------------------------
id                 | 60917ed7-b146-4f35-b50b-bac9a2d536ad
timestamp          | 2026-05-22 11:01:13.110565+00
symbol             | E2E
broker             | paper
avg_slippage_bps   | 0.5
fill_latency_ms    |
rejection_rate     |
fill_quality_score | 0.90000000000000002220446049250313080847263336181640625
execution_regime   | normal
sample_size        | 0
metadata           | {}


```

---

## 35. `execution_log`

- **Row count:** 98
- **Columns (14):**
  - `id (uuid)`
  - `order_key (text)`
  - `strategy_id (uuid)`
  - `symbol (text)`
  - `side (text)`
  - `quantity (numeric)`
  - `price (numeric)`
  - `state (text)`
  - `broker_order_id (text)`
  - `client_order_id (text)`
  - `broker (text)`
  - `error_message (text)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---+---------------------------------------
id              | d3844a2b-4a11-4b8e-b9d5-ee9e360d80fb
order_key       | a8762355:UNKNOWN:buy:4dc4e722:20260525
strategy_id     | a8762355-ffc4-48f6-b318-b3de08e0b5cd
symbol          | UNKNOWN
side            | buy
quantity        | 10
price           |
state           | signal_received
broker_order_id |
client_order_id | atlas_311efbd5bd4eb131
broker          | alpaca
error_message   |
metadata        |
created_at      | 2026-05-25 03:41:25.817045+00
-[ RECORD 2 ]---+---------------------------------------
id              | 488b76c5-5c66-42d0-b556-f420f7513f2f
order_key       | a8762355:UNKNOWN:buy:4dc4e722:20260525
strategy_id     |
symbol          | UNKNOWN
side            | UNKNOWN
quantity        |
price           |
state           | risk_approved
broker_order_id |
client_order_id |
broker          | alpaca
error_message   |
metadata        |
created_at      | 2026-05-25 03:41:25.940403+00


```

---

## 36. `execution_realism`

- **Row count:** 0
- **Columns (13):**
  - `id (uuid)`
  - `simulated_at (timestamp with time zone)`
  - `n_trades_simulated (integer)`
  - `avg_fill_probability (numeric)`
  - `avg_expected_slippage_bps (numeric)`
  - `avg_expected_partial_pct (numeric)`
  - `avg_simulated_latency_ms (numeric)`
  - `avg_market_impact_bps (numeric)`
  - `exhaustion_scenario (jsonb)`
  - `execution_degradation_score (numeric)`
  - `liquidity_state (jsonb)`
  - `simulated_fills (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 37. `external_scout_memory`

- **Row count:** 0
- **Columns (11):**
  - `id (uuid)`
  - `source (text)`
  - `source_sub (text)`
  - `source_reliability (numeric)`
  - `timestamp (timestamp with time zone)`
  - `sentiment (numeric)`
  - `mentioned_tickers (jsonb)`
  - `hypothesis_score (numeric)`
  - `signal_direction (text)`
  - `metadata (jsonb)`
  - `details (text)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 38. `failed_inserts`

- **Row count:** 331
- **Columns (6):**
  - `id (uuid)`
  - `table_name (text)`
  - `query (text)`
  - `params (jsonb)`
  - `reason (text)`
  - `inserted_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id          | 06072d0b-1ae5-4730-bd76-470a17bff7ec
table_name  | feature_importance
query       |                                                                                                                                                                                                                                   +
            |             INSERT INTO feature_importance                                                                                                                                                                                        +
            |                 (id, feature_name, feature_importance_score,                                                                                                                                                                      +
            |                  n_uses, survival_rate, dominant_archetype, metadata)                                                                                                                                                             +
            |             VALUES                                                                                                                                                                                                                +
            |                 (:id, :name, 0.5, 1, 0.5, '',                                                                                                                                                                                     +
            |                  CAST(:metadata AS jsonb))                                                                                                                                                                                        +
            |
params      | {"id": "eddd7159671c4ff7", "name": "synthetic_price_vs_vwap_pct_difference_relative_volume", "metadata": "{\"evolved\": true, \"parent_id\": null, \"evolved_at\": \"2026-05-22T07:13:24.042969+00:00\"}"}
reason      | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DataError'>: invalid input for query argument $1: 'eddd7159671c4ff7' (invalid UUID 'eddd7159671c4ff7': length must be between 32..36 characters, got 16)+
            | [SQL:                                                                                                                                                                                                                             +
            |             INSERT INTO feature_importance                                                                                                                                                                                        +
            |                 (id, feature_name, feature_importance_score,                                                                                                                                                                      +
            |                  n_uses, survival_rate, dominant_archetype, metadata)                                                                                                                                                             +
            |             VALUES                                                                                                                                                                                                                +
            |                 ($1, $2, 0.5, 1, 0.5, '',                                                                                                                                                                                         +
            |                  CAST($3 AS jsonb))                                                                                                                                                                                               +
            |             ]                                                                                                                                                                                                                     +
            | [parameters: ('eddd7159671c4ff7', 'synthetic_price_vs_vwap_pct_difference_relative_volume', '{"evolved": true, "parent_id": null, "evolved_at": "2026-05-22T07:13:24.042969+00:00"}')]                                            +
            | (Background on this error at: https://sqlalche.me/e/20/dbapi)
inserted_at | 2026-05-22 07:13:24.045624+00
-[ RECORD 2 ]-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id          | cd0f973c-1ca5-4103-b7e7-d50189bda01b
table_name  | feature_importance
query       |                                                                                                                                                                                                                                   +
            |             INSERT INTO feature_importance                                                                                                                                                                                        +
            |                 (id, feature_name, feature_importance_score,                                                                                                                                                                      +
            |                  n_uses, survival_rate, dominant_archetype, metadata)                                                                                                                                                             +
            |             VALUES                                                                                                                                                                                                                +
            |                 (:id, :name, 0.5, 1, 0.5, '',                                                                                                                                                                                     +
            |                  CAST(:metadata AS jsonb))                                                                                                                                                                                        +
            |
params      | {"id": "d53be27d5b2e42c8", "name": "mutated_ema_spread_pct_lagged", "metadata": "{\"evolved\": true, \"parent_id\": \"700a86ec-bed9-4f39-9aee-af8a0732d684\", \"evolved_at\": \"2026-05-22T07:13:24.210273+00:00\"}"}
reason      | (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DataError'>: invalid input for query argument $1: 'd53be27d5b2e42c8' (invalid UUID 'd53be27d5b2e42c8': length must be between 32..36 characters, got 16)+
            | [SQL:                                                                                                                                                                                                                             +
            |             INSERT INTO feature_importance                                                                                                                                                                                        +
            |                 (id, feature_name, feature_importance_score,                                                                                                                                                                      +
            |                  n_uses, survival_rate, dominant_archetype, metadata)                                                                                                                                                             +
            |             VALUES                                                                                                                                                                                                                +
            |                 ($1, $2, 0.5, 1, 0.5, '',                                                                                                                                                                                         +
            |                  CAST($3 AS jsonb))                                                                                                                                                                                               +
            |             ]                                                                                                                                                                                                                     +
            | [parameters: ('d53be27d5b2e42c8', 'mutated_ema_spread_pct_lagged', '{"evolved": true, "parent_id": "700a86ec-bed9-4f39-9aee-af8a0732d684", "evolved_at": "2026-05-22T07:13:24.210273+00:00"}')]                                   +
            | (Background on this error at: https://sqlalche.me/e/20/dbapi)
inserted_at | 2026-05-22 07:13:24.217217+00


```

---

## 39. `failure_analysis`

- **Row count:** 273
- **Columns (13):**
  - `id (text)`
  - `trace_id (text)`
  - `analysis_type (text)`
  - `confidence (numeric)`
  - `root_causes (jsonb)`
  - `systemic_patterns (jsonb)`
  - `governance_recommendations (jsonb)`
  - `mutation_collapse_warnings (jsonb)`
  - `feature_saturation_alerts (jsonb)`
  - `n_failures_analyzed (integer)`
  - `advisory_only (boolean)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------------+-----------------------------------------------------------------------------------------------------------
id                         | 113d8494-29dc-4007-9511-6485f1b114f8
trace_id                   | 2f967d3e-fecf-49f0-81a3-aee987e84647
analysis_type              | periodic_postmortem
confidence                 | 0.6999999999999999555910790149937383830547332763671875
root_causes                | ["Feature saturation: Feature 'bollinger_band_position' appears in 20/30 failed strategies"]
systemic_patterns          | ["Feature saturation: Feature 'bollinger_band_position' appears in 20/30 failed strategies"]
governance_recommendations | ["Diversify feature selection in strategy generation."]
mutation_collapse_warnings | []
feature_saturation_alerts  | ["Feature 'bollinger_band_position' appears in 20/30 failed strategies"]
n_failures_analyzed        | 30
advisory_only              | t
metadata                   | {"agent": "FailureAnalysisEngine", "llm_used": false, "risk_level": "high", "temporal_pattern": "unknown"}
created_at                 | 2026-05-27 06:59:49.63906+00
-[ RECORD 2 ]--------------+-----------------------------------------------------------------------------------------------------------
id                         | b147ac66-9884-4eb9-9a11-824726c783d5
trace_id                   | 5dbff435-235f-4bef-a32c-7b6ffc6ca460
analysis_type              | periodic_postmortem
confidence                 | 0.6999999999999999555910790149937383830547332763671875
root_causes                | ["Feature saturation: Feature 'bollinger_band_position' appears in 20/30 failed strategies"]
systemic_patterns          | ["Feature saturation: Feature 'bollinger_band_position' appears in 20/30 failed strategies"]
governance_recommendations | ["Diversify feature selection in strategy generation."]
mutation_collapse_warnings | []
feature_saturation_alerts  | ["Feature 'bollinger_band_position' appears in 20/30 failed strategies"]
n_failures_analyzed        | 30
advisory_only              | t
metadata                   | {"agent": "FailureAnalysisEngine", "llm_used": false, "risk_level": "high", "temporal_pattern": "unknown"}
created_at                 | 2026-05-27 06:59:57.431614+00


```

---

## 40. `feature_importance`

- **Row count:** 485
- **Columns (13):**
  - `id (uuid)`
  - `feature_name (text)`
  - `feature_importance_score (numeric)`
  - `avg_composite_score (numeric)`
  - `std_composite_score (numeric)`
  - `n_uses (integer)`
  - `survival_rate (numeric)`
  - `decay_score (numeric)`
  - `dominant_archetype (text)`
  - `archetype_focus_pct (numeric)`
  - `top_archetypes (jsonb)`
  - `computed_at (timestamp with time zone)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]------------+-------------------------------------------------------------------------------------------------------------------------
id                       | dbd0b8ae-c2d9-46ed-bf19-2a026ac6aeeb
feature_name             | mutated_bollinger_band_position_accelerated
feature_importance_score | 0.5
avg_composite_score      |
std_composite_score      |
n_uses                   | 1
survival_rate            | 0.5
decay_score              |
dominant_archetype       |
archetype_focus_pct      |
top_archetypes           | {}
computed_at              | 2026-05-22 07:21:39.11634+00
metadata                 | {"evolved": true, "parent_id": "0c35c70f-8372-49c7-9f20-490a2659e8ba", "evolved_at": "2026-05-22T07:21:39.113685+00:00"}
-[ RECORD 2 ]------------+-------------------------------------------------------------------------------------------------------------------------
id                       | a5eea9cc-8c36-48d4-9133-ed8d3d585ee8
feature_name             | synthetic_mutated_ema_spread_pct_vol_adjusted_sum_mutated_bollinger_band_position_accelerated
feature_importance_score | 0.5
avg_composite_score      |
std_composite_score      |
n_uses                   | 1
survival_rate            | 0.5
decay_score              |
dominant_archetype       |
archetype_focus_pct      |
top_archetypes           | {}
computed_at              | 2026-05-22 07:27:42.060294+00
metadata                 | {"evolved": true, "parent_id": null, "evolved_at": "2026-05-22T07:27:42.053348+00:00"}


```

---

## 41. `features`

- **Row count:** 1458631
- **Columns (4):**
  - `time (timestamp with time zone)`
  - `symbol (text)`
  - `feature_name (text)`
  - `value (numeric)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]+-----------------------------------------------------------------
time         | 2026-05-13 18:01:00+00
symbol       | BNBUSDT
feature_name | returns
value        | 0.0005514651086533373103293342865072190761566162109375
-[ RECORD 2 ]+-----------------------------------------------------------------
time         | 2026-05-13 18:01:00+00
symbol       | BNBUSDT
feature_name | log_returns
value        | 0.00055131310764990558957732158518183496198616921901702880859375


```

---

## 42. `features_wide_bootstrap`

- **Row count:** 17422
- **Columns (10):**
  - `time (timestamp with time zone)`
  - `symbol (text)`
  - `sma_10 (numeric)`
  - `sma_20 (numeric)`
  - `sma_50 (numeric)`
  - `ema_12 (numeric)`
  - `ema_26 (numeric)`
  - `macd (numeric)`
  - `macd_signal (numeric)`
  - `rsi_14 (numeric)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------------------
time        | 2025-05-20 11:00:00+00
symbol      | BTCUSDT
sma_10      | 105540.655
sma_20      | 105534.21099999998
sma_50      | 104691.40179999999
ema_12      | 105364.04540766076
ema_26      | 105141.53679896475
macd        | 222.5086086960073
macd_signal | 347.5358655594213
rsi_14      | 46.6237116614115
-[ RECORD 2 ]-----------------------
time        | 2025-05-20 12:00:00+00
symbol      | BTCUSDT
sma_10      | 105408.656
sma_20      | 105505.389
sma_50      | 104709.8656
ema_12      | 105274.19226802063
ema_26      | 105114.75629533772
macd        | 159.43597268291342
macd_signal | 309.91588698411977
rsi_14      | 41.1715736413131


```

---

## 43. `follower_reconciliation`

- **Row count:** 0
- **Columns (13):**
  - `id (text)`
  - `trace_id (text)`
  - `leader_id (text)`
  - `follower_id (text)`
  - `reconciliation_type (text)`
  - `n_positions_checked (integer)`
  - `n_mismatches (integer)`
  - `exposure_delta (numeric)`
  - `pnl_delta (numeric)`
  - `repair_actions (jsonb)`
  - `reconciliation_score (numeric)`
  - `metadata (jsonb)`
  - `reconciled_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 44. `hypothesis_registry`

- **Row count:** 282
- **Columns (17):**
  - `id (text)`
  - `trace_id (text)`
  - `statement (text)`
  - `observation_source (text)`
  - `testable_prediction (text)`
  - `confidence (numeric)`
  - `evidence_count (integer)`
  - `contradiction_count (integer)`
  - `regime_scope (text)`
  - `replay_score (numeric)`
  - `decay_rate (numeric)`
  - `status (text)`
  - `evidence (jsonb)`
  - `metadata (jsonb)`
  - `last_confirmed_at (timestamp with time zone)`
  - `created_at (timestamp with time zone)`
  - `updated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------+----------------------------------------------------------------------------
id                  | b7b57172-78b9-4218-876e-6c8d13c01472
trace_id            | 3a85c75e-3f05-4233-8300-16e6a67f204d
statement           | Feature 'rsi_14' is over-represented (156 uses) â€” saturation risk
observation_source  | feature_importance
testable_prediction | Strategies avoiding 'rsi_14' will show higher survival rates in next 7 days
confidence          | 0.48999999999999999979183318288278314867056906223297119140625
evidence_count      | 0
contradiction_count | 0
regime_scope        | all
replay_score        | 0
decay_rate          | 0.01000000000000000020816681711721685132943093776702880859375
status              | active
evidence            | []
metadata            | {}
last_confirmed_at   |
created_at          | 2026-05-29 05:17:41.631749+00
updated_at          | 2026-05-29 05:17:41.641814+00
-[ RECORD 2 ]-------+----------------------------------------------------------------------------
id                  | 079e5885-262d-45cb-a14b-77cc7b85e64a
trace_id            | fb56f9d8-6863-4853-9c03-d4d2ac45db7b
statement           | Feature 'rsi_14' is over-represented (156 uses) â€” saturation risk
observation_source  | feature_importance
testable_prediction | Strategies avoiding 'rsi_14' will show higher survival rates in next 7 days
confidence          | 0.33999999999999999666933092612453037872910499572753906250000
evidence_count      | 0
contradiction_count | 0
regime_scope        | all
replay_score        | 0
decay_rate          | 0.01000000000000000020816681711721685132943093776702880859375
status              | active
evidence            | []
metadata            | {}
last_confirmed_at   |
created_at          | 2026-05-28 16:25:09.369188+00
updated_at          | 2026-05-29 05:17:41.641814+00


```

---

## 45. `intelligence_briefs`

- **Row count:** 3
- **Columns (5):**
  - `id (uuid)`
  - `generated_at (timestamp with time zone)`
  - `brief_text (text)`
  - `regime (text)`
  - `strategies_count (integer)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 46. `leader_health_metrics`

- **Row count:** 0
- **Columns (17):**
  - `id (text)`
  - `trace_id (text)`
  - `leader_id (text)`
  - `health_score (numeric)`
  - `leader_state (text)`
  - `drawdown_pct (numeric)`
  - `survivability_score (numeric)`
  - `execution_quality (numeric)`
  - `replay_consistency (numeric)`
  - `drift_stability (numeric)`
  - `portfolio_concentration (numeric)`
  - `slippage_amplification (numeric)`
  - `strategy_mortality_rate (numeric)`
  - `vol_adjusted_return (numeric)`
  - `n_followers (integer)`
  - `metadata (jsonb)`
  - `assessed_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 47. `leader_orders`

- **Row count:** 9
- **Columns (9):**
  - `id (uuid)`
  - `account_ref (text)`
  - `symbol (text)`
  - `side (text)`
  - `qty (numeric)`
  - `price (numeric)`
  - `status (text)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------------------------------
id          | e38c8d91-bbec-43d3-8e69-50d27babf97e
account_ref | SIM_LEADER_001
symbol      | NVDA
side        | buy
qty         | 10
price       | 150.0
status      | filled
metadata    |
created_at  | 2026-05-16 07:50:36.044368+00
-[ RECORD 2 ]-------------------------------------
id          | 2bde95ea-645e-4cd1-b3f1-9db821e12498
account_ref | SIM_LEADER_001
symbol      | NVDA
side        | buy
qty         | 10
price       | 150.0
status      | filled
metadata    |
created_at  | 2026-05-16 07:50:54.208895+00


```

---

## 48. `lifecycle_events`

- **Row count:** 22874
- **Columns (10):**
  - `id (text)`
  - `trace_id (text)`
  - `strategy_id (text)`
  - `stage (text)`
  - `status (text)`
  - `actor (text)`
  - `parent_event_id (text)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`
  - `agent_name (text)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---+-------------------------------------
id              | 2feba3c7c5e245ed
trace_id        | 9d1ba4fc32424fa0
strategy_id     | f78587d1-393c-462e-b8f8-271461d66d19
stage           | ideator
status          | completed
actor           | test_agent
parent_event_id |
metadata        | {"test": true}
created_at      | 2026-05-17 08:52:06.233043+00
agent_name      |
-[ RECORD 2 ]---+-------------------------------------
id              | e1cbe61549f24cd3
trace_id        | 9d1ba4fc32424fa0
strategy_id     | f78587d1-393c-462e-b8f8-271461d66d19
stage           | coder
status          | completed
actor           | CoderAgent
parent_event_id |
metadata        | {"code_len": 500}
created_at      | 2026-05-17 08:52:06.252343+00
agent_name      |


```

---

## 49. `liquidity_intelligence`

- **Row count:** 6201
- **Columns (10):**
  - `id (uuid)`
  - `symbol (text)`
  - `timestamp (timestamp with time zone)`
  - `avg_spread_bps (numeric)`
  - `depth_imbalance (numeric)`
  - `liquidity_score (numeric)`
  - `slippage_risk (numeric)`
  - `market_impact_estimate (numeric)`
  - `liquidity_regime (text)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------+---------------------------------------------------------------
id                     | 35bcb2b4-0ce0-4cc1-a61f-01942f98e6cb
symbol                 | BTCUSDT
timestamp              | 2026-05-19 15:21:06.249881+00
avg_spread_bps         | 0.001299999999999999940325512426397835952229797840118408203125
depth_imbalance        | 13.4318000000000008498091119690798223018646240234375
liquidity_score        | 0
slippage_risk          | 0.40000000000000002220446049250313080847263336181640625
market_impact_estimate | 307.52357999999998128259903751313686370849609375
liquidity_regime       | dangerous
metadata               | {}
-[ RECORD 2 ]----------+---------------------------------------------------------------
id                     | b8a74afb-cdfb-4663-9e6d-b0e493604125
symbol                 | ETHUSDT
timestamp              | 2026-05-19 15:21:06.376598+00
avg_spread_bps         | 0.04700000000000000011102230246251565404236316680908203125
depth_imbalance        | 0.00830000000000000008604228440844963188283145427703857421875
liquidity_score        | 80.0199999999999960209606797434389591217041015625
slippage_risk          | 0.3970000000000000195399252334027551114559173583984375
market_impact_estimate | 8.444725999999999288547769538126885890960693359375
liquidity_regime       | excellent
metadata               | {}


```

---

## 50. `market_data_l1`

- **Row count:** 44820
- **Columns (11):**
  - `time (timestamp with time zone)`
  - `symbol (text)`
  - `open (numeric)`
  - `high (numeric)`
  - `low (numeric)`
  - `close (numeric)`
  - `volume (numeric)`
  - `source (text)`
  - `interval (text)`
  - `asset_class (text)`
  - `ingestion_time (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--+------------------------------------------------------
time           | 2026-05-13 17:36:00+00
symbol         | SOLUSDT
open           | 90.840000000000003410605131648480892181396484375
high           | 90.900000000000005684341886080801486968994140625
low            | 90.8299999999999982946974341757595539093017578125
close          | 90.8799999999999954525264911353588104248046875
volume         | 1435.60500000000001818989403545856475830078125
source         | binance
interval       | 1m
asset_class    | crypto
ingestion_time | 2026-05-15 04:14:27.98838+00
-[ RECORD 2 ]--+------------------------------------------------------
time           | 2026-05-13 17:36:00+00
symbol         | BTCUSDT
open           | 79339.479999999995925463736057281494140625
high           | 79341.580000000001746229827404022216796875
low            | 79339.47000000000116415321826934814453125
close          | 79341.580000000001746229827404022216796875
volume         | 0.741330000000000044479975258582271635532379150390625
source         | binance
interval       | 1m
asset_class    | crypto
ingestion_time | 2026-05-15 04:14:27.98838+00


```

---

## 51. `market_data_l1_bootstrap`

- **Row count:** 17520
- **Columns (11):**
  - `time (timestamp with time zone)`
  - `symbol (text)`
  - `open (numeric)`
  - `high (numeric)`
  - `low (numeric)`
  - `close (numeric)`
  - `volume (numeric)`
  - `source (text)`
  - `interval (text)`
  - `asset_class (text)`
  - `ingestion_time (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--+------------------------------
time           | 2025-05-18 10:00:00+00
symbol         | BTCUSDT
open           | 103868.48
high           | 103935.4
low            | 103800.0
close          | 103856.81
volume         | 261.38595
source         | historical_backfill
interval       | 1h
asset_class    | crypto
ingestion_time | 2026-05-18 16:30:57.983271+00
-[ RECORD 2 ]--+------------------------------
time           | 2025-05-18 11:00:00+00
symbol         | BTCUSDT
open           | 103856.8
high           | 103998.98
low            | 103800.0
close          | 103800.54
volume         | 280.93869
source         | historical_backfill
interval       | 1h
asset_class    | crypto
ingestion_time | 2026-05-18 16:30:57.983271+00


```

---

## 52. `market_data_l2`

- **Row count:** 61704
- **Columns (6):**
  - `time (timestamp with time zone)`
  - `symbol (text)`
  - `bids (jsonb)`
  - `asks (jsonb)`
  - `spread (numeric)`
  - `mid_price (numeric)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
time      | 2026-05-13 17:36:06.449+00
symbol    | BTCUSDT
bids      | {"79338.60000000": 0.00007, "79338.61000000": 0.00007, "79339.09000000": 0.28571, "79339.17000000": 0.11342, "79339.31000000": 0.00407, "79339.45000000": 0.00014, "79339.47000000": 0.72978, "79339.48000000": 0.00008, "79339.96000000": 0.0029, "79339.97000000": 0.41626, "79340.13000000": 0.00008, "79340.58000000": 2.17725, "79340.59000000": 1.41589, "79340.60000000": 0.44024, "79340.630... [TRUNCATED]
asks      | {"79341.58000000": 0.11027, "79341.59000000": 0.0007, "79342.64000000": 0.00007, "79342.98000000": 0.00007, "79343.65000000": 0.00007, "79343.96000000": 0.00022, "79343.97000000": 0.11379, "79344.00000000": 0.0008, "79344.49000000": 0.00007, "79344.74000000": 0.00007, "79345.16000000": 0.0001, "79345.18000000": 0.0001, "79345.29000000": 0.00014, "79345.46000000": 0.00007, "79345.520000... [TRUNCATED]
spread    | 0.009999999994761310517787933349609375
mid_price | 79341.5750000000116415321826934814453125
-[ RECORD 2 ]---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
time      | 2026-05-13 17:36:06.497+00
symbol    | SOLUSDT
bids      | {"90.69000000": 422.773, "90.70000000": 330.922, "90.71000000": 216.097, "90.72000000": 559.046, "90.73000000": 265.34, "90.74000000": 290.98, "90.75000000": 484.631, "90.76000000": 334.337, "90.77000000": 412.068, "90.78000000": 590.092, "90.79000000": 428.118, "90.80000000": 452.239, "90.81000000": 961.461, "90.82000000": 568.192, "90.83000000": 2630.988, "90.84000000": 1242.994, "90... [TRUNCATED]
asks      | {"90.89000000": 788.621, "90.90000000": 543.063, "90.91000000": 706.728, "90.92000000": 749.927, "90.93000000": 370.888, "90.94000000": 254.592, "90.95000000": 529.575, "90.96000000": 360.14, "90.97000000": 420.505, "90.98000000": 292.397, "90.99000000": 498.757, "91.00000000": 658.461, "91.01000000": 984.32, "91.02000000": 2668.437, "91.03000000": 187.509, "91.04000000": 341.616, "91.... [TRUNCATED]
spread    | 0.0100000000000051159076974727213382720947265625
mid_price | 90.884999999999990905052982270717620849609375


```

---

## 53. `market_regime_memory`

- **Row count:** 12218
- **Columns (18):**
  - `id (uuid)`
  - `symbol (text)`
  - `asset_class (text)`
  - `timeframe (text)`
  - `timestamp (timestamp with time zone)`
  - `volatility_regime (text)`
  - `trend_regime (text)`
  - `liquidity_regime (text)`
  - `correlation_regime (text)`
  - `atr_percentile (numeric)`
  - `realized_volatility (numeric)`
  - `relative_volume (numeric)`
  - `spread_bps (numeric)`
  - `compression_detected (boolean)`
  - `expansion_detected (boolean)`
  - `vwap_deviation_pct (numeric)`
  - `confidence_score (numeric)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------+------------------------------------------------------------
id                   | d07ee1f9-cc62-4a08-b68d-001162ab7eab
symbol               | BTCUSDT
asset_class          | crypto
timeframe            | 1m
timestamp            | 2026-05-19 15:21:06.212327+00
volatility_regime    | high_vol
trend_regime         | choppy
liquidity_regime     | dangerous
correlation_regime   | clustered
atr_percentile       | 71.752577319587629745001322589814662933349609375
realized_volatility  | 0.1423580000000000123083765402043354697525501251220703125
relative_volume      | 0.294700000000000017497114868092467077076435089111328125
spread_bps           | 0
compression_detected | t
expansion_detected   | f
vwap_deviation_pct   | 0.039800000000000002042810365310288034379482269287109375
confidence_score     | 1
metadata             | {}
-[ RECORD 2 ]--------+------------------------------------------------------------
id                   | 771d1989-1366-40ca-a8ae-e6ad6b738441
symbol               | ETHUSDT
asset_class          | crypto
timeframe            | 1m
timestamp            | 2026-05-19 15:21:06.445932+00
volatility_regime    | high_vol
trend_regime         | choppy
liquidity_regime     | dangerous
correlation_regime   | clustered
atr_percentile       | 71.9587628865979382908335537649691104888916015625
realized_volatility  | 0.17302600000000001312372432948905043303966522216796875
relative_volume      | 0.2462999999999999911626247239837539382278919219970703125
spread_bps           | 0
compression_detected | t
expansion_detected   | f
vwap_deviation_pct   | 0.008500000000000000610622663543836097232997417449951171875
confidence_score     | 1
metadata             | {}


```

---

## 54. `meta_reasoning_log`

- **Row count:** 0
- **Columns (10):**
  - `id (text)`
  - `trace_id (text)`
  - `advisory_type (text)`
  - `confidence (numeric)`
  - `reasoning_text (text)`
  - `system_state_snapshot (jsonb)`
  - `recommendations (jsonb)`
  - `advisory_only (boolean)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 55. `monitoring_metrics`

- **Row count:** 0
- **Columns (4):**
  - `id (text)`
  - `recorded_at (timestamp with time zone)`
  - `counters (jsonb)`
  - `latencies (jsonb)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 56. `monte_carlo_analysis`

- **Row count:** 0
- **Columns (10):**
  - `id (uuid)`
  - `strategy_id (uuid)`
  - `monte_carlo_survival_score (numeric)`
  - `expected_tail_drawdown (numeric)`
  - `probabilistic_sharpe (numeric)`
  - `ci_low_90pct (numeric)`
  - `ci_high_90pct (numeric)`
  - `n_simulations (integer)`
  - `n_trades_input (integer)`
  - `simulated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 57. `mutation_lineage_log`

- **Row count:** 398
- **Columns (12):**
  - `id (character varying)`
  - `tracked_at (timestamp with time zone)`
  - `n_mutations_analyzed (integer)`
  - `n_lineages_identified (integer)`
  - `n_dominant_lineages (integer)`
  - `lineages (jsonb)`
  - `survival_rates (jsonb)`
  - `regime_specialization (jsonb)`
  - `drawdown_behavior (jsonb)`
  - `dominant_lineages (jsonb)`
  - `ecosystem_stats (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                    | 01a198ea-67ad-4ced-b273-55b9f8bafd7a
tracked_at            | 2026-05-25 14:18:24.553736+00
n_mutations_analyzed  | 945
n_lineages_identified | 11
n_dominant_lineages   | 10
lineages              | [{"depth": 3, "members": [{"role": "root", "depth": 0, "strategy_id": "37686ba2-5ba8-446c-87b3-26333071089e"}, {"role": "child", "depth": 1, "child_score": 0.0, "strategy_id": "1ae5fc69-e396-41ca-acca-a5cfb0a3f751", "child_sharpe": 0.0, "mutation_type": "repair::threshold_adjustment", "child_drawdown": 0.0, "child_win_rate": 0.0}, {"role": "child", "depth": 1, "child_score"... [TRUNCATED]
survival_rates        | [{"n_total": 393, "root_id": "37686ba2-5ba8-446c-87b3-26333071089e", "lineage_id": "73a87dd0-1bd", "n_survived": 0, "n_generations": 4, "survival_rate": 0.0}, {"n_total": 294, "root_id": "eb49402e-122c-4106-bc6e-bfb3b0c288a6", "lineage_id": "51b01bcc-59b", "n_survived": 0, "n_generations": 3, "survival_rate": 0.0}, {"n_total": 91, "root_id": "b5b78b05-3296-4feb-8277-1db1526... [TRUNCATED]
regime_specialization | {"11a94b10-9c8": {"dominant_state": "unknown", "n_specialized_states": 0, "lifecycle_distribution": {}}, "25abdf97-388": {"dominant_state": "unknown", "n_specialized_states": 0, "lifecycle_distribution": {}}, "40b29cef-e02": {"dominant_state": "unknown", "n_specialized_states": 0, "lifecycle_distribution": {}}, "4e65a336-955": {"dominant_state": "unknown", "n_specialized_st... [TRUNCATED]
drawdown_behavior     | {"11a94b10-9c8": {"avg_drawdown": 0.0, "max_drawdown": 0.0, "min_drawdown": 0.0, "n_members_with_dd": 3}, "25abdf97-388": {"avg_drawdown": 0.0, "max_drawdown": 0.0, "min_drawdown": 0.0, "n_members_with_dd": 3}, "40b29cef-e02": {"avg_drawdown": 0.0, "max_drawdown": 0.0, "min_drawdown": 0.0, "n_members_with_dd": 68}, "4e65a336-955": {"avg_drawdown": 0.0, "max_drawdown": 0.0, ... [TRUNCATED]
dominant_lineages     | [{"root_id": "37686ba2-5ba8-446c-87b3-26333071089e", "n_members": 393, "lineage_id": "73a87dd0-1bd", "n_generations": 4, "survival_rate": 0.0, "mutation_types": ["repair::rsi_threshold_shift", "repair::threshold_adjustment", "refinement::hold_time_adjustment", "simplification::condition_removal", "repair::regime_filter_adjustment", "refinement::cooldown_adjustment"], "avg_c... [TRUNCATED]
ecosystem_stats       | {"n_trees": 18, "avg_depth": 1.5, "max_depth": 3, "n_singletons": 0}
metadata              | {"method": "bfs_tree_building"}
-[ RECORD 2 ]---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                    | daa5cef4-ba68-4811-980e-f530d94ac8dc
tracked_at            | 2026-05-25 14:18:39.848678+00
n_mutations_analyzed  | 945
n_lineages_identified | 11
n_dominant_lineages   | 10
lineages              | [{"depth": 3, "members": [{"role": "root", "depth": 0, "strategy_id": "37686ba2-5ba8-446c-87b3-26333071089e"}, {"role": "child", "depth": 1, "child_score": 0.0, "strategy_id": "1ae5fc69-e396-41ca-acca-a5cfb0a3f751", "child_sharpe": 0.0, "mutation_type": "repair::threshold_adjustment", "child_drawdown": 0.0, "child_win_rate": 0.0}, {"role": "child", "depth": 1, "child_score"... [TRUNCATED]
survival_rates        | [{"n_total": 393, "root_id": "37686ba2-5ba8-446c-87b3-26333071089e", "lineage_id": "6d023e22-950", "n_survived": 0, "n_generations": 4, "survival_rate": 0.0}, {"n_total": 294, "root_id": "eb49402e-122c-4106-bc6e-bfb3b0c288a6", "lineage_id": "f2b42719-9e2", "n_survived": 0, "n_generations": 3, "survival_rate": 0.0}, {"n_total": 91, "root_id": "b5b78b05-3296-4feb-8277-1db1526... [TRUNCATED]
regime_specialization | {"2852e8d3-e21": {"dominant_state": "unknown", "n_specialized_states": 0, "lifecycle_distribution": {}}, "460b1fd1-4e5": {"dominant_state": "unknown", "n_specialized_states": 0, "lifecycle_distribution": {}}, "5a374ae3-ffe": {"dominant_state": "unknown", "n_specialized_states": 0, "lifecycle_distribution": {}}, "5b21b85a-ee0": {"dominant_state": "unknown", "n_specialized_st... [TRUNCATED]
drawdown_behavior     | {"2852e8d3-e21": {"avg_drawdown": 0.0, "max_drawdown": 0.0, "min_drawdown": 0.0, "n_members_with_dd": 3}, "460b1fd1-4e5": {"avg_drawdown": 0.0, "max_drawdown": 0.0, "min_drawdown": 0.0, "n_members_with_dd": 90}, "5a374ae3-ffe": {"avg_drawdown": 0.0, "max_drawdown": 0.0, "min_drawdown": 0.0, "n_members_with_dd": 68}, "5b21b85a-ee0": {"avg_drawdown": 0.0, "max_drawdown": 0.0,... [TRUNCATED]
dominant_lineages     | [{"root_id": "37686ba2-5ba8-446c-87b3-26333071089e", "n_members": 393, "lineage_id": "6d023e22-950", "n_generations": 4, "survival_rate": 0.0, "mutation_types": ["repair::rsi_threshold_shift", "repair::threshold_adjustment", "refinement::hold_time_adjustment", "simplification::condition_removal", "repair::regime_filter_adjustment", "refinement::cooldown_adjustment"], "avg_c... [TRUNCATED]
ecosystem_stats       | {"n_trees": 18, "avg_depth": 1.5, "max_depth": 3, "n_singletons": 0}
metadata              | {"method": "bfs_tree_building"}


```

---

## 58. `mutation_memory`

- **Row count:** 981
- **Columns (18):**
  - `id (uuid)`
  - `parent_strategy_id (uuid)`
  - `child_strategy_id (uuid)`
  - `mutation_type (text)`
  - `changed_fields (jsonb)`
  - `parent_sharpe (numeric)`
  - `child_sharpe (numeric)`
  - `sharpe_delta (numeric)`
  - `parent_entry_count (integer)`
  - `child_entry_count (integer)`
  - `parent_trades (integer)`
  - `child_trades (integer)`
  - `created_at (timestamp with time zone)`
  - `parent_composite_score (numeric)`
  - `child_composite_score (numeric)`
  - `score_delta (numeric)`
  - `improved (boolean)`
  - `updated_at (timestamp without time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------+------------------------------------------------
id                     | 0c0c0d4c-d8af-4883-ac5f-d4830f5be462
parent_strategy_id     | 7118f760-5bad-4148-a436-650608c26a29
child_strategy_id      | bf9aed13-eb4d-41ea-b5b9-c3cdb3c74fb8
mutation_type          | repair::threshold_adjustment
changed_fields         | ["entry_conditions", "exit_conditions"]
parent_sharpe          | 0
child_sharpe           | 0
sharpe_delta           | 0
parent_entry_count     | 768
child_entry_count      | 0
parent_trades          | 9
child_trades           | 0
created_at             | 2026-05-18 11:18:41.906464+00
parent_composite_score |
child_composite_score  |
score_delta            |
improved               |
updated_at             | 2026-05-18 11:18:41.906464
-[ RECORD 2 ]----------+------------------------------------------------
id                     | a765b3df-c9c0-4101-96fe-ea9cb74a5492
parent_strategy_id     | 7118f760-5bad-4148-a436-650608c26a29
child_strategy_id      | 5c8314b8-46c3-4c28-8059-39beb2744fae
mutation_type          | repair::threshold_adjustment
changed_fields         | {"relative_volume": {"new": 0.65, "old": 0.88}}
parent_sharpe          | 0
child_sharpe           | 0
sharpe_delta           | 0
parent_entry_count     | 768
child_entry_count      | 0
parent_trades          | 9
child_trades           | 0
created_at             | 2026-05-18 11:18:41.919711+00
parent_composite_score |
child_composite_score  |
score_delta            |
improved               |
updated_at             | 2026-05-18 11:18:41.919711


```

---

## 59. `mutation_outcome_log`

- **Row count:** 0
- **Columns (6):**
  - `id (text)`
  - `mutation_type (text)`
  - `parent_strategy_id (text)`
  - `child_strategy_id (text)`
  - `outcome_score (numeric)`
  - `recorded_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 60. `mutation_policy_log`

- **Row count:** 37
- **Columns (12):**
  - `id (text)`
  - `trace_id (text)`
  - `confidence (numeric)`
  - `advisory (text)`
  - `exploration_vs_exploitation (text)`
  - `entropy_metric (numeric)`
  - `diversification_advisory (text)`
  - `priority_weights (jsonb)`
  - `leaderboard_snapshot (jsonb)`
  - `advisory_only (boolean)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                          | c8c3033cddfb4f8d
trace_id                    | 5fc7fae39d3442da
confidence                  | 0.59999999999999997779553950749686919152736663818359375
advisory                    | Mutation policy balanced â€” continue current exploration strategy.
exploration_vs_exploitation | exploration_dominant
entropy_metric              | 0.9696000000000000174082970261224545538425445556640625
diversification_advisory    | No immediate rebalancing needed.
priority_weights            | {"exit_logic": 0.05, "risk_adjust": 0.1, "combine_with": 0.1, "regime_adapt": 0.1, "parameter_shift": 0.2, "threshold_loosen": 0.15, "indicator_replace": 0.15, "threshold_tighten": 0.15}
leaderboard_snapshot        | [{"total": 60, "failed": 6, "improved": 7, "mutation_type": "repair::threshold_adjustment", "avg_child_score": 40.13, "avg_score_delta": 0.18, "conversion_rate": 53.8, "avg_parent_score": 40.23}, {"total": 42, "failed": 10, "improved": 3, "mutation_type": "simplification::condition_removal", "avg_child_score": 39.28, "avg_score_delta": 0.46, "conversion_rate": 23.1, "... [TRUNCATED]
advisory_only               | t
metadata                    | {"agent": "MutationPolicyEngine", "llm_used": false}
created_at                  | 2026-05-22 07:21:39.05963+00
-[ RECORD 2 ]---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                          | 6ae49894874244e8
trace_id                    | 3c9b8bfa1b034e7a
confidence                  | 0.59999999999999997779553950749686919152736663818359375
advisory                    | Mutation policy balanced â€” continue current exploration strategy.
exploration_vs_exploitation | exploration_dominant
entropy_metric              | 0.9696000000000000174082970261224545538425445556640625
diversification_advisory    | No immediate rebalancing needed.
priority_weights            | {"exit_logic": 0.05, "risk_adjust": 0.1, "combine_with": 0.1, "regime_adapt": 0.1, "parameter_shift": 0.2, "threshold_loosen": 0.15, "indicator_replace": 0.15, "threshold_tighten": 0.15}
leaderboard_snapshot        | [{"total": 60, "failed": 6, "improved": 7, "mutation_type": "repair::threshold_adjustment", "avg_child_score": 40.13, "avg_score_delta": 0.18, "conversion_rate": 53.8, "avg_parent_score": 40.23}, {"total": 43, "failed": 10, "improved": 3, "mutation_type": "simplification::condition_removal", "avg_child_score": 39.28, "avg_score_delta": 0.46, "conversion_rate": 23.1, "... [TRUNCATED]
advisory_only               | t
metadata                    | {"agent": "MutationPolicyEngine", "llm_used": false}
created_at                  | 2026-05-22 07:27:42.118585+00


```

---

## 61. `mutation_policy_state`

- **Row count:** 188
- **Columns (6):**
  - `id (text)`
  - `learned_at (timestamp with time zone)`
  - `mutation_weights (jsonb)`
  - `per_type_success_rates (jsonb)`
  - `n_observations (integer)`
  - `details (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                     | 238cd9a6-e0bc-4001-bcba-eee6d527653f
learned_at             | 2026-05-27 13:02:22.654606+00
mutation_weights       | {"exit_logic": 0.05, "risk_adjust": 0.1, "combine_with": 0.1, "regime_adapt": 0.1, "parameter_shift": 0.2, "threshold_loosen": 0.15, "indicator_replace": 0.15, "threshold_tighten": 0.15, "repair::rsi_threshold_shift": 2.0, "repair::threshold_adjustment": 3.0, "refinement::cooldown_adjustment": 0.5, "refinement::hold_time_adjustment": 0.3, "simplification::condition_removal... [TRUNCATED]
per_type_success_rates | {}
n_observations         | 0
details                | {"note": "default_weights_persisted_no_observations"}
-[ RECORD 2 ]----------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                     | 92a0b2fd-5b43-4e20-883d-4355fd5e01e7
learned_at             | 2026-05-27 13:04:25.950423+00
mutation_weights       | {"exit_logic": 0.05, "risk_adjust": 0.1, "combine_with": 0.1, "regime_adapt": 0.1, "parameter_shift": 0.2, "threshold_loosen": 0.15, "indicator_replace": 0.15, "threshold_tighten": 0.15, "repair::rsi_threshold_shift": 2.0, "repair::threshold_adjustment": 3.0, "refinement::cooldown_adjustment": 0.5, "refinement::hold_time_adjustment": 0.3, "simplification::condition_removal... [TRUNCATED]
per_type_success_rates | {}
n_observations         | 0
details                | {"note": "default_weights_persisted_no_observations"}


```

---

## 62. `mutation_survival_log`

- **Row count:** 0
- **Columns (9):**
  - `id (uuid)`
  - `mutation_type (text)`
  - `target_agent (text)`
  - `total_applications (integer)`
  - `survival_count (integer)`
  - `avg_fitness_contribution (numeric)`
  - `survival_rate (numeric)`
  - `metadata (jsonb)`
  - `updated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 63. `order_flow`

- **Row count:** 941208
- **Columns (6):**
  - `time (timestamp with time zone)`
  - `symbol (text)`
  - `price (numeric)`
  - `size (numeric)`
  - `side (text)`
  - `aggressor (text)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]------------------------------------------------------------------
time      | 2026-05-13 17:35:54.237+00
symbol    | BTCUSDT
price     | 79352
size      | 0.00006999999999999999386775251242198692125384695827960968017578125
side      | sell
aggressor | 6292823239
-[ RECORD 2 ]------------------------------------------------------------------
time      | 2026-05-13 17:35:54.237+00
symbol    | BTCUSDT
price     | 79352
size      | 0.00006999999999999999386775251242198692125384695827960968017578125
side      | sell
aggressor | 6292823240


```

---

## 64. `organism_regime_profile`

- **Row count:** 3770
- **Columns (13):**
  - `id (character varying)`
  - `strategy_id (character varying)`
  - `profiled_at (timestamp with time zone)`
  - `bull_survivability (double precision)`
  - `bear_survivability (double precision)`
  - `ranging_survivability (double precision)`
  - `volatility_tolerance (double precision)`
  - `liquidity_sensitivity (double precision)`
  - `archetype_regime_alignment (double precision)`
  - `primary_affinity (character varying)`
  - `profile_confidence (double precision)`
  - `archetype (character varying)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------------+--------------------------------------------
id                         | ea8e0e09-ae40-4e73-9f50-049c89ed048c
strategy_id                | 9170f273-c7c7-40a9-aa83-da99fb53953e
profiled_at                | 2026-05-26 08:19:38.995435+00
bull_survivability         | 0.2716
bear_survivability         | 0.3597
ranging_survivability      | 0.6055
volatility_tolerance       | 0.25
liquidity_sensitivity      | 1
archetype_regime_alignment | 0.5272
primary_affinity           | ranging
profile_confidence         | 0.15
archetype                  | mean_reversion
metadata                   | {"method": "multi_factor_regime_profiling"}
-[ RECORD 2 ]--------------+--------------------------------------------
id                         | b6016075-befd-4f0a-bd94-e40f0ece27e9
strategy_id                | d55518d2-b91d-4dc2-afbb-fd06938e8c75
profiled_at                | 2026-05-26 08:19:38.995435+00
bull_survivability         | 0.2715
bear_survivability         | 0.3593
ranging_survivability      | 0.6048
volatility_tolerance       | 0.25
liquidity_sensitivity      | 1
archetype_regime_alignment | 0.5271
primary_affinity           | ranging
profile_confidence         | 0.15
archetype                  | mean_reversion
metadata                   | {"method": "multi_factor_regime_profiling"}


```

---

## 65. `overfitting_analysis`

- **Row count:** 0
- **Columns (8):**
  - `id (uuid)`
  - `strategy_id (uuid)`
  - `overfit_probability (numeric)`
  - `robustness_score (numeric)`
  - `parameter_stability_score (numeric)`
  - `shuffle_test_p_value (numeric)`
  - `noise_degradation_pct (numeric)`
  - `analyzed_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 66. `paper_trades`

- **Row count:** 0
- **Columns (11):**
  - `time (timestamp with time zone)`
  - `strategy_id (uuid)`
  - `symbol (text)`
  - `side (text)`
  - `quantity (numeric)`
  - `price (numeric)`
  - `fill_price (numeric)`
  - `status (text)`
  - `pnl (numeric)`
  - `id (uuid)`
  - `qty (numeric)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 67. `pattern_memory`

- **Row count:** 6433
- **Columns (19):**
  - `id (uuid)`
  - `pattern_type (text)`
  - `archetype (text)`
  - `feature_family (ARRAY)`
  - `asset_class (text)`
  - `timeframe (text)`
  - `regime (text)`
  - `composite_score_avg (numeric)`
  - `short_window_score_avg (numeric)`
  - `sharpe_avg (numeric)`
  - `win_rate_avg (numeric)`
  - `total_trades_avg (numeric)`
  - `cost_burden_avg (numeric)`
  - `sample_size (integer)`
  - `confidence_score (numeric)`
  - `recommendation (text)`
  - `motif_details (jsonb)`
  - `detected_at (timestamp with time zone)`
  - `updated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------+-----------------------------------------------------------------------------------------------------------------------------------------------------
id                     | 10912bdf-a12e-4b1b-a776-056069f9e5a1
pattern_type           | winning_motif
archetype              | mean_reversion
feature_family         | {rsi}
asset_class            | equity
timeframe              | mixed
regime                 |
composite_score_avg    | 40.7999999999999971578290569595992565155029296875
short_window_score_avg | 40.7999999999999971578290569595992565155029296875
sharpe_avg             | 0
win_rate_avg           | 0.5340000000000000301980662698042578995227813720703125
total_trades_avg       | 7
cost_burden_avg        | 0.003000000000000000062450045135165055398829281330108642578125
sample_size            | 1
confidence_score       | 0.1000000000000000055511151231257827021181583404541015625
recommendation         | Prioritize this archetype for ideation focus
motif_details          | {"members": ["control_rsi14_mean_reversion_equity"], "is_cost_trap": false, "total_members": 1, "avg_gross_edge": -0.0017}
detected_at            | 2026-05-17 08:23:56.051735+00
updated_at             | 2026-05-17 08:23:56.051735+00
-[ RECORD 2 ]----------+-----------------------------------------------------------------------------------------------------------------------------------------------------
id                     | 19c98cf4-e93e-4a9e-a9da-54f0701c5b48
pattern_type           | ecosystem_summary
archetype              | all
feature_family         | {}
asset_class            | all
timeframe              | all
regime                 |
composite_score_avg    | 40.7999999999999971578290569595992565155029296875
short_window_score_avg | 0
sharpe_avg             | 0
win_rate_avg           | 0
total_trades_avg       | 0
cost_burden_avg        | 0
sample_size            | 1
confidence_score       | 1
recommendation         | Pattern analysis summary
motif_details          | {"cost_traps": 0, "losing_motifs": 0, "winning_motifs": 1, "total_backtested": 1, "losing_archetypes": [], "winning_archetypes": ["mean_reversion"]}
detected_at            | 2026-05-17 08:23:56.051735+00
updated_at             | 2026-05-17 08:23:56.051735+00


```

---

## 68. `performance_metrics`

- **Row count:** 0
- **Columns (4):**
  - `time (timestamp with time zone)`
  - `strategy_id (uuid)`
  - `metric_name (text)`
  - `value (numeric)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 69. `phase29_runtime_metrics`

- **Row count:** 35
- **Columns (4):**
  - `id (uuid)`
  - `captured_at (timestamp with time zone)`
  - `interval_seconds (integer)`
  - `metrics (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id               | 4c052102-4633-4f88-a3cc-d0749fc578b5
captured_at      | 2026-05-24 16:42:05.730935+00
interval_seconds | 300
metrics          | {"active_count": 0, "retired_count": 0, "elapsed_seconds": 304.4, "trades_executed": 0, "validated_count": 0, "async_task_count": 43, "replay_violations": 0, "pending_code_count": 0, "attribution_records": 15, "mutation_candidates": 0, "strategies_generated": 15, "pending_backtest_count": 0, "portfolio_participants": 50, "replay_integrity_score": 100.0, "scout_trust_divergence":... [TRUNCATED]
-[ RECORD 2 ]----+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id               | 1d8604f1-9281-4b55-9bd7-f6b82097237c
captured_at      | 2026-05-24 16:47:07.265002+00
interval_seconds | 300
metrics          | {"active_count": 0, "retired_count": 0, "elapsed_seconds": 606.0, "trades_executed": 0, "validated_count": 0, "async_task_count": 43, "replay_violations": 0, "pending_code_count": 0, "attribution_records": 4, "mutation_candidates": 0, "strategies_generated": 4, "pending_backtest_count": 0, "portfolio_participants": 50, "replay_integrity_score": 100.0, "scout_trust_divergence": 0... [TRUNCATED]


```

---

## 70. `phase30_runtime_metrics`

- **Row count:** 76
- **Columns (36):**
  - `id (integer)`
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (integer)`
  - `strategies_generated (integer)`
  - `validated_organisms (integer)`
  - `active_organisms (integer)`
  - `pending_backtest (integer)`
  - `pending_validation (integer)`
  - `pending_code (integer)`
  - `trades_executed (integer)`
  - `trade_throughput_24h (integer)`
  - `avg_trades_per_strategy (double precision)`
  - `mutation_candidates (integer)`
  - `mutation_family_count (integer)`
  - `mutation_accept_rate (double precision)`
  - `scout_trust_divergence (double precision)`
  - `scout_agreement_score (double precision)`
  - `scout_entropy (double precision)`
  - `regime_diversity_count (integer)`
  - `active_perturbations (integer)`
  - *... and 16 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------+--------------------------------------------------------------------------
id                        | 1
recorded_at               | 2026-05-25 07:47:25.813547+00
runtime_minutes           | 0
strategies_generated      | 10
validated_organisms       | 6
active_organisms          | 6
pending_backtest          | 0
pending_validation        | 0
pending_code              | 0
trades_executed           | 48
trade_throughput_24h      | 0
avg_trades_per_strategy   | 8
mutation_candidates       | 0
mutation_family_count     | 0
mutation_accept_rate      |
scout_trust_divergence    | 0.6
scout_agreement_score     | 0.75
scout_entropy             | 0.5
regime_diversity_count    | 0
active_perturbations      | 0
regime_stress_level       | 0
portfolio_diversification | 0.4986
concentration_risk        | 0.0001
capital_allocation_count  |
retirement_count          | 4
dominant_organisms        | 0
execution_degradation     | 0
avg_slippage_bps          | 0
avg_fill_probability      | 0
replay_integrity          |
lifecycle_events          |
error_count               |
economic_density_score    | 21.9
selection_pressure        | 44.5
regime_adaptation_score   | 54
metadata                  | {"recorded_at": "2026-05-25T07:47:25.813547+00:00", "runtime_minutes": 0}
-[ RECORD 2 ]-------------+--------------------------------------------------------------------------
id                        | 2
recorded_at               | 2026-05-25 07:47:55.852983+00
runtime_minutes           | 0
strategies_generated      | 10
validated_organisms       | 6
active_organisms          | 6
pending_backtest          | 0
pending_validation        | 0
pending_code              | 0
trades_executed           | 48
trade_throughput_24h      | 0
avg_trades_per_strategy   | 8
mutation_candidates       | 0
mutation_family_count     | 0
mutation_accept_rate      |
scout_trust_divergence    | 0.6
scout_agreement_score     | 0.75
scout_entropy             | 0.5
regime_diversity_count    | 0
active_perturbations      | 0
regime_stress_level       | 0
portfolio_diversification | 0.4986
concentration_risk        | 0.0001
capital_allocation_count  |
retirement_count          | 4
dominant_organisms        | 0
execution_degradation     | 0
avg_slippage_bps          | 0
avg_fill_probability      | 0
replay_integrity          |
lifecycle_events          |
error_count               |
economic_density_score    | 21.9
selection_pressure        | 44.5
regime_adaptation_score   | 54
metadata                  | {"recorded_at": "2026-05-25T07:47:55.852983+00:00", "runtime_minutes": 0}


```

---

## 71. `phase31_specialization_metrics`

- **Row count:** 143
- **Columns (49):**
  - `id (integer)`
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (integer)`
  - `strategies_generated (integer)`
  - `validated_organisms (integer)`
  - `active_organisms (integer)`
  - `pending_backtest (integer)`
  - `pending_validation (integer)`
  - `pending_code (integer)`
  - `trades_executed (integer)`
  - `trade_throughput_24h (integer)`
  - `avg_trades_per_strategy (double precision)`
  - `n_dominant_identified (integer)`
  - `n_dominant_lineages (integer)`
  - `dominant_concentration (double precision)`
  - `mutation_candidates (integer)`
  - `mutation_family_count (integer)`
  - `mutation_accept_rate (double precision)`
  - `lineages_identified (integer)`
  - `lineage_depth_avg (double precision)`
  - *... and 29 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------------+---------------------------------------------------------------------------
id                              | 1
recorded_at                     | 2026-05-25 08:24:31.740326+00
runtime_minutes                 | 0
strategies_generated            | 10
validated_organisms             | 9
active_organisms                | 9
pending_backtest                | 0
pending_validation              | 0
pending_code                    | 0
trades_executed                 | 19
trade_throughput_24h            | 0
avg_trades_per_strategy         | 2.11
n_dominant_identified           | 0
n_dominant_lineages             | 0
dominant_concentration          | 0
mutation_candidates             | 0
mutation_family_count           | 0
mutation_accept_rate            | 0
lineages_identified             | 0
lineage_depth_avg               | 0
regime_specialization_count     | 0
regime_specialization_diversity | 0
regime_affinity_bull            | 0
regime_affinity_bear            | 0
regime_affinity_ranging         | 0
portfolio_diversification       | 0.4986
concentration_risk              | 0.0001
capital_migrated_pct            | 0
n_weak_penalized                | 0
n_dominant_boosted              | 0
retirement_count                | 0
scout_divergence_count          | 0
scout_trust_divergence          | 0
n_high_value_scouts             | 0
n_contradictory_scouts          | 0
active_perturbations            | 0
stress_level                    | 0
n_survivors                     | 9
n_collapsed                     | 0
execution_degradation           | 0
avg_slippage_bps                | 0
avg_fill_probability            | 0
dominant_emergence_score        | 15
lineage_evolution_score         | 0
regime_adaptation_score         | 13.5
scout_predictive_divergence     | 20
portfolio_evolution_pressure    | 10
stress_survival_score           | 92
metadata                        | {"collected_at": "2026-05-25T08:24:31.858268+00:00", "runtime_minutes": 0}
-[ RECORD 2 ]-------------------+---------------------------------------------------------------------------
id                              | 2
recorded_at                     | 2026-05-25 08:25:01.884462+00
runtime_minutes                 | 0
strategies_generated            | 10
validated_organisms             | 9
active_organisms                | 9
pending_backtest                | 0
pending_validation              | 0
pending_code                    | 0
trades_executed                 | 19
trade_throughput_24h            | 0
avg_trades_per_strategy         | 2.11
n_dominant_identified           | 0
n_dominant_lineages             | 0
dominant_concentration          | 0
mutation_candidates             | 0
mutation_family_count           | 0
mutation_accept_rate            | 0
lineages_identified             | 0
lineage_depth_avg               | 0
regime_specialization_count     | 0
regime_specialization_diversity | 0
regime_affinity_bull            | 0
regime_affinity_bear            | 0
regime_affinity_ranging         | 0
portfolio_diversification       | 0.4986
concentration_risk              | 0.0001
capital_migrated_pct            | 0
n_weak_penalized                | 0
n_dominant_boosted              | 0
retirement_count                | 0
scout_divergence_count          | 0
scout_trust_divergence          | 0
n_high_value_scouts             | 0
n_contradictory_scouts          | 0
active_perturbations            | 0
stress_level                    | 0
n_survivors                     | 9
n_collapsed                     | 0
execution_degradation           | 0
avg_slippage_bps                | 0
avg_fill_probability            | 0
dominant_emergence_score        | 15
lineage_evolution_score         | 0
regime_adaptation_score         | 13.5
scout_predictive_divergence     | 20
portfolio_evolution_pressure    | 10
stress_survival_score           | 92
metadata                        | {"collected_at": "2026-05-25T08:25:01.995688+00:00", "runtime_minutes": 0}


```

---

## 72. `phase32_intelligence_metrics`

- **Row count:** 49
- **Columns (20):**
  - `id (integer)`
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (integer)`
  - `dominant_organisms (integer)`
  - `mutation_family_performance (jsonb)`
  - `regime_affinity_rankings (jsonb)`
  - `scout_predictive_rankings (jsonb)`
  - `capital_allocation_evolution (jsonb)`
  - `recovery_quality (double precision)`
  - `drawdown_resilience (double precision)`
  - `diversification_quality (double precision)`
  - `expectancy_distribution (jsonb)`
  - `execution_degradation_metrics (jsonb)`
  - `replay_integrity (double precision)`
  - `adaptive_quality_score (double precision)`
  - `specialization_quality_score (double precision)`
  - `allocation_quality_score (double precision)`
  - `evolutionary_selection_score (double precision)`
  - `long_horizon_survivability_score (double precision)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                               | 1
recorded_at                      | 2026-05-26 05:49:32.595032+00
runtime_minutes                  | 0
dominant_organisms               | 0
mutation_family_performance      | [{"n_obs": 124, "family": "simplification::condition_removal", "avg_score_delta": 0.46153846153846156, "avg_sharpe_delta": 0.0}, {"n_obs": 162, "family": "repair::threshold_adjustment", "avg_score_delta": 0.18461538461538549, "avg_sharpe_delta": 0.0}, {"n_obs": 142, "family": "repair::regime_filter_adjustment", "avg_score_delta": 0.0, "avg_sharpe_delta": 0.0}, {"... [TRUNCATED]
regime_affinity_rankings         | []
scout_predictive_rankings        | []
capital_allocation_evolution     | {"weak_penalized": 0, "capital_migrated": 0.0, "dominant_boosted": 0}
recovery_quality                 | 0
drawdown_resilience              | 1
diversification_quality          | 0.5
expectancy_distribution          | {"p90": 0.0, "mean": 0.0, "median": 0.0}
execution_degradation_metrics    | {"degradation": 0.0, "slippage_bps": 0.0, "fill_probability": 0.0}
replay_integrity                 | 1
adaptive_quality_score           | 0.75
specialization_quality_score     | 0
allocation_quality_score         | 0.725
evolutionary_selection_score     | 0.5
long_horizon_survivability_score | 0.5825
metadata                         | {"collected_at": "2026-05-26T05:49:32.695673+00:00"}
-[ RECORD 2 ]--------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                               | 2
recorded_at                      | 2026-05-26 05:49:40.705816+00
runtime_minutes                  | 0
dominant_organisms               | 0
mutation_family_performance      | [{"n_obs": 124, "family": "simplification::condition_removal", "avg_score_delta": 0.46153846153846156, "avg_sharpe_delta": 0.0}, {"n_obs": 162, "family": "repair::threshold_adjustment", "avg_score_delta": 0.18461538461538549, "avg_sharpe_delta": 0.0}, {"n_obs": 142, "family": "repair::regime_filter_adjustment", "avg_score_delta": 0.0, "avg_sharpe_delta": 0.0}, {"... [TRUNCATED]
regime_affinity_rankings         | []
scout_predictive_rankings        | []
capital_allocation_evolution     | {"weak_penalized": 0, "capital_migrated": 0.0, "dominant_boosted": 0}
recovery_quality                 | 0
drawdown_resilience              | 1
diversification_quality          | 0.5
expectancy_distribution          | {"p90": 0.0, "mean": 0.0, "median": 0.0}
execution_degradation_metrics    | {"degradation": 0.0, "slippage_bps": 0.0, "fill_probability": 0.0}
replay_integrity                 | 1
adaptive_quality_score           | 0.75
specialization_quality_score     | 0
allocation_quality_score         | 0.725
evolutionary_selection_score     | 0.5
long_horizon_survivability_score | 0.5825
metadata                         | {"collected_at": "2026-05-26T05:49:40.785264+00:00"}


```

---

## 73. `phase32_mutation_weights`

- **Row count:** 49
- **Columns (5):**
  - `id (integer)`
  - `learned_at (timestamp with time zone)`
  - `family_weights (jsonb)`
  - `exploration_fraction (double precision)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                   | 1
learned_at           | 2026-05-26 05:49:32.714676+00
family_weights       | {"aggression::exit_refinement": 0.02857142857142857, "repair::rsi_threshold_shift": 0.02857142857142857, "repair::threshold_adjustment": 0.2571428571428579, "refinement::cooldown_adjustment": 0.02857142857142857, "refinement::hold_time_adjustment": 0.02857142857142857, "repair::regime_filter_adjustment": 0.02857142857142857, "simplification::condition_removal": 0.59999999999... [TRUNCATED]
exploration_fraction | 0.2
metadata             | {"source": "phase32_adaptive_intelligence_soak"}
-[ RECORD 2 ]--------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                   | 2
learned_at           | 2026-05-26 05:49:40.800667+00
family_weights       | {"aggression::exit_refinement": 0.02857142857142857, "repair::rsi_threshold_shift": 0.02857142857142857, "repair::threshold_adjustment": 0.2571428571428579, "refinement::cooldown_adjustment": 0.02857142857142857, "refinement::hold_time_adjustment": 0.02857142857142857, "repair::regime_filter_adjustment": 0.02857142857142857, "simplification::condition_removal": 0.59999999999... [TRUNCATED]
exploration_fraction | 0.2
metadata             | {"source": "phase32_adaptive_intelligence_soak"}


```

---

## 74. `phase33_performance_metrics`

- **Row count:** 45
- **Columns (69):**
  - `id (integer)`
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (integer)`
  - `expectancy_mean (double precision)`
  - `expectancy_median (double precision)`
  - `expectancy_p90 (double precision)`
  - `avg_sharpe (double precision)`
  - `avg_sortino (double precision)`
  - `avg_calmar (double precision)`
  - `avg_composite_fitness (double precision)`
  - `median_composite_fitness (double precision)`
  - `top_decile_fitness (double precision)`
  - `bottom_decile_fitness (double precision)`
  - `recovery_quality (double precision)`
  - `drawdown_resilience (double precision)`
  - `capital_efficiency (double precision)`
  - `survival_quality (double precision)`
  - `ram_mb (double precision)`
  - `cpu_percent (double precision)`
  - `event_loop_lag_ms (double precision)`
  - *... and 49 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                               | 1
recorded_at                      | 2026-05-26 17:17:57.427646+00
runtime_minutes                  | 0
expectancy_mean                  | -5.099492078654592
expectancy_median                | -0.33161663854524803
expectancy_p90                   | 0
avg_sharpe                       | 0
avg_sortino                      | 0
avg_calmar                       | 0
avg_composite_fitness            | 28.56205517792883
median_composite_fitness         | 29.9
top_decile_fitness               | 35
bottom_decile_fitness            | 21.8
recovery_quality                 | 1
drawdown_resilience              | 0.94890352729907
capital_efficiency               | 71.82714750396913
survival_quality                 | 0.026455026455026457
ram_mb                           | 136.2
cpu_percent                      | 0
event_loop_lag_ms                | 14
db_pool_size                     | 0
db_checked_out                   | 0
db_overflow                      | 0
dead_letter_count                | 0
failed_insert_count              | 331
task_count                       | 1
thread_count                     | 30
restart_count                    | 0
dominant_organisms               | 0
active_organisms                 | 151
mutation_family_count            | 7
top_mutation_family              | refinement::hold_time_adjustment
regime_specialist_count          | 1
cross_regime_survivors           | 0
scout_divergence                 | 0
capital_migrated                 | 0.3825
diversification_score            | 0.4638
concentration_risk               | 0.0015
organism_lifespan_avg            | 2256.916996047431
retirement_rate                  | 0
active_perturbations             | 0
stress_level                     | 0
avg_resilience                   | 0.3788
n_resilient                      | 0
n_fragile                        | 0
collapse_rate                    | 0
generation_comparison_score      | 0
adaptive_trend                   | -0.0592
adaptive_quality_score           | 0.9847
specialization_quality_score     | 0.2473
allocation_quality_score         | 0.6817
evolutionary_selection_score     | 0
long_horizon_survivability_score | 0.5709
infrastructure_stability_score   | 0.972
stress_resilience_score          | 0.4441
mutation_family_performance      | [{"n_obs": 284, "family": "refinement::hold_time_adjustment", "avg_score_delta": 0.0, "avg_sharpe_delta": 0.0}, {"n_obs": 162, "family": "repair::threshold_adjustment", "avg_score_delta": 0.18461538461538549, "avg_sharpe_delta": 0.0}, {"n_obs": 142, "family": "refinement::cooldown_adjustment", "avg_score_delta": 0.0, "avg_sharpe_delta": 0.0}, {"n_obs": 142, "fami... [TRUNCATED]
regime_affinity_rankings         | [{"n_obs": 250, "regime": "ranging", "survivability": 0.41211639999999944}]
scout_predictive_rankings        | [{"n_obs": 2903, "scout": "ideator_archetype_momentum", "alignment": 0.0, "avg_net_pnl": 0.0}, {"n_obs": 36, "scout": "regime_scout", "alignment": 0.0, "avg_net_pnl": 0.0}, {"n_obs": 197, "scout": "ideator_archetype_mean_reversion", "alignment": 0.0, "avg_net_pnl": 0.0}]
capital_allocation_evolution     | {"weak_penalized": 0, "capital_migrated": 0.3825, "dominant_boosted": 0}
expectancy_distribution          | {"p90": 0.0, "mean": -5.099492078654592, "median": -0.33161663854524803}
execution_degradation_metrics    | {}
replay_integrity                 | 1
error_count                      | 0
trades_per_hour                  | 0
execution_degradation            | 0
organism_survival_curves         | []
stress_state                     | {"stress_level": 0.0, "perturbation_types": [], "active_perturbations": 0}
infrastructure_snapshot          | {"ram_mb": 136.2, "task_count": 1, "cpu_percent": 0.0, "thread_count": 30, "event_loop_lag_ms": 14.0}
metadata                         | {"phase": "33", "sub_phases": ["33A", "33B", "33C", "33D", "33E"], "collected_at": "2026-05-26T17:17:57.427646+00:00"}
-[ RECORD 2 ]--------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                               | 2
recorded_at                      | 2026-05-26 17:22:58.883652+00
runtime_minutes                  | 5
expectancy_mean                  | -5.099492078654592
expectancy_median                | -0.33161663854524803
expectancy_p90                   | 0
avg_sharpe                       | 0
avg_sortino                      | 0
avg_calmar                       | 0
avg_composite_fitness            | 28.56205517792883
median_composite_fitness         | 29.9
top_decile_fitness               | 35
bottom_decile_fitness            | 21.8
recovery_quality                 | 1
drawdown_resilience              | 0.94890352729907
capital_efficiency               | 71.82714750396913
survival_quality                 | 0.026455026455026457
ram_mb                           | 138.2
cpu_percent                      | 0
event_loop_lag_ms                | 15
db_pool_size                     | 0
db_checked_out                   | 0
db_overflow                      | 0
dead_letter_count                | 0
failed_insert_count              | 331
task_count                       | 1
thread_count                     | 28
restart_count                    | 0
dominant_organisms               | 0
active_organisms                 | 151
mutation_family_count            | 7
top_mutation_family              | refinement::hold_time_adjustment
regime_specialist_count          | 1
cross_regime_survivors           | 0
scout_divergence                 | 0
capital_migrated                 | 0.3825
diversification_score            | 0.4638
concentration_risk               | 0.0015
organism_lifespan_avg            | 2296.4426877470355
retirement_rate                  | 0
active_perturbations             | 0
stress_level                     | 0
avg_resilience                   | 0.3788
n_resilient                      | 0
n_fragile                        | 0
collapse_rate                    | 0
generation_comparison_score      | 0
adaptive_trend                   | -0.0592
adaptive_quality_score           | 0.9847
specialization_quality_score     | 0.2473
allocation_quality_score         | 0.6817
evolutionary_selection_score     | 0
long_horizon_survivability_score | 0.5706
infrastructure_stability_score   | 0.97
stress_resilience_score          | 0.4441
mutation_family_performance      | [{"n_obs": 284, "family": "refinement::hold_time_adjustment", "avg_score_delta": 0.0, "avg_sharpe_delta": 0.0}, {"n_obs": 162, "family": "repair::threshold_adjustment", "avg_score_delta": 0.18461538461538549, "avg_sharpe_delta": 0.0}, {"n_obs": 142, "family": "refinement::cooldown_adjustment", "avg_score_delta": 0.0, "avg_sharpe_delta": 0.0}, {"n_obs": 142, "fami... [TRUNCATED]
regime_affinity_rankings         | [{"n_obs": 258, "regime": "ranging", "survivability": 0.41212635658914665}]
scout_predictive_rankings        | [{"n_obs": 2903, "scout": "ideator_archetype_momentum", "alignment": 0.0, "avg_net_pnl": 0.0}, {"n_obs": 36, "scout": "regime_scout", "alignment": 0.0, "avg_net_pnl": 0.0}, {"n_obs": 197, "scout": "ideator_archetype_mean_reversion", "alignment": 0.0, "avg_net_pnl": 0.0}]
capital_allocation_evolution     | {"weak_penalized": 0, "capital_migrated": 0.3825, "dominant_boosted": 0}
expectancy_distribution          | {"p90": 0.0, "mean": -5.099492078654592, "median": -0.33161663854524803}
execution_degradation_metrics    | {}
replay_integrity                 | 1
error_count                      | 0
trades_per_hour                  | 0
execution_degradation            | 0
organism_survival_curves         | []
stress_state                     | {"stress_level": 0.0, "perturbation_types": [], "active_perturbations": 0}
infrastructure_snapshot          | {"ram_mb": 138.2, "task_count": 1, "cpu_percent": 0.0, "thread_count": 28, "event_loop_lag_ms": 15.0}
metadata                         | {"phase": "33", "sub_phases": ["33A", "33B", "33C", "33D", "33E"], "collected_at": "2026-05-26T17:22:58.883652+00:00"}


```

---

## 75. `phase33_perturbation_events`

- **Row count:** 10
- **Columns (7):**
  - `id (integer)`
  - `perturbation_type (text)`
  - `severity (double precision)`
  - `started_at (timestamp with time zone)`
  - `expired_at (timestamp with time zone)`
  - `status (text)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----+------------------------------------------------------------------------------------------------------------------------------------------------------
id                | 1
perturbation_type | spread_widening
severity          | 10.42
started_at        | 2026-05-26 18:14:02.30368+00
expired_at        |
status            | active
metadata          | {"category": "execution", "target_symbol": "AAPL", "duration_minutes": 23, "affected_channels": ["execution_gateway", "cost_modeling"]}
-[ RECORD 2 ]-----+------------------------------------------------------------------------------------------------------------------------------------------------------
id                | 2
perturbation_type | liquidity_drought
severity          | 6.16
started_at        | 2026-05-26 18:14:02.316383+00
expired_at        |
status            | active
metadata          | {"category": "liquidity", "target_symbol": "QQQ", "duration_minutes": 81, "affected_channels": ["execution", "slippage_modeling", "position_sizing"]}


```

---

## 76. `phase34_coverage_metrics`

- **Row count:** 6
- **Columns (26):**
  - `id (integer)`
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (integer)`
  - `l1_ingestion (boolean)`
  - `l2_strategy_generation (boolean)`
  - `l3_backtesting (boolean)`
  - `l4_risk_capital (boolean)`
  - `l5_execution (boolean)`
  - `l6_governance (boolean)`
  - `l7_meta_evolution (boolean)`
  - `total_strategies (integer)`
  - `total_backtests (integer)`
  - `total_executions (integer)`
  - `total_event_store (integer)`
  - `total_audit_entries (integer)`
  - `total_scout_signals (integer)`
  - `total_mutations (integer)`
  - `total_paper_trades (integer)`
  - `total_portfolio_runs (integer)`
  - `total_patterns (integer)`
  - *... and 6 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                     | 1
recorded_at            | 2026-05-26 18:22:11.714583+00
runtime_minutes        | 0
l1_ingestion           | t
l2_strategy_generation | t
l3_backtesting         | t
l4_risk_capital        | t
l5_execution           | f
l6_governance          | t
l7_meta_evolution      | f
total_strategies       | 2503
total_backtests        | 2501
total_executions       | 98
total_event_store      | 4457
total_audit_entries    | 5301
total_scout_signals    | 0
total_mutations        | 981
total_paper_trades     | 0
total_portfolio_runs   | 24
total_patterns         | 6433
replay_integrity_score | 100
active_layers          | 7
total_layers           | 7
coverage_pct           | 100
end_to_end_flow        | t
metadata               | {"phase": "34", "coverage": {"L5_execution": {"active": true, "status": "[OK]", "paper_trades": 0, "copy_executions": 7, "dead_letter_entries": 16, "execution_log_entries": 98, "execution_realism_simulations": 0}, "system_health": {"health_checks": 309, "agent_registry_entries": 0}, "L4_risk_and_capital": {"active": true, "status": "[OK]", "stress_tests": 0, "capital_alloc... [TRUNCATED]
-[ RECORD 2 ]----------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                     | 2
recorded_at            | 2026-05-26 18:27:12.028969+00
runtime_minutes        | 5
l1_ingestion           | t
l2_strategy_generation | t
l3_backtesting         | t
l4_risk_capital        | t
l5_execution           | f
l6_governance          | t
l7_meta_evolution      | f
total_strategies       | 2503
total_backtests        | 2501
total_executions       | 98
total_event_store      | 4457
total_audit_entries    | 5301
total_scout_signals    | 0
total_mutations        | 981
total_paper_trades     | 0
total_portfolio_runs   | 24
total_patterns         | 6433
replay_integrity_score | 100
active_layers          | 7
total_layers           | 7
coverage_pct           | 100
end_to_end_flow        | t
metadata               | {"phase": "34", "coverage": {"L5_execution": {"active": true, "status": "[OK]", "paper_trades": 0, "copy_executions": 7, "dead_letter_entries": 16, "execution_log_entries": 98, "execution_realism_simulations": 0}, "system_health": {"health_checks": 309, "agent_registry_entries": 0}, "L4_risk_and_capital": {"active": true, "status": "[OK]", "stress_tests": 0, "capital_alloc... [TRUNCATED]


```

---

## 77. `phase35_activation_metrics`

- **Row count:** 12
- **Columns (41):**
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (double precision)`
  - `n_paper_trades (integer)`
  - `n_recent_trades (integer)`
  - `n_active_strategies (integer)`
  - `n_symbols_traded (integer)`
  - `n_fills (integer)`
  - `total_pnl (double precision)`
  - `win_rate (double precision)`
  - `n_realism_events (integer)`
  - `avg_slippage_bps (double precision)`
  - `avg_latency_ms (double precision)`
  - `avg_fill_probability (double precision)`
  - `execution_degradation (double precision)`
  - `n_execution_log (integer)`
  - `n_copy_executions (integer)`
  - `n_capital_allocations (integer)`
  - `n_portfolio_intelligence (integer)`
  - `n_portfolio_evolution (integer)`
  - `n_capital_migrations (integer)`
  - *... and 21 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------+---------------------------------------
recorded_at               | 2026-05-27 06:42:26.293172+00
runtime_minutes           | 5
n_paper_trades            | 0
n_recent_trades           | 0
n_active_strategies       | 0
n_symbols_traded          | 0
n_fills                   | 0
total_pnl                 | 0
win_rate                  | 0
n_realism_events          | 0
avg_slippage_bps          | 0
avg_latency_ms            | 0
avg_fill_probability      | 0
execution_degradation     | 0
n_execution_log           | 98
n_copy_executions         | 7
n_capital_allocations     | 31
n_portfolio_intelligence  | 24
n_portfolio_evolution     | 112
n_capital_migrations      | 0
n_retired_organisms       | 78
total_exposure            | 1.0012
diversification_score     | 0.4638
n_scout_signals           | 0
n_recent_scout_signals    | 0
n_economic_attributions   | 3136
n_hypotheses              | 0
n_active_hypotheses       | 0
n_scout_divergence        | 83
n_scout_influence         | 8703
replay_integrity          | 1
n_dead_letters            | 16
n_unresolved_dead_letters | 16
n_failed_inserts          | 331
n_event_store_events      | 4457
n_audit_entries           | 5301
n_total_strategies        | 2503
ram_mb                    | 122.9
cpu_pct                   | 0
all_layers_active         | f
metadata                  | {"cycle": 1, "source": "phase35_soak"}
-[ RECORD 2 ]-------------+---------------------------------------
recorded_at               | 2026-05-27 06:47:26.510965+00
runtime_minutes           | 10
n_paper_trades            | 0
n_recent_trades           | 0
n_active_strategies       | 0
n_symbols_traded          | 0
n_fills                   | 0
total_pnl                 | 0
win_rate                  | 0
n_realism_events          | 0
avg_slippage_bps          | 0
avg_latency_ms            | 0
avg_fill_probability      | 0
execution_degradation     | 0
n_execution_log           | 98
n_copy_executions         | 7
n_capital_allocations     | 31
n_portfolio_intelligence  | 24
n_portfolio_evolution     | 112
n_capital_migrations      | 0
n_retired_organisms       | 78
total_exposure            | 1.0012
diversification_score     | 0.4638
n_scout_signals           | 0
n_recent_scout_signals    | 0
n_economic_attributions   | 3136
n_hypotheses              | 0
n_active_hypotheses       | 0
n_scout_divergence        | 83
n_scout_influence         | 8703
replay_integrity          | 1
n_dead_letters            | 16
n_unresolved_dead_letters | 16
n_failed_inserts          | 331
n_event_store_events      | 4457
n_audit_entries           | 5301
n_total_strategies        | 2503
ram_mb                    | 123.2
cpu_pct                   | 14.2
all_layers_active         | f
metadata                  | {"cycle": 2, "source": "phase35_soak"}


```

---

## 78. `phase36_activation_weights`

- **Row count:** 178
- **Columns (4):**
  - `id (integer)`
  - `learned_at (timestamp with time zone)`
  - `domain_weights (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id             | 1
learned_at     | 2026-05-27 06:59:50.562784+00
domain_weights | {"scout": 0.06382576354524538, "realism": 0.31518895577898953, "execution": 0.1738897469032685, "validation": 0.11822737731269896, "circulation": 0.1418350301005453, "observability": 0.15129069877391496, "specialization": 0.03574242758533741}
metadata       | {"source": "phase36_full_ecosystem_activation"}
-[ RECORD 2 ]--+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id             | 2
learned_at     | 2026-05-27 06:59:58.152773+00
domain_weights | {"scout": 0.06382576354524538, "realism": 0.31518895577898953, "execution": 0.1738897469032685, "validation": 0.11822737731269896, "circulation": 0.1418350301005453, "observability": 0.15129069877391496, "specialization": 0.03574242758533741}
metadata       | {"source": "phase36_full_ecosystem_activation"}


```

---

## 79. `phase36_full_ecosystem_metrics`

- **Row count:** 178
- **Columns (21):**
  - `id (integer)`
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (integer)`
  - `execution_activation_score (double precision)`
  - `execution_realism_score (double precision)`
  - `scout_ecosystem_score (double precision)`
  - `advanced_validation_score (double precision)`
  - `specialization_score (double precision)`
  - `observability_score (double precision)`
  - `economic_circulation_score (double precision)`
  - `full_activation_score (double precision)`
  - `dominant_organisms (integer)`
  - `specialization_rankings (jsonb)`
  - `scout_rankings (jsonb)`
  - `copy_quality_rankings (jsonb)`
  - `validation_snapshot (jsonb)`
  - `observability_snapshot (jsonb)`
  - `economic_circulation_snapshot (jsonb)`
  - `drift_snapshot (jsonb)`
  - `retirement_snapshot (jsonb)`
  - *... and 1 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                            | 1
recorded_at                   | 2026-05-27 06:59:50.435215+00
runtime_minutes               | 0
execution_activation_score    | 0.5517
execution_realism_score       | 1
scout_ecosystem_score         | 0.2025
advanced_validation_score     | 0.3751
specialization_score          | 0.1134
observability_score           | 0.48
economic_circulation_score    | 0.45
full_activation_score         | 0.5541
dominant_organisms            | 0
specialization_rankings       | [{"n_obs": 610, "regime": "ranging", "survivability": 0.4123059016393452, "profile_confidence": 0.24623475409835918}]
scout_rankings                | [{"n_obs": 2903, "scout": "ideator_archetype_momentum", "n_survived": 0, "avg_pnl_contribution": 0.0, "avg_attribution_weight": 0.266667, "avg_sharpe_contribution": 0.0, "avg_drawdown_contribution": 0.0, "avg_win_rate_contribution": 0.0}, {"n_obs": 36, "scout": "regime_scout", "n_survived": 0, "avg_pnl_contribution": 0.0, "avg_attribution_weight": 0.5, "avg_sharpe_c... [TRUNCATED]
copy_quality_rankings         | [{"n_obs": 1, "leader_id": "87bf6ffa-d639-4403-9c6b-fa24235c05b5", "follower_id": "7416c767-c7e7-401b-90c7-e4e5b242b3ca", "replay_integrity": 0.98, "sync_quality_score": 1.0, "follower_survivability": 0.9}, {"n_obs": 1, "leader_id": "069cb59a-11de-476c-b802-c55f08964997", "follower_id": "855249b2-6376-4d5c-886e-ad349ab72337", "replay_integrity": 0.98, "sync_quality_... [TRUNCATED]
validation_snapshot           | {"avg_sharpe": 0.0, "avg_trades": 74.63814474210317, "n_backtests": 2501, "avg_win_rate": 0.12568079641502108, "avg_composite_fitness": 28.56205517792883}
observability_snapshot        | {"total_pending": 0, "total_retired": 1371, "n_retirement_reports": 105}
economic_circulation_snapshot | {"n_attributions": 3136, "avg_attribution_weight": 0.2761509250637755, "total_pnl_contribution": 0.0, "avg_sharpe_contribution": 0.0}
drift_snapshot                | {"composite_severity": 0.0003, "regime_drift_score": 0.0004, "feature_drift_score": 0.001, "strategy_drift_score": 0.0, "execution_drift_score": 0.0}
retirement_snapshot           | {"n_active": 100, "n_monitor": 0, "n_retired": 0, "n_retirement_pending": 0, "n_strategies_analyzed": 100}
metadata                      | {"collected_at": "2026-05-27T06:59:50.546960+00:00"}
-[ RECORD 2 ]-----------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                            | 2
recorded_at                   | 2026-05-27 06:59:58.095855+00
runtime_minutes               | 0
execution_activation_score    | 0.5517
execution_realism_score       | 1
scout_ecosystem_score         | 0.2025
advanced_validation_score     | 0.3751
specialization_score          | 0.1134
observability_score           | 0.48
economic_circulation_score    | 0.45
full_activation_score         | 0.5541
dominant_organisms            | 0
specialization_rankings       | [{"n_obs": 618, "regime": "ranging", "survivability": 0.41230760517799453, "profile_confidence": 0.24658058252427037}]
scout_rankings                | [{"n_obs": 2903, "scout": "ideator_archetype_momentum", "n_survived": 0, "avg_pnl_contribution": 0.0, "avg_attribution_weight": 0.266667, "avg_sharpe_contribution": 0.0, "avg_drawdown_contribution": 0.0, "avg_win_rate_contribution": 0.0}, {"n_obs": 36, "scout": "regime_scout", "n_survived": 0, "avg_pnl_contribution": 0.0, "avg_attribution_weight": 0.5, "avg_sharpe_c... [TRUNCATED]
copy_quality_rankings         | [{"n_obs": 2, "leader_id": "87bf6ffa-d639-4403-9c6b-fa24235c05b5", "follower_id": "7416c767-c7e7-401b-90c7-e4e5b242b3ca", "replay_integrity": 0.98, "sync_quality_score": 1.0, "follower_survivability": 0.9}, {"n_obs": 2, "leader_id": "069cb59a-11de-476c-b802-c55f08964997", "follower_id": "855249b2-6376-4d5c-886e-ad349ab72337", "replay_integrity": 0.98, "sync_quality_... [TRUNCATED]
validation_snapshot           | {"avg_sharpe": 0.0, "avg_trades": 74.63814474210317, "n_backtests": 2501, "avg_win_rate": 0.12568079641502108, "avg_composite_fitness": 28.56205517792883}
observability_snapshot        | {"total_pending": 0, "total_retired": 1371, "n_retirement_reports": 106}
economic_circulation_snapshot | {"n_attributions": 3136, "avg_attribution_weight": 0.2761509250637755, "total_pnl_contribution": 0.0, "avg_sharpe_contribution": 0.0}
drift_snapshot                | {"composite_severity": 0.0003, "regime_drift_score": 0.0004, "feature_drift_score": 0.001, "strategy_drift_score": 0.0, "execution_drift_score": 0.0}
retirement_snapshot           | {"n_active": 100, "n_monitor": 0, "n_retired": 0, "n_retirement_pending": 0, "n_strategies_analyzed": 100}
metadata                      | {"collected_at": "2026-05-27T06:59:58.143868+00:00"}


```

---

## 80. `phase37_activation_weights`

- **Row count:** 213
- **Columns (4):**
  - `id (integer)`
  - `learned_at (timestamp with time zone)`
  - `domain_weights (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id             | 1
learned_at     | 2026-05-27 11:20:47.519793+00
domain_weights | {"scout": 0.21531021232899403, "regime": 0.012786114147537183, "capital": 0.09791645963761635, "mutation": 0.0510782072940475, "survival": 0.16562324025307232, "execution": 0.0, "perturbation": 0.3311471065619928, "specialization": 0.12613865977673988}
metadata       | {"source": "phase37_long_horizon_intelligence"}
-[ RECORD 2 ]--+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id             | 2
learned_at     | 2026-05-27 11:20:54.230644+00
domain_weights | {"scout": 0.21531021232899403, "regime": 0.012786114147537183, "capital": 0.09791645963761635, "mutation": 0.0510782072940475, "survival": 0.16562324025307232, "execution": 0.0, "perturbation": 0.3311471065619928, "specialization": 0.12613865977673988}
metadata       | {"source": "phase37_long_horizon_intelligence"}


```

---

## 81. `phase37_intelligence_metrics`

- **Row count:** 215
- **Columns (27):**
  - `id (integer)`
  - `recorded_at (timestamp with time zone)`
  - `runtime_minutes (integer)`
  - `dominant_organisms (integer)`
  - `long_horizon_specialization_score (double precision)`
  - `mutation_dominance_score (double precision)`
  - `scout_intelligence_score (double precision)`
  - `capital_migration_score (double precision)`
  - `survival_quality_score (double precision)`
  - `perturbation_resilience_score (double precision)`
  - `execution_survivability_score (double precision)`
  - `diversification_quality (double precision)`
  - `regime_adaptation_quality (double precision)`
  - `retirement_pressure_score (double precision)`
  - `replay_integrity (double precision)`
  - `specialization_lineage_history (jsonb)`
  - `mutation_family_rankings (jsonb)`
  - `mutation_survival_curves (jsonb)`
  - `scout_trust_rankings (jsonb)`
  - `scout_specialization_history (jsonb)`
  - *... and 7 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                                | 1
recorded_at                       | 2026-05-27 11:20:47.460306+00
runtime_minutes                   | 0
dominant_organisms                | 0
long_horizon_specialization_score | 0.3808
mutation_dominance_score          | 0.1542
scout_intelligence_score          | 0.65
capital_migration_score           | 0.2956
survival_quality_score            | 0.5
perturbation_resilience_score     | 0.9997
execution_survivability_score     | 0
diversification_quality           | 0
regime_adaptation_quality         | 0.0386
retirement_pressure_score         | 0
replay_integrity                  | 1
specialization_lineage_history    | [{"status": "emerging", "efficiency": 3500.0, "strategy_id": "41bd49bb-ed21-46c5-9a47-4d4b38d3c8f1", "lifespan_bars": 0, "strategy_name": "trend_following_equity_det_225550_45", "dominance_score": 70, "specializations": [], "composite_expectancy": -0.15, "dominance_categories": ["longevity", "capital_efficiency"], "specialization_score": 0}, {"status": "emerging... [TRUNCATED]
mutation_family_rankings          | [{"mutation_type": "repair::threshold_adjustment", "survival_rate": 0.0948, "survived_count": 11, "total_applications": 116, "avg_fitness_contribution": 34.5}, {"mutation_type": "repair::rsi_threshold_shift", "survival_rate": 0.0545, "survived_count": 6, "total_applications": 110, "avg_fitness_contribution": 31.0}, {"mutation_type": "simplification::condition_re... [TRUNCATED]
mutation_survival_curves          | [{"day": "2026-05-18 00:00:00+00:00", "avg_sharpe": 0.0, "avg_fitness": 0.0, "avg_drawdown": 0.0, "mutation_type": "repair::threshold_adjustment", "survival_rate": 0.0, "survived_count": 0, "total_applications": 43}, {"day": "2026-05-18 00:00:00+00:00", "avg_sharpe": 0.0, "avg_fitness": 0.0, "avg_drawdown": 0.0, "mutation_type": "simplification::condition_remova... [TRUNCATED]
scout_trust_rankings              | [{"n_failed": 0, "scout_name": "regime_scout", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "composite_divergence_score": 0.278}, {"n_failed": 2, "scout_name": "ideator_archetype_momentum", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 2, "composite_divergence_score": 0.265}, {"n_failed": 0, "scout_name": "ideator_arch... [TRUNCATED]
scout_specialization_history      | [{"n_failed": 0, "scout_name": "regime_scout", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "attribution_quality": 0.26, "contradiction_penalty": 0, "composite_divergence_score": 0.278}, {"n_failed": 2, "scout_name": "ideator_archetype_momentum", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 2, "attribution_quality": 0... [TRUNCATED]
capital_allocation_migration      | {"tracked_at": "2026-05-27 11:20:46.574898+00:00", "weak_penalized": 0, "capital_migrated": 0.3825, "dominant_boosted": 0, "concentration_risk": 0.0, "diversification_score": 0.0, "drawdown_recovery_speed": 0.0, "portfolio_survivability": 0.0}
survival_quality_evolution        | {"late": {"expectancy": 0.0, "half_life_hours": 7.213600000000021, "regime_persistence": 0.0, "recovery_efficiency": 1.0, "return_per_drawdown": 0.0, "risk_adjusted_return": 0.0, "execution_degradation": 0.0, "cascading_failure_risk": 0.0, "mutation_survival_rate": 0.0, "portfolio_contagion_risk": 0.0, "concentration_instability": 0.0015000000000000011, "drawdow... [TRUNCATED]
perturbation_snapshot             | {"drift_severity": 0.0003, "regime_drift_score": 0.0004, "active_perturbations": [], "strategy_drift_score": 0.0, "execution_drift_score": 0.0}
regime_specialization_snapshot    | {"ecosystem_health": {"n_retired": 0, "n_degraded": 0, "avg_lifespan_bars": 907.5, "n_surviving_organisms": 17, "dominant_concentration": 0.54}, "n_organisms_total": 200, "regime_specialists": [], "n_dominant_identified": 108}
retirement_snapshot               | {"n_active": 100, "n_monitor": 0, "n_retired": 0, "analyzed_at": "2026-05-27 11:20:47.059777+00:00", "n_retirement_pending": 0, "n_strategies_analyzed": 100, "capital_withdrawal_signals": [], "retirement_recommendations": []}
execution_realism_snapshot        | {}
metadata                          | {"collected_at": "2026-05-27 11:20:47.511854+00:00"}
-[ RECORD 2 ]---------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                                | 2
recorded_at                       | 2026-05-27 11:20:54.188744+00
runtime_minutes                   | 0
dominant_organisms                | 0
long_horizon_specialization_score | 0.3808
mutation_dominance_score          | 0.1542
scout_intelligence_score          | 0.65
capital_migration_score           | 0.2956
survival_quality_score            | 0.5
perturbation_resilience_score     | 0.9997
execution_survivability_score     | 0
diversification_quality           | 0
regime_adaptation_quality         | 0.0386
retirement_pressure_score         | 0
replay_integrity                  | 1
specialization_lineage_history    | [{"status": "emerging", "efficiency": 3500.0, "strategy_id": "41bd49bb-ed21-46c5-9a47-4d4b38d3c8f1", "lifespan_bars": 0, "strategy_name": "trend_following_equity_det_225550_45", "dominance_score": 70, "specializations": [], "composite_expectancy": -0.15, "dominance_categories": ["longevity", "capital_efficiency"], "specialization_score": 0}, {"status": "emerging... [TRUNCATED]
mutation_family_rankings          | [{"mutation_type": "repair::threshold_adjustment", "survival_rate": 0.0948, "survived_count": 11, "total_applications": 116, "avg_fitness_contribution": 34.5}, {"mutation_type": "repair::rsi_threshold_shift", "survival_rate": 0.0545, "survived_count": 6, "total_applications": 110, "avg_fitness_contribution": 31.0}, {"mutation_type": "simplification::condition_re... [TRUNCATED]
mutation_survival_curves          | [{"day": "2026-05-18 00:00:00+00:00", "avg_sharpe": 0.0, "avg_fitness": 0.0, "avg_drawdown": 0.0, "mutation_type": "repair::threshold_adjustment", "survival_rate": 0.0, "survived_count": 0, "total_applications": 43}, {"day": "2026-05-18 00:00:00+00:00", "avg_sharpe": 0.0, "avg_fitness": 0.0, "avg_drawdown": 0.0, "mutation_type": "simplification::condition_remova... [TRUNCATED]
scout_trust_rankings              | [{"n_failed": 0, "scout_name": "regime_scout", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "composite_divergence_score": 0.278}, {"n_failed": 2, "scout_name": "ideator_archetype_momentum", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 2, "composite_divergence_score": 0.265}, {"n_failed": 0, "scout_name": "ideator_arch... [TRUNCATED]
scout_specialization_history      | [{"n_failed": 0, "scout_name": "regime_scout", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "attribution_quality": 0.26, "contradiction_penalty": 0, "composite_divergence_score": 0.278}, {"n_failed": 2, "scout_name": "ideator_archetype_momentum", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 2, "attribution_quality": 0... [TRUNCATED]
capital_allocation_migration      | {"tracked_at": "2026-05-27 11:20:53.411245+00:00", "weak_penalized": 0, "capital_migrated": 0.3825, "dominant_boosted": 0, "concentration_risk": 0.0, "diversification_score": 0.0, "drawdown_recovery_speed": 0.0, "portfolio_survivability": 0.0}
survival_quality_evolution        | {"late": {"expectancy": 0.0, "half_life_hours": 7.213600000000021, "regime_persistence": 0.0, "recovery_efficiency": 1.0, "return_per_drawdown": 0.0, "risk_adjusted_return": 0.0, "execution_degradation": 0.0, "cascading_failure_risk": 0.0, "mutation_survival_rate": 0.0, "portfolio_contagion_risk": 0.0, "concentration_instability": 0.0015000000000000011, "drawdow... [TRUNCATED]
perturbation_snapshot             | {"drift_severity": 0.0003, "regime_drift_score": 0.0004, "active_perturbations": [], "strategy_drift_score": 0.0, "execution_drift_score": 0.0}
regime_specialization_snapshot    | {"ecosystem_health": {"n_retired": 0, "n_degraded": 0, "avg_lifespan_bars": 913.0, "n_surviving_organisms": 17, "dominant_concentration": 0.54}, "n_organisms_total": 200, "regime_specialists": [], "n_dominant_identified": 108}
retirement_snapshot               | {"n_active": 100, "n_monitor": 0, "n_retired": 0, "analyzed_at": "2026-05-27 11:20:53.852695+00:00", "n_retirement_pending": 0, "n_strategies_analyzed": 100, "capital_withdrawal_signals": [], "retirement_recommendations": []}
execution_realism_snapshot        | {}
metadata                          | {"collected_at": "2026-05-27 11:20:54.221122+00:00"}


```

---

## 82. `portfolio_evolution_log`

- **Row count:** 508
- **Columns (21):**
  - `id (character varying)`
  - `tracked_at (timestamp with time zone)`
  - `n_organisms_analyzed (integer)`
  - `n_dominant_organisms (integer)`
  - `stress_active (boolean)`
  - `organism_strength_scores (jsonb)`
  - `correlation_penalties (jsonb)`
  - `diversification_rewards (jsonb)`
  - `pressured_allocations (jsonb)`
  - `migration_signals (jsonb)`
  - `evolution_pressure_stats (jsonb)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`
  - `portfolio_id (text)`
  - `diversification_score (double precision)`
  - `correlation_collapse_risk (double precision)`
  - `contagion_exposure (double precision)`
  - `concentration_risk (double precision)`
  - `portfolio_survivability (double precision)`
  - `drawdown_recovery_speed (double precision)`
  - *... and 1 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                        | 99a997f9-9e8d-49b6-9ae7-a008b9ddf1d8
tracked_at                | 2026-05-25 14:18:24.63586+00
n_organisms_analyzed      | 9
n_dominant_organisms      | 5
stress_active             | f
organism_strength_scores  | [{"is_weak": false, "is_strong": false, "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "strategy_name": "volatility_regime_crypto_local_082258", "current_weight": 0.0, "strength_score": 0.3449}, {"is_weak": false, "is_strong": false, "strategy_id": "75387203-1fc4-4bed-b6dd-dfc65caddd5f", "strategy_name": "volatility_regime_crypto_local_082233", "current_weight":... [TRUNCATED]
correlation_penalties     | [{"archetype": "volatility_regime", "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "cluster_size": 4, "strategy_name": "volatility_regime_crypto_local_082220", "correlation_penalty": 0.3333333333333333}, {"archetype": "volatility_regime", "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "cluster_size": 4, "strategy_name": "volatility_regime_crypto_local_08... [TRUNCATED]
diversification_rewards   | [{"archetype": "volatility_regime", "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "strategy_name": "volatility_regime_crypto_local_082220", "archetype_frequency": 4, "diversification_reward_mult": 1.0}, {"archetype": "volatility_regime", "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "strategy_name": "volatility_regime_crypto_local_082258", "archetype_f... [TRUNCATED]
pressured_allocations     | [{"is_weak": false, "archetype": "volatility_regime", "is_dominant": false, "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "strategy_name": "volatility_regime_crypto_local_082220", "current_weight": 0.0, "strength_score": 0.3384, "evolution_adjustment": 0.1111, "evolution_adjusted_weight": 0.1111, "correlation_penalty_applied": true, "diversification_reward_appl... [TRUNCATED]
migration_signals         | [{"amount": 0.1111, "reason": "correlation_cluster_penalty", "archetype": "volatility_regime", "direction": "increase", "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "strategy_name": "volatility_regime_crypto_local_082220"}, {"amount": 0.1111, "reason": "dominant_organism_concentration; correlation_cluster_penalty", "archetype": "volatility_regime", "direction"... [TRUNCATED]
evolution_pressure_stats  | {"n_weak_penalized": 0, "n_dominant_boosted": 9, "n_correlated_penalized": 9, "total_capital_migrated": 0.4999, "stress_diversification_active": false}
metadata                  | {"method": "evolutionary_selection_pressure"}
created_at                | 2026-05-25 14:18:24.63712+00
portfolio_id              |
diversification_score     | 0
correlation_collapse_risk | 0
contagion_exposure        | 0
concentration_risk        | 0
portfolio_survivability   | 0
drawdown_recovery_speed   | 0
active_strategies         | 0
-[ RECORD 2 ]-------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                        | 356908b1-bc25-4517-8b79-8b9446eb91bf
tracked_at                | 2026-05-25 14:18:39.964495+00
n_organisms_analyzed      | 9
n_dominant_organisms      | 5
stress_active             | t
organism_strength_scores  | [{"is_weak": false, "is_strong": false, "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "strategy_name": "volatility_regime_crypto_local_082258", "current_weight": 0.0, "strength_score": 0.3449}, {"is_weak": false, "is_strong": false, "strategy_id": "75387203-1fc4-4bed-b6dd-dfc65caddd5f", "strategy_name": "volatility_regime_crypto_local_082233", "current_weight":... [TRUNCATED]
correlation_penalties     | [{"archetype": "volatility_regime", "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "cluster_size": 4, "strategy_name": "volatility_regime_crypto_local_082220", "correlation_penalty": 0.3333333333333333}, {"archetype": "volatility_regime", "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "cluster_size": 4, "strategy_name": "volatility_regime_crypto_local_08... [TRUNCATED]
diversification_rewards   | [{"archetype": "volatility_regime", "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "strategy_name": "volatility_regime_crypto_local_082220", "archetype_frequency": 4, "diversification_reward_mult": 1.0}, {"archetype": "volatility_regime", "strategy_id": "f69702f6-03d3-45da-9148-a9351dfd1920", "strategy_name": "volatility_regime_crypto_local_082258", "archetype_f... [TRUNCATED]
pressured_allocations     | [{"is_weak": false, "archetype": "volatility_regime", "is_dominant": false, "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "strategy_name": "volatility_regime_crypto_local_082220", "current_weight": 0.0, "strength_score": 0.3384, "evolution_adjustment": 0.1111, "evolution_adjusted_weight": 0.1111, "correlation_penalty_applied": true, "diversification_reward_appl... [TRUNCATED]
migration_signals         | [{"amount": 0.1111, "reason": "correlation_cluster_penalty", "archetype": "volatility_regime", "direction": "increase", "strategy_id": "739cfb48-53ed-4ad5-9944-c271880d2008", "strategy_name": "volatility_regime_crypto_local_082220"}, {"amount": 0.1111, "reason": "dominant_organism_concentration; correlation_cluster_penalty", "archetype": "volatility_regime", "direction"... [TRUNCATED]
evolution_pressure_stats  | {"n_weak_penalized": 0, "n_dominant_boosted": 9, "n_correlated_penalized": 9, "total_capital_migrated": 0.4999, "stress_diversification_active": true}
metadata                  | {"method": "evolutionary_selection_pressure"}
created_at                | 2026-05-25 14:18:39.965726+00
portfolio_id              |
diversification_score     | 0
correlation_collapse_risk | 0
contagion_exposure        | 0
concentration_risk        | 0
portfolio_survivability   | 0
drawdown_recovery_speed   | 0
active_strategies         | 0


```

---

## 83. `portfolio_intelligence`

- **Row count:** 24
- **Columns (14):**
  - `id (uuid)`
  - `computed_at (timestamp with time zone)`
  - `n_strategies (integer)`
  - `strategy_ids (jsonb)`
  - `correlation_matrix (jsonb)`
  - `covariance_matrix (jsonb)`
  - `cluster_map (jsonb)`
  - `efficiency_scores (jsonb)`
  - `optimal_allocations (jsonb)`
  - `regime_conditioned_weights (jsonb)`
  - `ensemble_survivability_score (numeric)`
  - `concentration_risk (numeric)`
  - `diversification_score (numeric)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                           | 9fbd585d-5ca1-4cdf-a032-9c20320e857f
computed_at                  | 2026-05-22 07:13:24.20726+00
n_strategies                 | 50
strategy_ids                 | ["8d3be794-913d-49d3-8b5b-f0b8d7d8e6b3", "69885aed-9c59-4e95-9a2c-bfe3521ef488", "5c8314b8-46c3-4c28-8059-39beb2744fae", "792e951c-b6ab-4e9a-8948-814927945736", "04fe5b08-a19d-43d4-9ab6-7b844fac8c81", "bf9aed13-eb4d-41ea-b5b9-c3cdb3c74fb8", "94581a3d-b8cc-4764-be48-e9bf4a7e3cb9", "83433d79-0dd4-4307-90ce-841cd054e0c4", "2a98291b-6d08-4d32-9cad-22af15ad4730", "e9f9d79... [TRUNCATED]
correlation_matrix           | [[1.0, 1.0, 0.859253106061668, 0.9976751147854676, 0.8576751147854677, 0.8587554436992549, 0.9976751147854676, 0.854628298491538, 0.8549381245225655, 0.8581691540382282, 0.8581691540382282, 0.8523181819717441, 0.8480787297360349, 0.8396964238866279, 0.8450030732974979, 0.8387435590891691, 0.8480787297360349, 0.8480787297360349, 0.8480787297360349, 0.8480783730618248,... [TRUNCATED]
covariance_matrix            | [[128.64414480194986, 128.64414480194986, 111.30868481850413, 129.2163576922263, 111.08391175986317, 111.44234763569496, 129.2163576922263, 111.56740392242847, 111.90446233727037, 113.37856442839602, 113.37856442839602, 113.06104247399324, 111.3944019816016, 110.31204430806166, 114.47070215165947, 110.4298001808908, 111.3944019816016, 111.3944019816016, 111.394401981... [TRUNCATED]
cluster_map                  | {"unknown|UNKNOWN": {"symbol": "UNKNOWN", "archetype": "unknown", "avg_score": 39.199999999999996, "n_strategies": 6, "strategy_ids": ["5c8314b8-46c3-4c28-8059-39beb2744fae", "04fe5b08-a19d-43d4-9ab6-7b844fac8c81", "bf9aed13-eb4d-41ea-b5b9-c3cdb3c74fb8", "83433d79-0dd4-4307-90ce-841cd054e0c4", "e9f9d79e-4843-45ad-9ef7-587a94e98564", "61e76b00-0d67-4f51-9d1d-7ec62e393... [TRUNCATED]
efficiency_scores            | [{"score": 40.2, "efficiency": 4020.0, "strategy_id": "8d3be794-913d-49d3-8b5b-f0b8d7d8e6b3", "max_drawdown": -0.6358, "strategy_name": "trend_following_equity_tmpl_063225"}, {"score": 40.2, "efficiency": 4020.0, "strategy_id": "69885aed-9c59-4e95-9a2c-bfe3521ef488", "max_drawdown": -0.6358, "strategy_name": "trend_following_equity_tmpl_072630"}, {"score": 40.1, "eff... [TRUNCATED]
optimal_allocations          | [{"score": 40.2, "sharpe": 0.0, "weight": 0.022, "strategy_id": "8d3be794-913d-49d3-8b5b-f0b8d7d8e6b3", "strategy_name": "trend_following_equity_tmpl_063225"}, {"score": 40.2, "sharpe": 0.0, "weight": 0.022, "strategy_id": "69885aed-9c59-4e95-9a2c-bfe3521ef488", "strategy_name": "trend_following_equity_tmpl_072630"}, {"score": 40.1, "sharpe": 0.0, "weight": 0.022, "s... [TRUNCATED]
regime_conditioned_weights   | {"04fe5b08-a19d-43d4-9ab6-7b844fac8c81": {"raw_score": 40.1, "adjusted_score": 41.08, "liq_regime_adjustment": 1.0, "vol_regime_adjustment": 1.0}, "0aba7737-9791-46bc-bfed-264427cf2605": {"raw_score": 39.6, "adjusted_score": 40.45, "liq_regime_adjustment": 1.0, "vol_regime_adjustment": 1.0}, "0c6d3b4b-708a-4e35-b499-9bdacc620bd9": {"raw_score": 39.3, "adjusted_score"... [TRUNCATED]
ensemble_survivability_score | 18.590699999999998226485331542789936065673828125
concentration_risk           | 0.000100000000000000004792173602385929598312941379845142364501953125
diversification_score        | 0.498599999999999987654319966168259270489215850830078125
metadata                     | {"method": "mean_variance_with_clustering", "correlation_window": "full_history"}
-[ RECORD 2 ]----------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                           | 2e083467-2b46-4805-a81c-b0025ad2cda6
computed_at                  | 2026-05-22 07:21:38.946477+00
n_strategies                 | 50
strategy_ids                 | ["8d3be794-913d-49d3-8b5b-f0b8d7d8e6b3", "69885aed-9c59-4e95-9a2c-bfe3521ef488", "5c8314b8-46c3-4c28-8059-39beb2744fae", "792e951c-b6ab-4e9a-8948-814927945736", "04fe5b08-a19d-43d4-9ab6-7b844fac8c81", "bf9aed13-eb4d-41ea-b5b9-c3cdb3c74fb8", "94581a3d-b8cc-4764-be48-e9bf4a7e3cb9", "83433d79-0dd4-4307-90ce-841cd054e0c4", "2a98291b-6d08-4d32-9cad-22af15ad4730", "e9f9d79... [TRUNCATED]
correlation_matrix           | [[1.0, 1.0, 0.859253106061668, 0.9976751147854676, 0.8576751147854677, 0.8587554436992549, 0.9976751147854676, 0.854628298491538, 0.8549381245225655, 0.8581691540382282, 0.8581691540382282, 0.8523181819717441, 0.8480787297360349, 0.8396964238866279, 0.8450030732974979, 0.8387435590891691, 0.8480787297360349, 0.8480787297360349, 0.8480787297360349, 0.8480783730618248,... [TRUNCATED]
covariance_matrix            | [[128.64414480194986, 128.64414480194986, 111.30868481850413, 129.2163576922263, 111.08391175986317, 111.44234763569496, 129.2163576922263, 111.56740392242847, 111.90446233727037, 113.37856442839602, 113.37856442839602, 113.06104247399324, 111.3944019816016, 110.31204430806166, 114.47070215165947, 110.4298001808908, 111.3944019816016, 111.3944019816016, 111.394401981... [TRUNCATED]
cluster_map                  | {"unknown|UNKNOWN": {"symbol": "UNKNOWN", "archetype": "unknown", "avg_score": 39.199999999999996, "n_strategies": 6, "strategy_ids": ["5c8314b8-46c3-4c28-8059-39beb2744fae", "04fe5b08-a19d-43d4-9ab6-7b844fac8c81", "bf9aed13-eb4d-41ea-b5b9-c3cdb3c74fb8", "83433d79-0dd4-4307-90ce-841cd054e0c4", "e9f9d79e-4843-45ad-9ef7-587a94e98564", "61e76b00-0d67-4f51-9d1d-7ec62e393... [TRUNCATED]
efficiency_scores            | [{"score": 40.2, "efficiency": 4020.0, "strategy_id": "8d3be794-913d-49d3-8b5b-f0b8d7d8e6b3", "max_drawdown": -0.6358, "strategy_name": "trend_following_equity_tmpl_063225"}, {"score": 40.2, "efficiency": 4020.0, "strategy_id": "69885aed-9c59-4e95-9a2c-bfe3521ef488", "max_drawdown": -0.6358, "strategy_name": "trend_following_equity_tmpl_072630"}, {"score": 40.1, "eff... [TRUNCATED]
optimal_allocations          | [{"score": 40.2, "sharpe": 0.0, "weight": 0.022, "strategy_id": "8d3be794-913d-49d3-8b5b-f0b8d7d8e6b3", "strategy_name": "trend_following_equity_tmpl_063225"}, {"score": 40.2, "sharpe": 0.0, "weight": 0.022, "strategy_id": "69885aed-9c59-4e95-9a2c-bfe3521ef488", "strategy_name": "trend_following_equity_tmpl_072630"}, {"score": 40.1, "sharpe": 0.0, "weight": 0.022, "s... [TRUNCATED]
regime_conditioned_weights   | {"04fe5b08-a19d-43d4-9ab6-7b844fac8c81": {"raw_score": 40.1, "adjusted_score": 41.08, "liq_regime_adjustment": 1.0, "vol_regime_adjustment": 1.0}, "0aba7737-9791-46bc-bfed-264427cf2605": {"raw_score": 39.6, "adjusted_score": 40.45, "liq_regime_adjustment": 1.0, "vol_regime_adjustment": 1.0}, "0c6d3b4b-708a-4e35-b499-9bdacc620bd9": {"raw_score": 39.3, "adjusted_score"... [TRUNCATED]
ensemble_survivability_score | 18.590699999999998226485331542789936065673828125
concentration_risk           | 0.000100000000000000004792173602385929598312941379845142364501953125
diversification_score        | 0.498599999999999987654319966168259270489215850830078125
metadata                     | {"method": "mean_variance_with_clustering", "correlation_window": "full_history"}


```

---

## 84. `positions`

- **Row count:** 0
- **Columns (11):**
  - `id (uuid)`
  - `account_ref (text)`
  - `symbol (text)`
  - `qty (numeric)`
  - `avg_price (numeric)`
  - `side (text)`
  - `created_at (timestamp with time zone)`
  - `updated_at (timestamp with time zone)`
  - `strategy_id (uuid)`
  - `broker (text)`
  - `unrealized_pnl (numeric)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 85. `prompt_generation_log`

- **Row count:** 0
- **Columns (6):**
  - `id (text)`
  - `prompt_id (text)`
  - `strategy_id (text)`
  - `success (boolean)`
  - `generation_score (numeric)`
  - `generated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 86. `prompt_templates`

- **Row count:** 0
- **Columns (11):**
  - `id (text)`
  - `prompt_type (text)`
  - `prompt_text (text)`
  - `archetype (text)`
  - `status (text)`
  - `parent_prompt_id (text)`
  - `generation_count (integer)`
  - `success_count (integer)`
  - `effectiveness_score (numeric)`
  - `created_at (timestamp with time zone)`
  - `updated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 87. `regime_fitness_log`

- **Row count:** 0
- **Columns (11):**
  - `id (uuid)`
  - `strategy_id (text)`
  - `regime (text)`
  - `sharpe (numeric)`
  - `sortino (numeric)`
  - `win_rate (numeric)`
  - `max_drawdown (numeric)`
  - `total_trades (integer)`
  - `regime_fitness_score (numeric)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 88. `regime_perturbation_events`

- **Row count:** 2372
- **Columns (7):**
  - `id (integer)`
  - `perturbation_type (character varying)`
  - `status (character varying)`
  - `started_at (timestamp with time zone)`
  - `ended_at (timestamp with time zone)`
  - `severity (double precision)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                | 1
perturbation_type | flash_crash
status            | active
started_at        | 2026-05-25 14:18:24.644418+00
ended_at          |
severity          | 14.54
metadata          | {"category": "volatility", "description": "Flash crash â€” 5-15% drop over 5-15 minutes, sharp reversal", "stress_cycle": 0, "target_symbol": "NVDA", "duration_minutes": 14, "affected_channels": ["all"], "amplification_factor": 1.0}
-[ RECORD 2 ]-----+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                | 2
perturbation_type | resilience_assessment
status            | completed
started_at        | 2026-05-25 14:18:24.660677+00
ended_at          |
severity          | 1
metadata          | {"category": "assessment", "resilience_data": {"n_fragile": 5, "assessed_at": "2026-05-25T14:18:24.649430+00:00", "n_resilient": 0, "stress_level": 1.0, "avg_resilience": 0.3581, "max_resilience": 0.3869, "min_resilience": 0.3358, "strategies_assessed": 9, "strategy_resilience": {"2f9279e8-bfb5-465e-96ba-afbbf940353f": {"name": "mean_reversion_crypto_local_082244", "sharpe": 0,... [TRUNCATED]


```

---

## 89. `regime_specialization_aggregate`

- **Row count:** 492
- **Columns (6):**
  - `id (character varying)`
  - `computed_at (timestamp with time zone)`
  - `n_organisms_profiled (integer)`
  - `affinity_scores (jsonb)`
  - `ecosystem_specialization (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]------------+--------------------------------------------
id                       | 8d729cce-c07e-4570-b4f6-9b8c76cef86c
computed_at              | 2026-05-25 14:18:24.57942+00
n_organisms_profiled     | 0
affinity_scores          | {}
ecosystem_specialization | {}
metadata                 | {"method": "multi_factor_regime_profiling"}
-[ RECORD 2 ]------------+--------------------------------------------
id                       | cb540492-04ce-47b7-a0c2-b4983d028f1b
computed_at              | 2026-05-25 14:18:39.918726+00
n_organisms_profiled     | 0
affinity_scores          | {}
ecosystem_specialization | {}
metadata                 | {"method": "multi_factor_regime_profiling"}


```

---

## 90. `regime_specialization_log`

- **Row count:** 0
- **Columns (11):**
  - `id (text)`
  - `analysis_id (text)`
  - `regime (text)`
  - `n_observations (integer)`
  - `avg_fitness (numeric)`
  - `avg_sharpe (numeric)`
  - `avg_sortino (numeric)`
  - `avg_win_rate (numeric)`
  - `avg_drawdown (numeric)`
  - `total_trades (integer)`
  - `recorded_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 91. `regime_specialization_summary`

- **Row count:** 558
- **Columns (8):**
  - `id (text)`
  - `analysis_id (text)`
  - `computed_at (timestamp with time zone)`
  - `n_fragile_organisms (integer)`
  - `n_cross_regime_survivors (integer)`
  - `n_volatility_sensitive (integer)`
  - `n_liquidity_sensitive (integer)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]------------+--------------------------------------
id                       | 67dab32398874020
analysis_id              | 1fa59c5346734e81
computed_at              | 2026-05-24 11:26:44.987567+00
n_fragile_organisms      | 0
n_cross_regime_survivors | 0
n_volatility_sensitive   | 0
n_liquidity_sensitive    | 0
metadata                 | {"agent": "EconomicEfficiencyEngine"}
-[ RECORD 2 ]------------+--------------------------------------
id                       | 9ee4f54cea434a1a
analysis_id              | 5d37ca48a14c4072
computed_at              | 2026-05-24 11:28:57.167677+00
n_fragile_organisms      | 0
n_cross_regime_survivors | 0
n_volatility_sensitive   | 0
n_liquidity_sensitive    | 0
metadata                 | {"agent": "EconomicEfficiencyEngine"}


```

---

## 92. `regime_validation`

- **Row count:** 0
- **Columns (9):**
  - `id (uuid)`
  - `strategy_id (uuid)`
  - `regime_survival_map (jsonb)`
  - `regime_dependency_score (numeric)`
  - `regime_survival_score (numeric)`
  - `n_regimes_survived (integer)`
  - `passes_min_regimes (boolean)`
  - `over_specialized (boolean)`
  - `validated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 93. `replay_integrity`

- **Row count:** 530
- **Columns (7):**
  - `id (text)`
  - `checked_at (timestamp with time zone)`
  - `n_aggregates_checked (integer)`
  - `n_events_checked (integer)`
  - `integrity_score (numeric)`
  - `n_violations (integer)`
  - `details (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                   | 5fa1b768a0c040ee
checked_at           | 2026-05-22 07:13:24.701081+00
n_aggregates_checked | 20
n_events_checked     | 27
integrity_score      | 100
n_violations         | 0
details              | {"aggregates": ["4703d8d500214200", "d58f52889b764ec4", "1d7311009efa46a2", "b65a65c0bc6348ee", "1ddd8e2a942e4e19", "8a9e39e448784829", "8f876e89807247c3", "mutation_context_20260522_0633", "mutation_context_20260522_0529", "66107bb414d4463f", "4f00ae52bc234032", "cd178c6f762141a1", "d627a07b072c446a", "56ac51a916ba425c", "3516313adedc4fa3", "c4f351eb3c394a87", "ef2924d87fbd... [TRUNCATED]
-[ RECORD 2 ]--------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                   | e53aea27325e458f
checked_at           | 2026-05-22 07:21:39.386937+00
n_aggregates_checked | 20
n_events_checked     | 27
integrity_score      | 100
n_violations         | 0
details              | {"aggregates": ["4703d8d500214200", "d58f52889b764ec4", "1d7311009efa46a2", "b65a65c0bc6348ee", "1ddd8e2a942e4e19", "8a9e39e448784829", "8f876e89807247c3", "mutation_context_20260522_0633", "mutation_context_20260522_0529", "66107bb414d4463f", "4f00ae52bc234032", "cd178c6f762141a1", "d627a07b072c446a", "56ac51a916ba425c", "3516313adedc4fa3", "c4f351eb3c394a87", "ef2924d87fbd... [TRUNCATED]


```

---

## 94. `risk_state`

- **Row count:** 1
- **Columns (11):**
  - `id (uuid)`
  - `scope (text)`
  - `strategy_id (uuid)`
  - `halted (boolean)`
  - `reason (text)`
  - `triggered_by (text)`
  - `activated_at (timestamp with time zone)`
  - `released_at (timestamp with time zone)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`
  - `updated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]+-------------------------------------
id           | 108ff8fd-3c12-424c-9488-86861b55b359
scope        | portfolio
strategy_id  |
halted       | f
reason       | initial_state
triggered_by |
activated_at |
released_at  |
metadata     | {}
created_at   | 2026-05-19 06:37:01.993664+00
updated_at   | 2026-05-19 06:37:01.993664+00


```

---

## 95. `schema_version`

- **Row count:** 3
- **Columns (4):**
  - `version (text)`
  - `applied_at (timestamp with time zone)`
  - `description (text)`
  - `checksum (text)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------------------------------------------------------------------------
version     | v24.0
applied_at  | 2026-05-20 16:42:29.20916+00
description | Phase 24: Schema drift remediation, column alignment, start-up validation
checksum    |
-[ RECORD 2 ]-----------------------------------------------------------------------------
version     | v26.0
applied_at  | 2026-05-22 15:44:58.377557+00
description | Phase 26: Scout influence tracking, economic attribution, entropy governance
checksum    |


```

---

## 96. `scout_divergence_log`

- **Row count:** 479
- **Columns (12):**
  - `id (character varying)`
  - `tracked_at (timestamp with time zone)`
  - `n_attributions_analyzed (integer)`
  - `n_scouts_tracked (integer)`
  - `profit_contribution (jsonb)`
  - `failure_contribution (jsonb)`
  - `regime_usefulness (jsonb)`
  - `contradiction_penalties (jsonb)`
  - `attribution_quality (jsonb)`
  - `divergence_scores (jsonb)`
  - `ecosystem_scout_health (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                      | 4a0a7032-0e04-475c-b520-2c00a29444e0
tracked_at              | 2026-05-25 14:18:24.600529+00
n_attributions_analyzed | 643
n_scouts_tracked        | 2
profit_contribution     | []
failure_contribution    | []
regime_usefulness       | {"oversold": {"ideator_archetype_mean_reversion": {"n_failure": 0, "n_success": 0, "n_attributions": 197, "usefulness_score": 0.0}}, "overbought": {"ideator_archetype_momentum": {"n_failure": 0, "n_success": 0, "n_attributions": 446, "usefulness_score": 0.0}}}
contradiction_penalties | []
attribution_quality     | [{"scout_name": "ideator_archetype_mean_reversion", "total_delta": 0.0, "avg_confidence": 0.375, "n_attributions": 197, "regime_diversity": 1, "attribution_quality_score": 0.21}, {"scout_name": "ideator_archetype_momentum", "total_delta": 0.0, "avg_confidence": 0.2667, "n_attributions": 446, "regime_diversity": 1, "attribution_quality_score": 0.1667}]
divergence_scores       | [{"n_failed": 0, "scout_name": "ideator_archetype_mean_reversion", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "attribution_quality": 0.21, "contradiction_penalty": 0, "composite_divergence_score": 0.263}, {"n_failed": 0, "scout_name": "ideator_archetype_momentum", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "attribution_q... [TRUNCATED]
ecosystem_scout_health  | {"n_active_scouts": 2, "n_low_value_scouts": 2, "n_high_value_scouts": 0, "n_contradictory_scouts": 0}
metadata                | {"method": "multi_factor_divergence_scoring"}
-[ RECORD 2 ]-----------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                      | a160af4c-68a9-4f3c-818b-73fb01745e20
tracked_at              | 2026-05-25 14:18:39.938824+00
n_attributions_analyzed | 643
n_scouts_tracked        | 2
profit_contribution     | []
failure_contribution    | []
regime_usefulness       | {"oversold": {"ideator_archetype_mean_reversion": {"n_failure": 0, "n_success": 0, "n_attributions": 197, "usefulness_score": 0.0}}, "overbought": {"ideator_archetype_momentum": {"n_failure": 0, "n_success": 0, "n_attributions": 446, "usefulness_score": 0.0}}}
contradiction_penalties | []
attribution_quality     | [{"scout_name": "ideator_archetype_mean_reversion", "total_delta": 0.0, "avg_confidence": 0.375, "n_attributions": 197, "regime_diversity": 1, "attribution_quality_score": 0.21}, {"scout_name": "ideator_archetype_momentum", "total_delta": 0.0, "avg_confidence": 0.2667, "n_attributions": 446, "regime_diversity": 1, "attribution_quality_score": 0.1667}]
divergence_scores       | [{"n_failed": 0, "scout_name": "ideator_archetype_mean_reversion", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "attribution_quality": 0.21, "contradiction_penalty": 0, "composite_divergence_score": 0.263}, {"n_failed": 0, "scout_name": "ideator_archetype_momentum", "n_profitable": 0, "net_contribution": 0.0, "total_attributions": 0, "attribution_q... [TRUNCATED]
ecosystem_scout_health  | {"n_active_scouts": 2, "n_low_value_scouts": 2, "n_high_value_scouts": 0, "n_contradictory_scouts": 0}
metadata                | {"method": "multi_factor_divergence_scoring"}


```

---

## 97. `scout_economic_attribution`

- **Row count:** 3236
- **Columns (17):**
  - `id (uuid)`
  - `trace_id (text)`
  - `source_scout (text)`
  - `influence_type (text)`
  - `target_agent (text)`
  - `strategy_id (text)`
  - `strategy_name (text)`
  - `sharpe_contribution (numeric)`
  - `drawdown_contribution (numeric)`
  - `pnl_contribution (numeric)`
  - `win_rate_contribution (numeric)`
  - `attribution_weight (numeric)`
  - `survived_validation (boolean)`
  - `regime_at_time (text)`
  - `entropy_at_time (numeric)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---------+----------------------------------------------------
id                    | 4f574a99-9ceb-4e66-bccd-523a48f53666
trace_id              | b3b9e3c10ca446b7
source_scout          | ideator_archetype_momentum
influence_type        | archetype_selection
target_agent          | IdeatorV2_0_R
strategy_id           | b1c1b589-c68f-41af-a408-a6a20316eace
strategy_name         | momentum_equity_det_042248_33
sharpe_contribution   | 0
drawdown_contribution | 0
pnl_contribution      | 0
win_rate_contribution | 0
attribution_weight    | 0.2666669999999999873807610129006206989288330078125
survived_validation   | f
regime_at_time        | overbought
entropy_at_time       | 1
metadata              | {"before_value": 0.2}
created_at            | 2026-05-24 04:22:48.570879+00
-[ RECORD 2 ]---------+----------------------------------------------------
id                    | be1a2fca-975e-445f-b604-a431157d9227
trace_id              | 79ad3cc94bb74a4d
source_scout          | ideator_archetype_momentum
influence_type        | archetype_selection
target_agent          | IdeatorV2_0_R
strategy_id           | 5a36ed88-c96c-46d6-9f01-881ca9ff418c
strategy_name         | momentum_equity_det_042507_20
sharpe_contribution   | 0
drawdown_contribution | 0
pnl_contribution      | 0
win_rate_contribution | 0
attribution_weight    | 0.2666669999999999873807610129006206989288330078125
survived_validation   | f
regime_at_time        | overbought
entropy_at_time       | 1
metadata              | {"before_value": 0.2}
created_at            | 2026-05-24 04:25:07.161579+00


```

---

## 98. `scout_influence_log`

- **Row count:** 8740
- **Columns (14):**
  - `id (uuid)`
  - `trace_id (text)`
  - `source_scout (text)`
  - `target_agent (text)`
  - `influence_type (text)`
  - `influence_metric (text)`
  - `before_value (numeric)`
  - `after_value (numeric)`
  - `delta (numeric)`
  - `confidence (numeric)`
  - `regime_context (text)`
  - `entropy_context (numeric)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id               | 5c2bffbf-c9d6-4474-a7ad-00d3975a31cd
trace_id         |
source_scout     | regime_scout
target_agent     | IdeatorV2_0_R
influence_type   | archetype_modulation
influence_metric | momentum->mean_reversion
before_value     |
after_value      |
delta            | -0.11666700000000000680966394384086015634238719940185546875
confidence       | 0.59999999999999997779553950749686919152736663818359375
regime_context   | overbought
entropy_context  | 1
metadata         | {"all_weights": {"breakout": 0.2333333333333333, "momentum": 0.2666666666666667, "mean_reversion": 0.08333333333333334, "trend_following": 0.25000000000000006, "volatility_regime": 0.16666666666666669}, "to_archetype": "mean_reversion", "from_archetype": "momentum", "scout_aggression": 1.0}
created_at       | 2026-05-24 07:28:19.237309+00
-[ RECORD 2 ]----+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id               | afd6f983-2eed-4fb5-ad7f-312122550d63
trace_id         |
source_scout     | regime_scout
target_agent     | IdeatorV2_0_R
influence_type   | archetype_modulation
influence_metric | momentum->trend_following
before_value     |
after_value      |
delta            | 0.05000000000000000277555756156289135105907917022705078125
confidence       | 0.59999999999999997779553950749686919152736663818359375
regime_context   | overbought
entropy_context  | 1
metadata         | {"all_weights": {"breakout": 0.2333333333333333, "momentum": 0.2666666666666667, "mean_reversion": 0.08333333333333334, "trend_following": 0.25000000000000006, "volatility_regime": 0.16666666666666669}, "to_archetype": "trend_following", "from_archetype": "momentum", "scout_aggression": 1.0}
created_at       | 2026-05-24 07:28:24.274211+00


```

---

## 99. `scout_mirror_debug_log`

- **Row count:** 16101
- **Columns (9):**
  - `id (uuid)`
  - `table_name (text)`
  - `source (text)`
  - `symbol (text)`
  - `signal_type (text)`
  - `confidence_score (numeric)`
  - `success (boolean)`
  - `error_message (text)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----+-------------------------------------
id               | f0f1fb65-fd70-461d-a05b-e0255acd0f8f
table_name       | market_regime_memory
source           | regime_scout
symbol           | BTCUSDT
signal_type      | regime
confidence_score | 1
success          | t
error_message    |
created_at       | 2026-05-22 16:03:23.901562+00
-[ RECORD 2 ]----+-------------------------------------
id               | 13a79d0b-2237-4054-af15-0f58494d88de
table_name       | market_regime_memory
source           | regime_scout
symbol           | SPY
signal_type      | regime
confidence_score | 1
success          | t
error_message    |
created_at       | 2026-05-22 16:03:23.962487+00


```

---

## 100. `scout_poison_quarantine`

- **Row count:** 658
- **Columns (10):**
  - `id (text)`
  - `trace_id (text)`
  - `source (text)`
  - `source_sub (text)`
  - `violation_type (text)`
  - `severity_score (numeric)`
  - `affected_symbols (jsonb)`
  - `action_taken (text)`
  - `metadata (jsonb)`
  - `detected_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----+-------------------------------------------------------
id               | 6c2ee068a50f4f04
trace_id         | 1174b0efd52d461a
source           | regime_scout
source_sub       | all
violation_type   | signal_burst_spam
severity_score   | 0.8000000000000000444089209850062616169452667236328125
affected_symbols | ["MSFT"]
action_taken     | slash_trust_and_quarantine_signals
metadata         | {"reason": "29 signals in 1 hour for MSFT"}
detected_at      | 2026-05-23 17:04:51.373825+00
-[ RECORD 2 ]----+-------------------------------------------------------
id               | 9b9b9e81fa7d4a70
trace_id         | 090e7738d1cd41db
source           | regime_scout
source_sub       | all
violation_type   | signal_burst_spam
severity_score   | 0.8000000000000000444089209850062616169452667236328125
affected_symbols | ["SOLUSDT"]
action_taken     | slash_trust_and_quarantine_signals
metadata         | {"reason": "29 signals in 1 hour for SOLUSDT"}
detected_at      | 2026-05-23 17:04:51.428165+00


```

---

## 101. `scout_predictive_value_log`

- **Row count:** 1613
- **Columns (13):**
  - `id (text)`
  - `analysis_id (text)`
  - `source_scout (text)`
  - `computed_at (timestamp with time zone)`
  - `n_attributions (integer)`
  - `survival_rate (numeric)`
  - `avg_sharpe_contribution (numeric)`
  - `avg_pnl_contribution (numeric)`
  - `avg_drawdown_contribution (numeric)`
  - `contradiction_rate (numeric)`
  - `economic_score (numeric)`
  - `economic_score_penalized (numeric)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------+---------------------------------------------------------
id                        | 4ffade4ebe0c4d31
analysis_id               | 1fa59c5346734e81
source_scout              | ideator_archetype_momentum
computed_at               | 2026-05-24 11:26:44.987567+00
n_attributions            | 30
survival_rate             | 0
avg_sharpe_contribution   | 0
avg_pnl_contribution      | 0
avg_drawdown_contribution | 0
contradiction_rate        | 0
economic_score            | 0.200000000000000011102230246251565404236316680908203125
economic_score_penalized  | 0.200000000000000011102230246251565404236316680908203125
metadata                  | {"agent": "EconomicEfficiencyEngine"}
-[ RECORD 2 ]-------------+---------------------------------------------------------
id                        | fafddaaa622043c6
analysis_id               | 5d37ca48a14c4072
source_scout              | ideator_archetype_momentum
computed_at               | 2026-05-24 11:28:57.167677+00
n_attributions            | 32
survival_rate             | 0
avg_sharpe_contribution   | 0
avg_pnl_contribution      | 0
avg_drawdown_contribution | 0
contradiction_rate        | 0
economic_score            | 0.200000000000000011102230246251565404236316680908203125
economic_score_penalized  | 0.200000000000000011102230246251565404236316680908203125
metadata                  | {"agent": "EconomicEfficiencyEngine"}


```

---

## 102. `scout_quarantine`

- **Row count:** 0
- **Columns (6):**
  - `id (uuid)`
  - `source (text)`
  - `source_sub (text)`
  - `reasons (jsonb)`
  - `raw_payload (jsonb)`
  - `quarantined_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 103. `scout_signal_attribution`

- **Row count:** 0
- **Columns (12):**
  - `id (text)`
  - `signal_id (text)`
  - `source (text)`
  - `source_sub (text)`
  - `symbol (text)`
  - `executed_order_id (text)`
  - `hypothesis_id (text)`
  - `outcome_pnl (numeric)`
  - `attribution_score (numeric)`
  - `predictive_survivability (numeric)`
  - `metadata (jsonb)`
  - `attributed_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 104. `scout_signals`

- **Row count:** 14546
- **Columns (7):**
  - `id (uuid)`
  - `source (text)`
  - `symbol (text)`
  - `signal_type (text)`
  - `confidence_score (numeric)`
  - `signal_data (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]----+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id               | e55cdab9-c2a1-40a2-bfa8-84eb037b581b
source           | regime_scout
symbol           | BTCUSDT
signal_type      | regime
confidence_score | 1
signal_data      | {"trend_regime": "choppy", "atr_percentile": 71.75257731958763, "relative_volume": 0.2947, "liquidity_regime": "dangerous", "volatility_regime": "high_vol", "correlation_regime": "clustered", "expansion_detected": false, "vwap_deviation_pct": 0.0398, "realized_volatility": 0.142358, "compression_detected": true}
created_at       | 2026-05-22 16:13:25.696067+00
-[ RECORD 2 ]----+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id               | b406c1d3-1851-4e60-b52f-19c6787b426c
source           | regime_scout
symbol           | SPY
signal_type      | regime
confidence_score | 1
signal_data      | {"trend_regime": "choppy", "atr_percentile": 60.20618556701031, "relative_volume": 0.053, "liquidity_regime": "dangerous", "volatility_regime": "normal_vol", "correlation_regime": "diversified", "expansion_detected": false, "vwap_deviation_pct": 0.3674, "realized_volatility": 0.05599, "compression_detected": true}
created_at       | 2026-05-22 16:13:25.769443+00


```

---

## 105. `scout_synthesis_log`

- **Row count:** 326
- **Columns (13):**
  - `id (text)`
  - `trace_id (text)`
  - `confidence (numeric)`
  - `contextual_summary (text)`
  - `scout_agreement_score (numeric)`
  - `scout_disagreement_areas (jsonb)`
  - `market_state_interpretation (text)`
  - `confidence_weights (jsonb)`
  - `source_signals (jsonb)`
  - `advisory_only (boolean)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`
  - `disagreement_entropy (double precision)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]---------------+------------------------------------------------------------------------------------------------------------------------------
id                          | 88a9a8bb0e744a46
trace_id                    | 30ca6a4c70a8433c
confidence                  | 0.59999999999999997779553950749686919152736663818359375
contextual_summary          | 4 internal and 0 external scouts reporting. Agreement score: 0.75. Weighted direction: +0.25.
scout_agreement_score       | 0.75
scout_disagreement_areas    | []
market_state_interpretation | Mixed signals across sources â€” potential regime transition.
confidence_weights          | {"regime_scout": 0.85, "execution_scout": 0.8, "liquidity_scout": 0.8, "correlation_scout": 0.75}
source_signals              | {"regime_scout": "mean_reverting", "execution_scout": "healthy", "liquidity_scout": "healthy", "correlation_scout": "normal"}
advisory_only               | t
metadata                    | {"agent": "ScoutSynthesisEngine", "llm_used": true, "source_count": 4, "dominant_theme": "transitioning"}
created_at                  | 2026-05-23 16:56:52.721803+00
disagreement_entropy        | 0.5
-[ RECORD 2 ]---------------+------------------------------------------------------------------------------------------------------------------------------
id                          | 7c0f384392ed47cb
trace_id                    | a408d84104134715
confidence                  | 0.59999999999999997779553950749686919152736663818359375
contextual_summary          | 4 internal and 0 external scouts reporting. Agreement score: 0.75. Weighted direction: +0.25.
scout_agreement_score       | 0.75
scout_disagreement_areas    | []
market_state_interpretation | Mixed signals across sources â€” potential regime transition.
confidence_weights          | {"regime_scout": 0.85, "execution_scout": 0.8, "liquidity_scout": 0.8, "correlation_scout": 0.75}
source_signals              | {"regime_scout": "choppy", "execution_scout": "healthy", "liquidity_scout": "healthy", "correlation_scout": "normal"}
advisory_only               | t
metadata                    | {"agent": "ScoutSynthesisEngine", "llm_used": true, "source_count": 4, "dominant_theme": "transitioning"}
created_at                  | 2026-05-23 16:56:58.786265+00
disagreement_entropy        | 0.5


```

---

## 106. `source_performance_log`

- **Row count:** 128
- **Columns (11):**
  - `id (text)`
  - `source (text)`
  - `source_sub (text)`
  - `dynamic_trust_score (numeric)`
  - `historical_accuracy (numeric)`
  - `n_profitable_signals (integer)`
  - `n_loss_signals (integer)`
  - `n_quarantined_signals (integer)`
  - `recent_contradiction_rate (numeric)`
  - `metadata (jsonb)`
  - `updated_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------+-------------------------------------
id                        | fc90d1ca-8ee0-4afa-a9ca-9ed3034d16b7
source                    | correlation_scout
source_sub                | all
dynamic_trust_score       | 0.5
historical_accuracy       | 0.5
n_profitable_signals      | 0
n_loss_signals            | 0
n_quarantined_signals     | 0
recent_contradiction_rate | 0.0
metadata                  | {}
updated_at                | 2026-05-23 19:12:22.132557+00
-[ RECORD 2 ]-------------+-------------------------------------
id                        | 7448954c-4856-49d0-b7d8-1e22a62037e9
source                    | liquidity_scout
source_sub                | all
dynamic_trust_score       | 0.5
historical_accuracy       | 0.5
n_profitable_signals      | 0
n_loss_signals            | 0
n_quarantined_signals     | 0
recent_contradiction_rate | 0.0
metadata                  | {}
updated_at                | 2026-05-23 19:12:22.137586+00


```

---

## 107. `strategies`

- **Row count:** 2528
- **Columns (24):**
  - `id (uuid)`
  - `name (text)`
  - `code (text)`
  - `parameters (jsonb)`
  - `status (text)`
  - `created_at (timestamp with time zone)`
  - `author_agent (text)`
  - `prompt (text)`
  - `raw_response (text)`
  - `normalized_strategy (jsonb)`
  - `compile_error (text)`
  - `strategy_signature (text)`
  - `validation_metrics (jsonb)`
  - `train_sharpe (numeric)`
  - `test_sharpe (numeric)`
  - `holdout_sharpe (numeric)`
  - `stability_score (numeric)`
  - `overfit_flag (boolean)`
  - `regime_score (numeric)`
  - `trace_id (text)`
  - *... and 4 more columns*

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                  | 739cfb48-53ed-4ad5-9944-c271880d2008
name                | volatility_regime_crypto_local_082220
code                | import pandas as pd                                                                                                                                                                                                                                                                                                                                                                       ... [TRUNCATED]
                    | import numpy as np                                                                                                                                                                                                                                                                                                                                                                        ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    | class volatility_regime_crypto_local_082220:                                                                                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |     """Auto-generated from normalized strategy spec."""                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |     # Market regimes this strategy is designed for (empty = all allowed)                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |     VALID_REGIMES: list = []                                                                                                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |     def generate_signals(self, df):                                                                                                                                                                                                                                                                                                                                                       ... [TRUNCATED]
                    |         if df is None or df.empty:                                                                                                                                                                                                                                                                                                                                                        ... [TRUNCATED]
                    |             return pd.Series(dtype=int)                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         signals = pd.Series(0, index=df.index)                                                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         entry = (                                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |             (df['volatility_regime'] > 1.1)                                                                                                                                                                                                                                                                                                                                               ... [TRUNCATED]
                    |             & (df['rsi_14'] < 45)                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |         )                                                                                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         exit_ = (df['volatility_regime'] < 0.85)                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         # Regime classification â€” determines which market states are tradeable                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |         df['_regime'] = 'unknown'                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |         df.loc[df['volatility_regime'] > 1.4, '_vol_regime'] = 'high_vol'                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |         df.loc[df['volatility_regime'] < 0.7, '_vol_regime'] = 'low_vol'                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |         df.loc[(df['volatility_regime'] >= 0.7) & (df['volatility_regime'] <= 1.4), '_vol_regime'] = 'normal_vol'                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |         df.loc[df['trend_strength'] > 0.002, '_trend_regime'] = 'trending'                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         df.loc[df['trend_strength'] <= 0.002, '_trend_regime'] = 'ranging'                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         df.loc[df['ema_spread_pct'] > 0.001, '_direction'] = 'bullish'                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |         df.loc[df['ema_spread_pct'] < -0.001, '_direction'] = 'bearish'                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |         df.loc[(df['ema_spread_pct'] >= -0.001) & (df['ema_spread_pct'] <= 0.001), '_direction'] = 'neutral'                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |         df.loc[df['bollinger_band_position'] > 0.8, '_bb_regime'] = 'overbought'                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |         df.loc[df['bollinger_band_position'] < 0.2, '_bb_regime'] = 'oversold'                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |         df.loc[(df['bollinger_band_position'] >= 0.2) & (df['bollinger_band_position'] <= 0.8), '_bb_regime'] = 'normal'                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |         # Composite regime â€” combine volatility + trend for meaningful classification                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |         df.loc[df['_vol_regime'] == 'high_vol', '_regime'] = 'high_vol'                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |         df.loc[df['_vol_regime'] == 'low_vol', '_regime'] = 'low_vol'                                                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |         df.loc[(df['_direction'] == 'bullish') & (df['_trend_regime'] == 'trending'), '_regime'] = 'bullish'                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |         df.loc[(df['_direction'] == 'bearish') & (df['_trend_regime'] == 'trending'), '_regime'] = 'bearish'                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |         df.loc[(df['_trend_regime'] == 'ranging') & (df['_vol_regime'] == 'normal_vol'), '_regime'] = 'ranging'                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         df.loc[df['_bb_regime'] == 'overbought', '_regime'] = 'overbought'                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         df.loc[df['_bb_regime'] == 'oversold', '_regime'] = 'oversold'                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         # Position state machine â€” prevents exit spam, enforces holding discipline                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |         in_position = False                                                                                                                                                                                                                                                                                                                                                               ... [TRUNCATED]
                    |         bars_held = 0                                                                                                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |         cooldown = 0                                                                                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |         MIN_HOLD_BARS = 3                                                                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |         MAX_HOLD_BARS = 40                                                                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         entry_clean = entry.fillna(False)                                                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |         exit_clean = exit_.fillna(False)                                                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         for i in range(len(df)):                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |             if cooldown > 0:                                                                                                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |                 cooldown -= 1                                                                                                                                                                                                                                                                                                                                                             ... [TRUNCATED]
                    |                 continue                                                                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |             if not in_position:                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |                 if entry_clean.iloc[i]:                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                     # Regime gate â€” skip entry if current regime not in valid set                                                                                                                                                                                                                                                                                                       ... [TRUNCATED]
                    |                     if self.VALID_REGIMES and df['_regime'].iloc[i] not in self.VALID_REGIMES:                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |                         continue                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |                     signals.iloc[i] = 1                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                     in_position = True                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |                     bars_held = 1                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |             else:                                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |                 bars_held += 1                                                                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |                 if bars_held >= MAX_HOLD_BARS or (bars_held >= MIN_HOLD_BARS and exit_clean.iloc[i]):                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |                     signals.iloc[i] = -1                                                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |                     in_position = False                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                     bars_held = 0                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |                     cooldown = 5                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         return signals                                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |
parameters          | {"tags": ["volatility_regime", "crypto", "local_fallback"], "reasoning": "Fallback template â€” guaranteed signal generation", "stop_loss": "0.5% below entry", "timeframe": "1m", "hypothesis": "Local template: volatility_regime on crypto 1m data", "risk_level": "medium", "asset_class": "crypto", "take_profit": "1.0% above entry", "strategy_name": "volatility_regime_crypto_loc... [TRUNCATED]
status              | validated
created_at          | 2026-05-25 08:22:20.750609+00
author_agent        | IdeatorAgent_3
prompt              |
raw_response        |
normalized_strategy | {"tags": ["volatility_regime", "crypto", "local_fallback"], "reasoning": "Fallback template â€” guaranteed signal generation", "stop_loss": "0.5% below entry", "timeframe": "1m", "hypothesis": "Local template: volatility_regime on crypto 1m data", "risk_level": "medium", "asset_class": "crypto", "take_profit": "1.0% above entry", "strategy_name": "volatility_regime_crypto_loc... [TRUNCATED]
compile_error       |
strategy_signature  |
validation_metrics  |
train_sharpe        |
test_sharpe         |
holdout_sharpe      |
stability_score     |
overfit_flag        |
regime_score        |
trace_id            | 3fc2982fb34d419d
generation_batch    |
mutation_type       |
lifecycle_state     | active
age_bars            | 100
-[ RECORD 2 ]-------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                  | a4ee0c11-26ce-43cb-9390-593e9e1da964
name                | mean_reversion_equity_det_170411_96_mut1
code                | import pandas as pd                                                                                                                                                                                                                                                                                                                                                                       ... [TRUNCATED]
                    | import numpy as np                                                                                                                                                                                                                                                                                                                                                                        ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    | class mean_reversion_equity_det_170411_96_mut1:                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |     """Auto-generated from normalized strategy spec."""                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |     # Market regimes this strategy is designed for                                                                                                                                                                                                                                                                                                                                        ... [TRUNCATED]
                    |     VALID_REGIMES: list = ['oversold', 'ranging', 'normal_vol']                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |     def generate_signals(self, df):                                                                                                                                                                                                                                                                                                                                                       ... [TRUNCATED]
                    |         if df is None or df.empty:                                                                                                                                                                                                                                                                                                                                                        ... [TRUNCATED]
                    |             return pd.Series(dtype=int)                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         signals = pd.Series(0, index=df.index)                                                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         entry = (                                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |             (df['bollinger_band_position'] < 0.2200)                                                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |             & (df['price_vs_vwap_pct'] < -0.0027)                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |             & (df['rsi_14'] < 38.0)                                                                                                                                                                                                                                                                                                                                                       ... [TRUNCATED]
                    |         )                                                                                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         exit_ = (df['bollinger_band_position'] > 0.6959)                                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         # Regime classification â€” determines which market states are tradeable                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |         df['_regime'] = 'unknown'                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |         df.loc[df['volatility_regime'] > 1.4, '_vol_regime'] = 'high_vol'                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |         df.loc[df['volatility_regime'] < 0.7, '_vol_regime'] = 'low_vol'                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |         df.loc[(df['volatility_regime'] >= 0.7) & (df['volatility_regime'] <= 1.4), '_vol_regime'] = 'normal_vol'                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |         df.loc[df['trend_strength'] > 0.002, '_trend_regime'] = 'trending'                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         df.loc[df['trend_strength'] <= 0.002, '_trend_regime'] = 'ranging'                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         df.loc[df['ema_spread_pct'] > 0.001, '_direction'] = 'bullish'                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |         df.loc[df['ema_spread_pct'] < -0.001, '_direction'] = 'bearish'                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |         df.loc[(df['ema_spread_pct'] >= -0.001) & (df['ema_spread_pct'] <= 0.001), '_direction'] = 'neutral'                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |         df.loc[df['bollinger_band_position'] > 0.8, '_bb_regime'] = 'overbought'                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |         df.loc[df['bollinger_band_position'] < 0.2, '_bb_regime'] = 'oversold'                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |         df.loc[(df['bollinger_band_position'] >= 0.2) & (df['bollinger_band_position'] <= 0.8), '_bb_regime'] = 'normal'                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |         # Composite regime â€” combine volatility + trend for meaningful classification                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |         df.loc[df['_vol_regime'] == 'high_vol', '_regime'] = 'high_vol'                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |         df.loc[df['_vol_regime'] == 'low_vol', '_regime'] = 'low_vol'                                                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |         df.loc[(df['_direction'] == 'bullish') & (df['_trend_regime'] == 'trending'), '_regime'] = 'bullish'                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |         df.loc[(df['_direction'] == 'bearish') & (df['_trend_regime'] == 'trending'), '_regime'] = 'bearish'                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |         df.loc[(df['_trend_regime'] == 'ranging') & (df['_vol_regime'] == 'normal_vol'), '_regime'] = 'ranging'                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         df.loc[df['_bb_regime'] == 'overbought', '_regime'] = 'overbought'                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         df.loc[df['_bb_regime'] == 'oversold', '_regime'] = 'oversold'                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         # Position state machine â€” prevents exit spam, enforces holding discipline                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |         in_position = False                                                                                                                                                                                                                                                                                                                                                               ... [TRUNCATED]
                    |         bars_held = 0                                                                                                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |         cooldown = 0                                                                                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |         MIN_HOLD_BARS = 3                                                                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |         MAX_HOLD_BARS = 40                                                                                                                                                                                                                                                                                                                                                                ... [TRUNCATED]
                    |         entry_clean = entry.fillna(False)                                                                                                                                                                                                                                                                                                                                                 ... [TRUNCATED]
                    |         exit_clean = exit_.fillna(False)                                                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         for i in range(len(df)):                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |             if cooldown > 0:                                                                                                                                                                                                                                                                                                                                                              ... [TRUNCATED]
                    |                 cooldown -= 1                                                                                                                                                                                                                                                                                                                                                             ... [TRUNCATED]
                    |                 continue                                                                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |             if not in_position:                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |                 if entry_clean.iloc[i]:                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                     # Regime gate â€” skip entry if current regime not in valid set                                                                                                                                                                                                                                                                                                       ... [TRUNCATED]
                    |                     if self.VALID_REGIMES and df['_regime'].iloc[i] not in self.VALID_REGIMES:                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |                         continue                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |                     signals.iloc[i] = 1                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                     in_position = True                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |                     bars_held = 1                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |             else:                                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |                 bars_held += 1                                                                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |                 if bars_held >= MAX_HOLD_BARS or (bars_held >= MIN_HOLD_BARS and exit_clean.iloc[i]):                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |                     signals.iloc[i] = -1                                                                                                                                                                                                                                                                                                                                                  ... [TRUNCATED]
                    |                     in_position = False                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |                     bars_held = 0                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |                     cooldown = 5                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |         return signals                                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |
parameters          | {"name": "mean_reversion_equity_det_170411_96_mut1", "cooldown_bars": 5, "hold_time_max": 40, "hold_time_min": 3, "valid_regimes": ["oversold", "ranging", "normal_vol"], "changed_fields": {"entry_conditions[0]": "bollinger_band_position threshold relaxed from 0.1668 to 0.2200", "entry_conditions[2]": "rsi_14 threshold relaxed from 32.1851 to 38.0"}, "exit_conditions": ["bolli... [TRUNCATED]
status              | research_candidate
created_at          | 2026-05-25 17:05:54.94732+00
author_agent        | MutatorAgent
prompt              | Strategy: mean_reversion_equity_det_170411_96                                                                                                                                                                                                                                                                                                                                             ... [TRUNCATED]
                    | Sharpe: 0.00 | Entries: 5 | Trades: 1 | Hold: 3-40 | Cooldown: 5 | Regimes: ['oversold', 'ranging', 'normal_vol']                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    | DIAGNOSTIC: None                                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    | Current Spec:                                                                                                                                                                                                                                                                                                                                                                             ... [TRUNCATED]
                    | {                                                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |   "entry_conditions": [                                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |     "bollinger_band_position < 0.1668",                                                                                                                                                                                                                                                                                                                                                   ... [TRUNCATED]
                    |     "price_vs_vwap_pct < -0.0027",                                                                                                                                                                                                                                                                                                                                                        ... [TRUNCATED]
                    |     "rsi_14 < 32.1851"                                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |   ],                                                                                                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |   "exit_conditions": [                                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |     "bollinger_band_position > 0.6959"                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |   ],                                                                                                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |   "hold_time_min": 3,                                                                                                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |   "hold_time_max": 40,                                                                                                                                                                                                                                                                                                                                                                    ... [TRUNCATED]
                    |   "cooldown_bars": 5,                                                                                                                                                                                                                                                                                                                                                                     ... [TRUNCATED]
                    |   "valid_regimes": [                                                                                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |     "oversold",                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    |     "ranging",                                                                                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |     "normal_vol"                                                                                                                                                                                                                                                                                                                                                                          ... [TRUNCATED]
                    |   ],                                                                                                                                                                                                                                                                                                                                                                                      ... [TRUNCATED]
                    |   "sharpe": 0,                                                                                                                                                                                                                                                                                                                                                                            ... [TRUNCATED]
                    |   "entry_count": 5                                                                                                                                                                                                                                                                                                                                                                        ... [TRUNCATED]
                    | }                                                                                                                                                                                                                                                                                                                                                                                         ... [TRUNCATED]
                    |                                                                                                                                                                                                                                                                                                                                                                                           ... [TRUNCATED]
                    | Mutate conservatively. Output valid JSON: strategy_name, entry_conditions, exit_conditions, mutation_type, changed_fields, hold_time_min, hold_time_max, cooldown_bars, valid_regimes (include economic params if relevant).
raw_response        | {"strategy_name": "mean_reversion_equity_det_170411_96_mut1", "entry_conditions": ["bollinger_band_position < 0.2200", "price_vs_vwap_pct < -0.0027", "rsi_14 < 38.0"], "exit_conditions": ["bollinger_band_position > 0.6959"], "hold_time_min": 3, "hold_time_max": 40, "cooldown_bars": 5, "valid_regimes": ["oversold", "ranging", "normal_vol"], "changed_fields": {"entry_conditions... [TRUNCATED]
normalized_strategy | {"name": "mean_reversion_equity_det_170411_96_mut1", "cooldown_bars": 5, "hold_time_max": 40, "hold_time_min": 3, "valid_regimes": ["oversold", "ranging", "normal_vol"], "changed_fields": {"entry_conditions[0]": "bollinger_band_position threshold relaxed from 0.1668 to 0.2200", "entry_conditions[2]": "rsi_14 threshold relaxed from 32.1851 to 38.0"}, "exit_conditions": ["bolli... [TRUNCATED]
compile_error       |
strategy_signature  |
validation_metrics  |
train_sharpe        |
test_sharpe         |
holdout_sharpe      |
stability_score     |
overfit_flag        |
regime_score        |
trace_id            | b6dd632de4bd4861
generation_batch    |
mutation_type       |
lifecycle_state     | emerging
age_bars            | 0


```

---

## 108. `strategy_lineage`

- **Row count:** 0
- **Columns (8):**
  - `id (uuid)`
  - `parent_id (uuid)`
  - `child_id (uuid)`
  - `source_type (text)`
  - `mutation_type (text)`
  - `performance_delta (numeric)`
  - `metadata (jsonb)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 109. `strategy_regime_performance`

- **Row count:** 0
- **Columns (12):**
  - `id (integer)`
  - `strategy_id (uuid)`
  - `regime (character varying)`
  - `sharpe (double precision)`
  - `cagr (double precision)`
  - `max_drawdown (double precision)`
  - `win_rate (double precision)`
  - `profit_factor (double precision)`
  - `total_trades (integer)`
  - `composite_score (double precision)`
  - `survivability_score (double precision)`
  - `created_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 110. `strategy_retirement`

- **Row count:** 499
- **Columns (11):**
  - `id (uuid)`
  - `analyzed_at (timestamp with time zone)`
  - `n_strategies_analyzed (integer)`
  - `n_active (integer)`
  - `n_monitor (integer)`
  - `n_retirement_pending (integer)`
  - `n_retired (integer)`
  - `lifecycle_states (jsonb)`
  - `retirement_recommendations (jsonb)`
  - `capital_withdrawal_signals (jsonb)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]--------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                         | 8fc42dea-8021-45d6-97dd-ffd2f5292700
analyzed_at                | 2026-05-22 07:13:24.213293+00
n_strategies_analyzed      | 100
n_active                   | 100
n_monitor                  | 0
n_retirement_pending       | 0
n_retired                  | 0
lifecycle_states           | {"000aa349-7efa-4865-aacb-97ed55a36d21": {"state": "active", "reason": "normal_performance", "severity": "none", "avg_score": 30.1, "peak_score": 30.1, "recent_score": 30.1, "divergence_pct": 0.0, "score_degradation_pct": 0.0, "overfit_relapse_detected": false, "degradation_persistence_count": 0}, "005ec4eb-1d17-4c18-abc4-75ede2e7cbe9": {"state": "active", "reason": "n... [TRUNCATED]
retirement_recommendations | []
capital_withdrawal_signals | []
metadata                   | {"method": "score_divergence_and_persistence"}
-[ RECORD 2 ]--------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------... [TRUNCATED]
id                         | 832c2e1d-c268-4cce-8dc2-9464376c4cda
analyzed_at                | 2026-05-22 07:21:38.925373+00
n_strategies_analyzed      | 100
n_active                   | 100
n_monitor                  | 0
n_retirement_pending       | 0
n_retired                  | 0
lifecycle_states           | {"000aa349-7efa-4865-aacb-97ed55a36d21": {"state": "active", "reason": "normal_performance", "severity": "none", "avg_score": 30.1, "peak_score": 30.1, "recent_score": 30.1, "divergence_pct": 0.0, "score_degradation_pct": 0.0, "overfit_relapse_detected": false, "degradation_persistence_count": 0}, "005ec4eb-1d17-4c18-abc4-75ede2e7cbe9": {"state": "active", "reason": "n... [TRUNCATED]
retirement_recommendations | []
capital_withdrawal_signals | []
metadata                   | {"method": "score_divergence_and_persistence"}


```

---

## 111. `stress_test_results`

- **Row count:** 0
- **Columns (9):**
  - `id (text)`
  - `tested_at (timestamp with time zone)`
  - `n_scenarios (integer)`
  - `n_positions (integer)`
  - `worst_scenario (text)`
  - `min_survival_probability (numeric)`
  - `max_drawdown (numeric)`
  - `avg_recovery_days (numeric)`
  - `scenario_results (jsonb)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 112. `system_health`

- **Row count:** 309
- **Columns (8):**
  - `id (text)`
  - `checked_at (timestamp with time zone)`
  - `composite_score (numeric)`
  - `system_mode (text)`
  - `subsystem_scores (jsonb)`
  - `degraded_subsystems (jsonb)`
  - `n_degraded (integer)`
  - `n_total (integer)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id                  | dde9aa8bcaac423c
checked_at          | 2026-05-22 07:13:24.37598+00
composite_score     | 42
system_mode         | degraded
subsystem_scores    | {"api": 100.0, "audit": 100.0, "drift": 100.0, "replay": 100.0, "scouts": 0, "backtest": 0, "ideation": 100.0, "dashboard": 100.0, "execution": 0, "ingestion": 0.0, "portfolio": 0, "validation": 0}
degraded_subsystems | ["ingestion", "backtest", "validation", "portfolio", "execution", "scouts"]
n_degraded          | 6
n_total             | 12
-[ RECORD 2 ]-------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
id                  | dab2b77d24cb49ec
checked_at          | 2026-05-22 07:21:39.065272+00
composite_score     | 46.9463999999999970214048516936600208282470703125
system_mode         | degraded
subsystem_scores    | {"api": 100.0, "audit": 100.0, "drift": 99.33, "replay": 100.0, "scouts": 0, "backtest": 0, "ideation": 100.0, "dashboard": 100.0, "execution": 0, "ingestion": 0.0, "portfolio": 50, "validation": 0}
degraded_subsystems | ["ingestion", "backtest", "validation", "execution", "scouts"]
n_degraded          | 5
n_total             | 12


```

---

## 113. `system_logs`

- **Row count:** 1469
- **Columns (5):**
  - `time (timestamp with time zone)`
  - `agent_id (text)`
  - `level (text)`
  - `message (text)`
  - `metadata (jsonb)`

**Sample rows (LIMIT 2):**

```
-[ RECORD 1 ]-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
time     | 2026-05-25 08:23:34.692693+00
agent_id | ValidatorAgent
level    | INFO
message  | Validation metrics for f69702f6-03d3-45da-9148-a9351dfd1920
metadata | {"tier": "validated", "test_sharpe": 0.0, "overfit_flag": false, "regime_score": 1.0, "train_sharpe": 0.0, "pass_rate_pct": null, "holdout_sharpe": 0.0, "composite_score": 44.6, "stability_score": 0.5, "friction_burden_pct": 0.0, "cost_efficiency_score": 0.0, "cost_governance_status": "PASS", "cost_profile_classification": "undefined", "expected_edge_per_trade_bps": -9.7}
-[ RECORD 2 ]-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
time     | 2026-05-25 08:23:34.759302+00
agent_id | ValidatorAgent
level    | INFO
message  | Validation metrics for 2f9279e8-bfb5-465e-96ba-afbbf940353f
metadata | {"tier": "validated", "test_sharpe": 0.0, "overfit_flag": false, "regime_score": 0.5, "train_sharpe": 0.0, "pass_rate_pct": null, "holdout_sharpe": 0.0, "composite_score": 35.8, "stability_score": 0.5, "friction_burden_pct": 0.0, "cost_efficiency_score": 0.0, "cost_governance_status": "PASS", "cost_profile_classification": "undefined", "expected_edge_per_trade_bps": -11.6}


```

---

## 114. `systemic_risk`

- **Row count:** 0
- **Columns (9):**
  - `id (text)`
  - `assessed_at (timestamp with time zone)`
  - `systemic_risk_score (numeric)`
  - `contagion_probability (numeric)`
  - `portfolio_fragility (numeric)`
  - `correlation_regime (numeric)`
  - `concentration_risk (numeric)`
  - `n_strategies_analyzed (integer)`
  - `details (jsonb)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---

## 115. `walk_forward_analysis`

- **Row count:** 0
- **Columns (9):**
  - `id (uuid)`
  - `strategy_id (uuid)`
  - `walk_forward_score (numeric)`
  - `temporal_consistency (numeric)`
  - `regime_survival_score (numeric)`
  - `n_windows_survived (integer)`
  - `n_windows_total (integer)`
  - `per_window_metrics (jsonb)`
  - `analyzed_at (timestamp with time zone)`

**Sample rows (LIMIT 2):**

```
(no data)
```

---


*End of dump — 115 tables total*
