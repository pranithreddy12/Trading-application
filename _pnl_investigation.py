"""Investigate PnL discrepancies — compare stored vs calculated PnL for all paper trades."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB_URL = "postgresql+asyncpg://postgres:password@localhost:5433/atlas"

async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        # 1. Schema
        r = await conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'paper_trades' ORDER BY ordinal_position"
        ))
        print("=== paper_trades Schema ===")
        for row in r.fetchall():
            print(f"  {row[0]:<20} {row[1]}")

        # 2. Count by status
        print("\n=== By Status ===")
        r = await conn.execute(text("SELECT status, COUNT(*) FROM paper_trades GROUP BY status"))
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # 3. Check: do we need to distinguish entry (buy) from exit (sell)?
        # A typical PnL cycle: buy (price=entry, pnl=0) then sell (price=exit, pnl=realized)
        print("\n=== Side Distribution ===")
        r = await conn.execute(text("SELECT side, COUNT(*) FROM paper_trades GROUP BY side"))
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # 4. Check for paired trades (buy then sell of same strategy+symbol)
        print("\n=== Looking for entry/exit trade pairs ===")
        r = await conn.execute(text("""
            SELECT strategy_id, symbol, 
                   COUNT(*) FILTER (WHERE side='buy') as buys,
                   COUNT(*) FILTER (WHERE side='sell') as sells,
                   COUNT(*) as total
            FROM paper_trades
            GROUP BY strategy_id, symbol
            HAVING COUNT(*) >= 2
            ORDER BY total DESC
            LIMIT 10
        """))
        for row in r.fetchall():
            print(f"  {str(row[0])[:8]}... | {row[1]:<8} | buys={row[2]} sells={row[3]} total={row[4]}")

        # 5. Analyze a trade pair in detail
        print("\n=== Detailed analysis of a trade pair ===")
        r = await conn.execute(text("""
            SELECT id, strategy_id, symbol, side, quantity, price, fill_price, pnl, time, trace_id
            FROM paper_trades
            WHERE strategy_id = (SELECT strategy_id FROM paper_trades WHERE side='sell' LIMIT 1)
              AND symbol = (SELECT symbol FROM paper_trades WHERE side='sell' LIMIT 1)
            ORDER BY time ASC
            LIMIT 10
        """))
        rows = r.fetchall()
        for row in rows:
            d = dict(row._mapping)
            print(f"  id={str(d['id'])[:8]} sym={d['symbol']} side={str(d['side']):5} "
                  f"qty={d['quantity']:>6} price={float(d['price'] or 0):>8.2f} "
                  f"fill_price={float(d['fill_price'] or 0):>8.2f} "
                  f"pnl={float(d['pnl'] or 0):>8.2f} time={d['time']}")
            if str(d.get('trace_id','')):
                print(f"    trace_id={d['trace_id']}")

        # 6. Comprehensive comparison: compare stored PnL with calculated PnL
        print("\n=== Comprehensive PnL Comparison ===")
        print("(comparing ALL closed/filled trades)")
        r = await conn.execute(text("""
            SELECT id, symbol, side, quantity, price, fill_price, pnl
            FROM paper_trades
            WHERE status IN ('filled', 'closed')
            ORDER BY time DESC
        """))
        rows = r.fetchall()
        print(f"Total trades to analyze: {len(rows)}")

        mismatches = []
        matches = []
        for row in rows:
            d = dict(row._mapping)
            entry = float(d.get('price') or 0)
            exit_ = float(d.get('fill_price') or 0)
            qty = float(d.get('quantity') or 0)
            side = str(d.get('side', 'buy')).lower()
            stored_pnl = float(d.get('pnl') or 0)

            # Expected PnL formula
            if side in ('long', 'buy'):
                expected = (exit_ - entry) * qty
            else:
                expected = (entry - exit_) * qty

            diff = abs(expected - stored_pnl)
            sid_short = str(d.get('id', ''))[:8]

            if diff > 0.01:
                mismatches.append({
                    'id': sid_short,
                    'symbol': d.get('symbol'),
                    'side': side,
                    'qty': qty,
                    'entry': entry,
                    'exit': exit_,
                    'expected': expected,
                    'stored': stored_pnl,
                    'diff': diff,
                    'stored_type': 'zero' if stored_pnl == 0 else ('negative' if stored_pnl < 0 else 'positive'),
                    'expected_type': 'zero' if expected == 0 else ('negative' if expected < 0 else 'positive'),
                })
            else:
                matches.append({
                    'id': sid_short,
                    'symbol': d.get('symbol'),
                    'side': side,
                    'qty': qty,
                    'expected': expected,
                    'stored': stored_pnl,
                })

        print(f"\nMatching trades: {len(matches)}")
        print(f"Mismatched trades: {len(mismatches)}/{len(rows)}")

        # Analyze mismatch patterns
        if mismatches:
            print(f"\n=== Mismatch Pattern Analysis ===")

            # By side
            from collections import Counter
            side_counts = Counter(m['side'] for m in mismatches)
            print(f"\nBy side:")
            for side, count in side_counts.most_common():
                print(f"  {side}: {count}")

            # By stored vs expected type
            type_counts = Counter((m['stored_type'], m['expected_type']) for m in mismatches)
            print(f"\nBy expected vs stored sign:")
            for (st, et), count in type_counts.most_common():
                print(f"  stored={st} expected={et}: {count}")

            # Sample of mismatches with details
            print(f"\nSample mismatches (first 15):")
            for m in mismatches[:15]:
                print(f"  MISMATCH id={m['id']} sym={m['symbol']} side={m['side']} "
                      f"qty={m['qty']} entry={m['entry']:.4f} exit={m['exit']:.4f} "
                      f"expected={m['expected']:.4f} stored={m['stored']:.4f} "
                      f"diff={m['diff']:.4f}")

            # Check for pattern: are PnLs always 0 for certain side or status?
            zero_pnl_mismatches = [m for m in mismatches if m['stored'] == 0]
            non_zero_mismatches = [m for m in mismatches if m['stored'] != 0]

            print(f"\nMismatches where stored PnL = 0: {len(zero_pnl_mismatches)}")
            print(f"Mismatches where stored PnL != 0: {len(non_zero_mismatches)}")

            if zero_pnl_mismatches:
                print(f"\nSample zero-PnL mismatches:")
                for m in zero_pnl_mismatches[:5]:
                    print(f"  id={m['id']} sym={m['symbol']} side={m['side']} "
                          f"qty={m['qty']} entry={m['entry']:.4f} exit={m['exit']:.4f} "
                          f"expected={m['expected']:.4f} stored={0:.4f}")

        # 7. Check if PnL is stored on the *exit* trade but calculated across both legs
        print(f"\n=== Key Question: Is PnL stored on entry (pnl=0) + exit (pnl=realized?)? ===")
        r = await conn.execute(text("""
            SELECT side, 
                   COUNT(*) FILTER (WHERE pnl = 0) as zero_pnl,
                   COUNT(*) FILTER (WHERE pnl != 0) as non_zero_pnl,
                   ROUND(AVG(pnl)::numeric, 4) as avg_pnl
            FROM paper_trades
            WHERE status IN ('filled', 'closed')
            GROUP BY side
        """))
        for row in r.fetchall():
            print(f"  {row[0]}: zero_pnl={row[1]} non_zero_pnl={row[2]} avg_pnl={row[3]}")

        # 8. Check for sell trades where PnL is carried over
        print(f"\n=== Sell trades PnL analysis ===")
        r = await conn.execute(text("""
            SELECT id, strategy_id, symbol, quantity, price, fill_price, pnl, time
            FROM paper_trades
            WHERE side = 'sell' AND status IN ('filled', 'closed')
            ORDER BY time DESC
            LIMIT 20
        """))
        sell_rows = r.fetchall()
        print(f"Total sell trades: {len(sell_rows)} in sample, analyzing...")
        zero_pnl_sells = 0
        for row in sell_rows:
            d = dict(row._mapping)
            spnl = float(d.get('pnl') or 0)
            sid = str(d.get('id', ''))[:8]
            entry = float(d.get('price') or 0)
            exit_ = float(d.get('fill_price') or 0)
            qty = float(d.get('quantity') or 0)
            # For a sell (closing a long), PnL = (exit_price - entry_price) * qty
            # But entry here is actually the SELL price, and fill_price is also the SELL fill
            # The real entry price was the BUY price, stored separately
            if spnl == 0:
                zero_pnl_sells += 1
            print(f"  SELL id={sid} sym={d['symbol']} qty={qty} price={entry:.4f} fill={exit_:.4f} pnl={spnl:.4f}")
        print(f"  Zero-pnl sell trades: {zero_pnl_sells}/{len(sell_rows)}")

        # 9. Check for buy trades with non-zero PnL (these would be wrong)
        print(f"\n=== Buy trades with non-zero PnL (should be 0) ===")
        r = await conn.execute(text("""
            SELECT COUNT(*) FROM paper_trades
            WHERE side = 'buy' AND status = 'filled' AND pnl != 0
        """))
        count = r.scalar() or 0
        print(f"  Buy trades with non-zero PnL: {count}")

    print("\n" + "=" * 60)
    print("PNL INVESTIGATION COMPLETE")
    print("=" * 60)

    with open("logs/pnl_investigation.log", "w") as f:
        f.write(f"Mismatches: {len(mismatches)}/{len(rows)}\n")
        f.write(f"Zero-PnL exits: {zero_pnl_sells} sell trades with pnl=0\n")

    await engine.dispose()

asyncio.run(main())
