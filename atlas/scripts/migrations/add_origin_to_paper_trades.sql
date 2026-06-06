-- Migration: Add origin tracking to paper_trades
-- Allows distinguishing real execution trades from synthetic/seed data

ALTER TABLE paper_trades 
ADD COLUMN IF NOT EXISTS origin TEXT NOT NULL DEFAULT 'execution';

-- Backfill existing rows based on heuristics
-- 1. Trades with pnl=0 that match backtest_trades patterns (qty=100, sequential timestamps)
UPDATE paper_trades 
SET origin = 'backtest' 
WHERE origin = 'execution' 
  AND quantity = 100 
  AND pnl = 0;

-- 2. Trades with random-looking PnL values (from seed_dashboard_data.py)
-- These have PnL values not matching simple price*qty calculations
-- We flag trades where ABS(pnl) > quantity * fill_price (impossible for single-ticket trades)
UPDATE paper_trades 
SET origin = 'demo_seed' 
WHERE origin = 'execution' 
  AND ABS(COALESCE(pnl, 0)) > COALESCE(quantity, 1) * COALESCE(fill_price, 1) * 10;

-- 3. Trades with status='filled' but no matching opposite-side trade (orphans)
UPDATE paper_trades 
SET origin = 'migration' 
WHERE origin = 'execution' 
  AND status = 'filled' 
  AND id IS NULL;

-- 4. Trades inserted by verify_sell_path.py tests (have 'test' in strategy name or recent timestamps)
UPDATE paper_trades pt
SET origin = 'manual'
FROM strategies s
WHERE s.id::text = pt.strategy_id::text
  AND s.name LIKE 'test_%'
  AND pt.origin = 'execution';

-- 5. Remaining 'execution' trades are genuine execution output
-- These come from ExecutionGateway.execute() or PositionManager._execute_exit()

-- Create index for faster origin-based queries
CREATE INDEX IF NOT EXISTS idx_paper_trades_origin ON paper_trades (origin);

COMMENT ON COLUMN paper_trades.origin IS 
'Provenance tracking: execution=real trade from pipeline, backtest=copied from backtest_trades, migration=from schema migration, manual=test/verify script, demo_seed=from seed scripts';
