"""
Combiner Smoke Test — Priority 4
Verifies: temporal-score querying, combination_memory dedup, combination record persistence.
Does NOT call Claude (requires API key) — tests DB portion only.
"""

import asyncio
import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()
    print("=== COMBINER SMOKE TEST ===\n")

    # 1. Query top strategies by temporal score
    print("[TEST 1] get_top_strategies_by_composite_score(0, 100, 5)")
    top = await db.get_top_strategies_by_composite_score(0.0, 100.0, 5)
    assert len(top) >= 2, f"Need at least 2 strategies, got {len(top)}"
    print(f"  Found {len(top)} strategies")
    for s in top:
        print(
            f"    {s['name']:>40}  score={s['short_window_score']:.1f}  status={s['status']}"
        )
    print(f"  PASS\n")

    # 2. Check no existing combination between top 2
    a, b = top[0], top[1]
    print(f"[TEST 2] check_combination_exists({a['name']}, {b['name']})")
    exists = await db.check_combination_exists(a["id"], b["id"])
    print(f"  Exists before save: {exists}")
    assert exists is False, "Fresh pair should not exist in combination_memory"
    print(f"  PASS\n")

    # Create a temporary strategy to use as child_id (FK reference)
    child_id = str(uuid.uuid4())
    import asyncpg

    url = settings.database_url
    parts = url.replace("postgresql+asyncpg://", "").split("/")
    user_pass_host = parts[0].split("@")
    user_pass = user_pass_host[0].split(":")
    host_port = user_pass_host[1].split(":")
    conn = await asyncpg.connect(
        user=user_pass[0],
        password=user_pass[1],
        host=host_port[0],
        port=int(host_port[1]),
        database=parts[1],
    )
    await conn.execute(
        """
        INSERT INTO strategies (id, name, code, parameters, status, created_at, author_agent, normalized_strategy)
        VALUES ($1, 'smoke_test_child', '', $2, 'smoke_test', NOW(), 'combiner_smoke_test', $2)
        ON CONFLICT (id) DO NOTHING
        """,
        child_id,
        json.dumps({"type": "smoke_test_child"}),
    )

    # 3. Save a combination record
    print(f"[TEST 3] save_combination_record({a['name']}, {b['name']})")
    await db.save_combination_record(
        parent_a=a["id"],
        parent_b=b["id"],
        child_id=child_id,
        combination_type="smoke_test",
        parent_a_score=a["short_window_score"],
        parent_b_score=b["short_window_score"],
        child_score=max(a["short_window_score"], b["short_window_score"]) + 5.0,
    )
    print(f"  Saved combination record")
    print(f"  PASS\n")

    # 4. Verify dedup — second attempt should find it
    print(f"[TEST 4] Dedup: check_combination_exists again")
    exists = await db.check_combination_exists(a["id"], b["id"])
    assert exists is True, "Combination should now exist"
    print(f"  Exists after save: {exists}")
    print(f"  PASS\n")

    # 5. Save reversed order (a, b) — should be caught by UNIQUE constraint
    print(f"[TEST 5] Save reversed order — should be caught by ON CONFLICT DO NOTHING")
    await db.save_combination_record(
        parent_a=b["id"],
        parent_b=a["id"],
        child_id=child_id,
        combination_type="smoke_test",
        parent_a_score=b["short_window_score"],
        parent_b_score=a["short_window_score"],
        child_score=max(a["short_window_score"], b["short_window_score"]) + 5.0,
    )
    print(f"  No error — ON CONFLICT DO NOTHING handled duplicate")
    print(f"  PASS\n")

    # 6. Query combination_memory to verify record
    print(f"[TEST 6] Verify combination_memory record")
    row = await conn.fetchrow(
        "SELECT parent_a, parent_b, child_id, combination_type, sharpe_delta FROM combination_memory WHERE child_id = $1",
        child_id,
    )
    assert row is not None, "Combination record should exist"
    print(f"  parent_a:      {row['parent_a']}")
    print(f"  parent_b:      {row['parent_b']}")
    print(f"  child_id:      {row['child_id']}")
    print(f"  type:          {row['combination_type']}")
    print(f"  sharpe_delta:  {row['sharpe_delta']}")
    print(f"  PASS\n")

    # 7. Verify combiner query finds untried pair with dedup
    print(f"[TEST 7] Simulate combiner find-untried-pair logic")
    top10 = await db.get_top_strategies_by_composite_score(0.0, 100.0, 10)
    import itertools

    found = None
    for x, y in itertools.combinations(top10, 2):
        if not await db.check_combination_exists(x["id"], y["id"]):
            found = (x, y)
            break
    assert found is not None, "Should find at least one untried pair among 10"
    print(
        f"  Untried pair: {found[0]['name']} ({found[0]['short_window_score']}) + {found[1]['name']} ({found[1]['short_window_score']})"
    )
    print(f"  PASS\n")

    # 8. Cleanup
    print(f"[CLEANUP] Removing smoke test records")
    await conn.execute("DELETE FROM combination_memory WHERE child_id = $1", child_id)
    await conn.execute("DELETE FROM strategies WHERE id = $1", child_id)
    await conn.close()
    print(f"  Cleanup complete\n")

    print("=== ALL COMBINER SMOKE TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
