-- ============================================================
-- ATLAS DATABASE MIGRATION — Phase 38: Deployment Mode
-- ============================================================
-- Adds deployment_mode column to strategies table to track
-- paper trading promotion status (used by DeploymentGovernor).
-- ============================================================

BEGIN;

-- Add deployment_mode column to strategies (idempotent)
ALTER TABLE strategies
  ADD COLUMN IF NOT EXISTS deployment_mode TEXT
  DEFAULT NULL;

-- Add index for deployment queries
CREATE INDEX IF NOT EXISTS idx_strategies_deployment_mode
  ON strategies (deployment_mode)
  WHERE deployment_mode IS NOT NULL;

COMMIT;
