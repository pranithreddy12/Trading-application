# ATLAS Repository Cleanup Audit Report

**Generated:** June 1, 2026
**Scope:** Full repository scan for non-runtime artifacts
**Rules Applied:** No runtime code deleted; no files imported by active runtime paths touched

---

## Summary

| Category | Count | Est. Size |
|----------|-------|-----------|
| **SAFE_DELETE** | ~80 files + 26 `__pycache__` dirs | ~50 MB |
| **ARCHIVE_ONLY** | ~25 files | ~5 MB |
| **REVIEW_MANUALLY** | ~10 files | ~2 MB |

---

## SAFE_DELETE — Guaranteed Non-Runtime Files

These files are **not imported** by any runtime code path (`atlas/agents`, `atlas/core`, `atlas/data`, `atlas/api`, `atlas/dashboard`, `atlas/config`, `atlas/governance`). No entrypoints reference them. No tests depend on them.

### Category 1: `__pycache__` Directories (26 dirs)

All `__pycache__` directories are Python bytecode caches and safe to remove.

```
atlas/__pycache__/
atlas/agents/__pycache__/
atlas/agents/l1_data/__pycache__/
atlas/agents/l1_pattern/__pycache__/
atlas/agents/l2_strategy/__pycache__/
atlas/agents/l3_backtest/__pycache__/
atlas/agents/l3_validation/__pycache__/
atlas/agents/l4_risk/__pycache__/
atlas/agents/l5_execution/__pycache__/
atlas/agents/l6_portfolio/__pycache__/
atlas/agents/l7_meta/__pycache__/
atlas/agents/scouts/__pycache__/
atlas/api/__pycache__/
atlas/api/services/__pycache__/
atlas/config/__pycache__/
atlas/core/__pycache__/
atlas/core/scout_contracts/__pycache__/
atlas/dashboard/__pycache__/
atlas/dashboard/control_plane/__pycache__/
atlas/dashboard/system_visualization/__pycache__/
atlas/data/__pycache__/
atlas/data/ingestion/__pycache__/
atlas/data/storage/__pycache__/
atlas/governance/__pycache__/
atlas/scripts/__pycache__/
atlas/scripts/soak/__pycache__/
```

**Command:**
```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

### Category 2: Log Files (40+ files)

All log files are generated output from pipeline runs and soak tests.

**Root-level logs:**
```
pipeline_output.log
soak_clean_output.log
soak_clean_v2_output.log
soak_final_output.log
soak_output.log
```

**atlas/ logs:**
```
atlas/api_server.log
atlas/gen_output.log
atlas/soak.log
atlas/soak_6h.log
atlas/soak_90min_output.log
atlas/soak_output.log
atlas/phase25_soak_pipeline.log
atlas/phase26_ab_a_scouts_off.log
atlas/phase26_ab_b_scouts_on.log
atlas/phase26_soak_pipeline.log
atlas/phase27_soak_output.log
atlas/phase28_soak.log
atlas/phase29_soak_console.log
atlas/phase30_soak.log
atlas/pipeline_phase30_6h.log
atlas/scripts/day5/validation.log
atlas/scripts/phase25_soak_pipeline.log
```

**logs/ directory (entire directory):**
```
logs/api_server.log
logs/api_server_port8001.log
logs/api_server_port8002.log
logs/autonomous_cycle_20260530_130836.log
logs/autonomous_cycle_2026-05-30_130929.log
logs/autonomous_cycle_2026-05-30_193205.log
logs/autonomous_cycle_2026-05-30_193302.log
logs/autonomous_cycle_2026-05-30_193321.log
logs/autonomous_cycle_2026-06-01_101445.log
logs/autonomous_cycle_2026-06-01_114411.log
logs/cycle_20260530_193319.log
logs/cycle_30min_20260530_193201.log
logs/cycle_30min_20260530_193300.log
logs/run_10min.log
logs/run_5min_scouts.log
```

**scripts/logs/ (entire directory):**
```
scripts/logs/phase37_soak_30m.log
scripts/logs/phase37_soak_full.log
scripts/logs/phase38_strict_soak_30m.log
```

**Command:**
```bash
rm -f pipeline_output.log soak_clean_output.log soak_clean_v2_output.log soak_final_output.log soak_output.log
rm -f atlas/api_server.log atlas/gen_output.log atlas/soak.log atlas/soak_6h.log atlas/soak_90min_output.log atlas/soak_output.log
rm -f atlas/phase25_soak_pipeline.log atlas/phase26_ab_a_scouts_off.log atlas/phase26_ab_b_scouts_on.log
rm -f atlas/phase26_soak_pipeline.log atlas/phase27_soak_output.log atlas/phase28_soak.log
rm -f atlas/phase29_soak_console.log atlas/phase30_soak.log atlas/pipeline_phase30_6h.log
rm -f atlas/scripts/day5/validation.log atlas/scripts/phase25_soak_pipeline.log
rm -rf logs/
rm -rf scripts/logs/
```

### Category 3: PID Files (4 files)

```
logs/dashboard.pid
logs/pipeline.pid
atlas/phase30_soak_pid.txt
atlas/pipeline_pid.txt
```

**Command:**
```bash
rm -f logs/dashboard.pid logs/pipeline.pid atlas/phase30_soak_pid.txt atlas/pipeline_pid.txt
```

### Category 4: Root-Level Debug/Utility Scripts (7 files)

These are standalone scripts not imported by any runtime path:

```
dt.py                              # Standalone debug utility (Anthropic API test)
test_coder.py                      # Standalone test (not in test suite)
test_copy_execution.py             # Standalone test (not in test suite)
test_copy_smoke.py                 # Standalone test (not in test suite)
test_copy_trade.py                 # Standalone test (not in test suite)
test_db_signals.py                 # Standalone test (not in test suite)
test_inject_strategy.py            # Standalone test (not in test suite)
test_risk_and_idempotency.py       # Standalone test (not in test suite)
```

**Note:** Root-level test files differ from `atlas/tests/` (the actual test suite). These are ad-hoc verification scripts.

### Category 4b: Runtime-Directory Debug Files (2 files)

```
atlas/agents/l2_strategy/test_fix.py   # Debug script inside runtime agents dir
atlas/nul                               # Windows artifact (empty device file)
```

**Command:**
```bash
rm -f dt.py test_coder.py test_copy_execution.py test_copy_smoke.py test_copy_trade.py test_db_signals.py test_inject_strategy.py test_risk_and_idempotency.py
rm -f atlas/agents/l2_strategy/test_fix.py atlas/nul
```

### Category 5: Generated Documentation/Reports (5 files)

```
ATLAS_Integrated_Masterpiece.docx
ATLAS_Integrated_Masterpiece.txt
ATLAS_Integrated_Masterpiece_Full.txt
demo.txt
atlas/ATLAS_Integrated_Masterpiece.docx    # Same generated doc, atlas/ copy
```

These are generated deliverable documents, not referenced by runtime code.

**Command:**
```bash
rm -f ATLAS_Integrated_Masterpiece.docx ATLAS_Integrated_Masterpiece.txt ATLAS_Integrated_Masterpiece_Full.txt demo.txt atlas/ATLAS_Integrated_Masterpiece.docx
```

### Category 6: Debug Scripts in atlas/scripts/ (3 files)

```
atlas/scripts/debug_hash.py
atlas/scripts/debug_hash2.py
atlas/scripts/debug_hash3.py
```

Debug scripts used during development, not imported by runtime.

**Command:**
```bash
rm -f atlas/scripts/debug_hash.py atlas/scripts/debug_hash2.py atlas/scripts/debug_hash3.py
```

### Category 7: Backup File and Memory (2 files)

```
.gemini/settings.json.bak
atlas/memory.md                      # Generated memory file, not runtime
```

**Command:**
```bash
rm -f .gemini/settings.json.bak atlas/memory.md
```

### Category 8: Generated JSONL Output (2 files)

```
scripts/monitor_output.jsonl
scripts/monitor_real_output.jsonl
```

Not referenced by runtime code.

**Command:**
```bash
rm -f scripts/monitor_output.jsonl scripts/monitor_real_output.jsonl
```

---

## ARCHIVE_ONLY — Move to `archive/`

These files are **generated outputs** that scripts produce and reference. They should be moved to `archive/` rather than deleted, as some scripts may re-generate or reference them.

### Soak/Analysis Results (referenced by scripts for report generation)

```
atlas/phase25_soak_results.json            # Referenced by atlas/scripts/phase25_1h_soak.py
atlas/phase26_ab_test_results.json         # Referenced by atlas/scripts/soak/ab_test_scout_coupling.py
atlas/post_soak_analysis_results.json      # Referenced by atlas/scripts/post_soak_analysis.py
post_soak_analysis_results.json            # Root-level duplicate
atlas/scripts/phase25_soak_results.json    # Duplicate of atlas/ version
```

### Generated Governance Reports (produced by scripts, not runtime)

```
atlas/governance/governance_analytics_4a4d0fdf04214ccd90559123d22c15da.json
atlas/governance/governance_analytics_7f7bd9f93b0640a99791dab11187d41a.json
atlas/governance/governance_analytics_c742339145c749a6832c00c59c42fcae.json
atlas/governance/governance_audit_report_4a4d0fdf04214ccd90559123d22c15da.json
```

### Validation Outputs (produced by scripts, referenced by scripts)

```
atlas/scripts/day5/validation_output.json
scripts/day5/live_validation_output.json
```

### Root-Level Duplicated Phase Reports (already in `docs/reports/`)

```
docs/PHASE33_ADAPTIVE_INTELLIGENCE_REPORT.md      # Also in docs/reports/
docs/PHASE33_ECONOMIC_PERFORMANCE_REPORT.md        # Also in docs/reports/
docs/PHASE33_EVOLUTIONARY_PERFORMANCE_REPORT.md    # Also in docs/reports/
docs/PHASE33_FINAL_BENCHMARK_CERTIFICATION.md      # Also in docs/reports/
docs/PHASE33_PORTFOLIO_SURVIVABILITY_REPORT.md     # Also in docs/reports/
docs/PHASE33_REGIME_STRESS_REPORT.md               # Also in docs/reports/
docs/PHASE33_RUNTIME_STABILITY_REPORT.md           # Also in docs/reports/
docs/PHASE34_DASHBOARD_VISIBILITY_REPORT.md        # Also in docs/reports/
docs/PHASE34_DELIVERY_DOCUMENTATION_REPORT.md      # Also in docs/reports/
docs/PHASE34_END_TO_END_FLOW_REPORT.md             # Also in docs/reports/
docs/PHASE34_FINAL_DELIVERY_CERTIFICATION.md       # Also in docs/reports/
docs/PHASE34_REPO_CLEANUP_REPORT.md                # Also in docs/reports/
docs/PHASE34_SYSTEM_COVERAGE_REPORT.md             # Also in docs/reports/
```

### Root-Level Phase Reports (not in docs/reports/)

```
PHASE35_PAPER_TRADING_REPORT.md
PHASE36_ADVANCED_VALIDATION_REPORT.md
PHASE36_EXECUTION_ACTIVATION_REPORT.md
PHASE36_EXECUTION_REALISM_REPORT.md
PHASE36_FULL_ECOSYSTEM_CERTIFICATION.md
PHASE36_OBSERVABILITY_REPORT.md
PHASE36_SCOUT_ECOSYSTEM_REPORT.md
PHASE36_SPECIALIZATION_REPORT.md
PHASE37_ADAPTIVE_CAPITAL_FLOW_REPORT.md
PHASE37_CAPITAL_MIGRATION_REPORT.md
PHASE37_LONG_HORIZON_CERTIFICATION.md
PHASE37_MUTATION_DOMINANCE_REPORT.md
PHASE37_MUTATION_RESPONSE_REPORT.md
PHASE37_REGIME_PERTURBATION_REPORT.md
PHASE37_SCOUT_DIVERGENCE_REPORT.md
PHASE37_SCOUT_INTELLIGENCE_REPORT.md
PHASE37_SHORT_INTELLIGENCE_CERTIFICATION.md
PHASE37_SHORT_REGIME_ANALYSIS.md
PHASE37_SPECIALIZATION_EVOLUTION_REPORT.md
PHASE37_SURVIVAL_QUALITY_REPORT.md
POST_SOAK_ANALYSIS_REPORT.md
ATLAS_FINAL_DELIVERY_CERTIFICATION.md
ATLAS_FINAL_EXECUTION_CERTIFICATION.md
ATLAS_FINAL_FAILURE_LEDGER.md
ATLAS_FINAL_OPERATIONAL_SCORECARD.md
ATLAS_FINAL_PORTFOLIO_CERTIFICATION.md
ATLAS_FINAL_REPLAY_CERTIFICATION.md
ATLAS_FINAL_SCOUT_CERTIFICATION.md
ATLAS_OPERATIONAL_VALIDATION_REPORT.md
ATLAS_Pipeline_Demo_Guide_For_Shakir.md
ATLAS_DATABASE_SAMPLE_DATA.md
PHASE33_*.md (root-level copies)
PHASE34_*.md (root-level copies)
```

### Duplicate/atlas/ Requirements

```
atlas/requirements.txt    # Duplicate of root pyproject.toml dependencies
```

### Generated Docx (atlas/ copy)

```
atlas/ATLAS_Integrated_Masterpiece.docx
```

**Command for archive:**
```bash
mkdir -p archive/soak_results archive/governance_reports archive/phase_reports archive/validation

# Soak results
mv atlas/phase25_soak_results.json archive/soak_results/
mv atlas/phase26_ab_test_results.json archive/soak_results/
mv atlas/post_soak_analysis_results.json archive/soak_results/
mv post_soak_analysis_results.json archive/soak_results/
mv atlas/scripts/phase25_soak_results.json archive/soak_results/

# Governance reports
mv atlas/governance/governance_analytics_*.json archive/governance_reports/
mv atlas/governance/governance_audit_report_*.json archive/governance_reports/

# Validation outputs
mv atlas/scripts/day5/validation_output.json archive/validation/
mv scripts/day5/live_validation_output.json archive/validation/

# Root-level phase reports
mv PHASE3*.md archive/phase_reports/ 2>/dev/null
mv PHASE36_*.md archive/phase_reports/ 2>/dev/null
mv PHASE37_*.md archive/phase_reports/ 2>/dev/null
mv POST_SOAK_ANALYSIS_REPORT.md archive/phase_reports/ 2>/dev/null
mv ATLAS_FINAL_*.md archive/phase_reports/ 2>/dev/null
mv ATLAS_OPERATIONAL_*.md archive/phase_reports/ 2>/dev/null
mv ATLAS_Pipeline_Demo_Guide_For_Shakir.md archive/phase_reports/ 2>/dev/null
mv ATLAS_DATABASE_SAMPLE_DATA.md archive/phase_reports/ 2>/dev/null

# Duplicated docs (already in docs/reports/)
mv docs/PHASE33_*.md archive/phase_reports/ 2>/dev/null
mv docs/PHASE34_*.md archive/phase_reports/ 2>/dev/null

# atlas/ duplicate
mv atlas/ATLAS_Integrated_Masterpiece.docx archive/ 2>/dev/null
mv atlas/requirements.txt archive/ 2>/dev/null
```

---

## REVIEW_MANUALLY — Requires Dependency Verification

These files **are referenced** by runtime code or may have implicit dependencies.

### SQLite Databases (Runtime Artifacts)

| File | Referenced By | Verdict |
|------|---------------|---------|
| `atlas/governance/governance.db` | `atlas/governance/persistence.py` (line 29) | **KEEP** — Active runtime artifact |
| `atlas/atlas.db` | Unknown — may be obsolete SQLite fallback | **REVIEW** — Check if used |
| `atlas/data/atlas.db` | Unknown — may be obsolete SQLite fallback | **REVIEW** — Check if used |
| `.code-review-graph/graph.db` | MCP code-review-graph tool | **KEEP** — Tool artifact |

### Runtime-Generated Logs (Written by Running System)

| File | Referenced By | Verdict |
|------|---------------|---------|
| `atlas/governance/identity_violation_journal.log` | `atlas/governance/analytics.py`, `atlas/governance/journal.py` | **KEEP** — Active runtime artifact |

### Standalone Utility Scripts (Validate/Verify)

| File | Purpose | Verdict |
|------|---------|---------|
| `verify_setup.py` | System verification (documented in README) | **KEEP** — User-facing validation |
| `verify_migration.py` | Migration verification (documented in README) | **KEEP** — User-facing validation |
| `final_smoke_test_verification.py` | Final verification script | **KEEP** — User-facing validation |
| `apply_leader_orders_migration.py` | One-off migration script | **REVIEW** — May be obsolete |
| `reinsert_test_data.py` | Test data insertion | **REVIEW** — May be obsolete |
| `conftest.py` | Pytest configuration | **KEEP** — Required by test suite |

### SQL Migration Files (Historical)

| File | Purpose | Verdict |
|------|---------|---------|
| `scripts/migrations/database_audit_diagnostics.sql` | Audit queries | **KEEP** — Diagnostic tool |
| `scripts/migrations/day4_copy_schema.sql` | Day 4 schema | **REVIEW** — May be superseded |
| `scripts/migrations/day5_auth_schema.sql` | Day 5 auth schema | **REVIEW** — May be superseded |
| `scripts/migrations/phase1_schema_hardening.sql` | Phase 1 hardening | **REVIEW** — May be superseded |
| `scripts/migrations/phase2_enum_and_indexes.sql` | Phase 2 indexes | **REVIEW** — May be superseded |
| `scripts/migrations/phase38_deployment_mode.sql` | Phase 38 deployment | **KEEP** — Recent migration |

---

## Quick Delete Command (SAFE_DELETE only)

```bash
# Remove __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Remove log files
rm -f pipeline_output.log soak_clean_output.log soak_clean_v2_output.log soak_final_output.log soak_output.log
rm -f atlas/api_server.log atlas/gen_output.log atlas/soak.log atlas/soak_6h.log atlas/soak_90min_output.log atlas/soak_output.log
rm -f atlas/phase25_soak_pipeline.log atlas/phase26_ab_a_scouts_off.log atlas/phase26_ab_b_scouts_on.log
rm -f atlas/phase26_soak_pipeline.log atlas/phase27_soak_output.log atlas/phase28_soak.log
rm -f atlas/phase29_soak_console.log atlas/phase30_soak.log atlas/pipeline_phase30_6h.log
rm -f atlas/scripts/day5/validation.log atlas/scripts/phase25_soak_pipeline.log
rm -rf logs/ scripts/logs/

# Remove PID files
rm -f logs/dashboard.pid logs/pipeline.pid atlas/phase30_soak_pid.txt atlas/pipeline_pid.txt

# Remove debug scripts
rm -f dt.py test_coder.py test_copy_execution.py test_copy_smoke.py test_copy_trade.py test_db_signals.py test_inject_strategy.py test_risk_and_idempotency.py
rm -f atlas/scripts/debug_hash.py atlas/scripts/debug_hash2.py atlas/scripts/debug_hash3.py

# Remove generated docs
rm -f ATLAS_Integrated_Masterpiece.docx ATLAS_Integrated_Masterpiece.txt ATLAS_Integrated_Masterpiece_Full.txt demo.txt

# Remove backup files
rm -f .gemini/settings.json.bak

# Remove JSONL outputs
rm -f scripts/monitor_output.jsonl scripts/monitor_real_output.jsonl
```

---

## Verification

After running cleanup:

```bash
# Verify no broken imports
python -c "import atlas; print('OK')"

# Verify test suite still passes
pytest atlas/tests/ -v --tb=short

# Verify API starts
uvicorn atlas.api.main:app --host 0.0.0.0 --port 8000
```
