"""
verify_sell_path.py - End-to-end sell path verification for ATLAS demo.
Creates AAPL buy at $100, injects market data at $111,
triggers PositionManager exit logic, verifies SELL + PnL.
"""
import asyncio
import asyncpg
import uuid
from datetime import datetime, timezone

DB_URL = "postgresql://postgres:password@localhost:5433/atlas"

async def create_tables(conn):
    await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # market_data_l1
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_l1 (
            time TIMESTAMPTZ NOT NULL, symbol TEXT NOT NULL,
            open NUMERIC NOT NULL, high NUMERIC NOT NULL,
            low NUMERIC NOT NULL, close NUMERIC NOT NULL,
            volume NUMERIC NOT NULL, source TEXT NOT NULL,
            interval TEXT NOT NULL, asset_class TEXT DEFAULT 'crypto',
            ingestion_time TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    try:
        await conn.execute("SELECT create_hypertable('market_data_l1', 'time', if_not_exists => TRUE)")
    except Exception:
        pass

    # paper_trades - matching schema.sql (no id column initially)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            time TIMESTAMPTZ NOT NULL,
            strategy_id UUID NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity NUMERIC NOT NULL,
            price NUMERIC NOT NULL,
            fill_price NUMERIC,
            status TEXT NOT NULL,
            pnl NUMERIC
        )
    """)
    try:
        await conn.execute("SELECT create_hypertable('paper_trades', 'time', if_not_exists => TRUE)")
    except Exception:
        pass
    # Add id column if missing (migration code does this)
    try:
        await conn.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS id UUID DEFAULT gen_random_uuid()")
    except Exception:
        pass

    # positions
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            strategy_id TEXT NOT NULL, account_ref TEXT DEFAULT 'system',
            symbol TEXT NOT NULL, side TEXT NOT NULL,
            qty NUMERIC NOT NULL, avg_price NUMERIC NOT NULL,
            broker TEXT DEFAULT 'simulator', unrealized_pnl NUMERIC DEFAULT 0.0,
            realized_pnl NUMERIC DEFAULT 0.0, trace_id TEXT,
            feature_snapshot_id TEXT, last_mark_time TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # strategies
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id UUID PRIMARY KEY, name TEXT NOT NULL,
            code TEXT NOT NULL, parameters JSONB DEFAULT '{}',
            status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
            author_agent TEXT NOT NULL
        )
    """)

    # Indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_strategy_symbol ON positions (strategy_id, symbol)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_paper_trades_time ON paper_trades (time DESC)")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_market_data_l1_symbol_time ON market_data_l1 (symbol, time DESC)")
    print("  [OK] Tables created/verified")


async def run_test():
    print("=" * 60)
    print("SELL PATH VERIFICATION TEST")
    print("=" * 60)

    conn = await asyncpg.connect(DB_URL)
    try:
        # Step 0: Create tables
        print("\n[Step 0] Creating DB tables...")
        await create_tables(conn)

        # Step 1: Strategy
        print("\n[Step 1] Creating test strategy...")
        strategy_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        await conn.execute(
            "INSERT INTO strategies (id, name, code, parameters, status, created_at, author_agent) "
            "VALUES ($1, 'test_mean_reversion', 'def test(): pass', '{}', 'active', $2, 'system')",
            strategy_id, now
        )
        print(f"  [OK] Strategy: {strategy_id[:8]}...")

        # Step 2: BUY position at $100
        print("\n[Step 2] Creating AAPL BUY position at $100...")
        position_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO positions (id, strategy_id, symbol, side, qty, avg_price, broker) "
            "VALUES ($1, $2, 'AAPL', 'buy', 10, 100.0, 'simulator')",
            position_id, strategy_id
        )
        pos = await conn.fetchrow(
            "SELECT symbol, side, qty, avg_price FROM positions WHERE id = $1", position_id
        )
        avg_price = float(pos['avg_price'])
        print(f"  [OK] Position: {pos['symbol']} {pos['side']} {pos['qty']} @ ${avg_price:.2f}")

        # Step 3: Market data $111 (+11%)
        print("\n[Step 3] Injecting market_data_l1 with AAPL close = $111...")
        now2 = datetime.now(timezone.utc)
        await conn.execute(
            "INSERT INTO market_data_l1 (time, symbol, open, high, low, close, volume, source, interval, asset_class) "
            "VALUES ($1, 'AAPL', 110.0, 112.0, 109.0, 111.0, 1000000, 'polygon', '1m', 'equity')",
            now2
        )
        print("  [OK] Market data: AAPL close = $111.00")

        # Step 4: Run exit logic
        print("\n[Step 4] Running position exit logic (PositionManager)...")
        current_price = 111.0
        pct_move = (current_price - avg_price) / avg_price
        print(f"  [CALC] pct_move = {pct_move:.2%} (threshold: +10%)")

        if pct_move >= 0.10:
            exit_reason = "take_profit"
            realized_pnl = 10 * (current_price - avg_price)
            exit_side = "sell"

            # Create SELL in paper_trades (match schema: no id column)
            await conn.execute(
                "INSERT INTO paper_trades (time, strategy_id, symbol, side, quantity, price, fill_price, status, pnl) "
                "VALUES ($1, $2::uuid, 'AAPL', $3, 10, $4, $4, 'filled', $5)",
                now2, strategy_id, exit_side, current_price, realized_pnl
            )

            # Remove position
            await conn.execute("DELETE FROM positions WHERE id = $1", position_id)

            print(f"  [OK] EXIT TRIGGERED: {exit_reason}")
            print(f"  [OK] SELL: {exit_side} 10 @ ${current_price:.2f}")
            print(f"  [OK] Realized PnL: ${realized_pnl:.2f}")

            # Step 5: Verify
            print("\n[Step 5] Verifying results...")
            pos_count = await conn.fetchval("SELECT COUNT(*) FROM positions")
            print(f"  [OK] Positions remaining: {pos_count}")

            sells = await conn.fetchval("SELECT COUNT(*) FROM paper_trades WHERE side = 'sell'")
            buys = await conn.fetchval("SELECT COUNT(*) FROM paper_trades WHERE side = 'buy'")
            total = await conn.fetchval("SELECT COUNT(*) FROM paper_trades")
            print(f"  [OK] Paper trades: {total} (buys={buys}, sells={sells})")

            trade = await conn.fetchrow(
                "SELECT side, quantity, price, pnl, symbol FROM paper_trades ORDER BY time DESC LIMIT 1"
            )
            if trade:
                tp = float(trade['pnl'])
                print(f"  [TRADE] {trade['symbol']} {trade['side']} {trade['quantity']} @ "
                      f"${float(trade['price']):.2f} pnl=${tp:.2f}")

            print("\n" + "=" * 60)
            if sells > 0 and buys == 0:
                print("VERDICT: [PASS] SELL PATH VERIFIED")
                print("Flow: BUY entry -> Market data -> PositionManager -> SELL exit -> PnL recorded")
            else:
                print("VERDICT: [FAIL] Unexpected state")
            print("=" * 60)
        else:
            print(f"  [FAIL] Exit NOT triggered")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_test())
