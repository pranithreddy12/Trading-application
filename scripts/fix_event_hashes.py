"""
fix_event_hashes.py — Recompute hash_self and hash_prev for all events in event_store.

This fixes "self-hash mismatch" violations detected by ReplayEngine.verify_integrity().
Events that were inserted directly (not via EventStore.append_event) have incorrect hashes.
"""
import asyncio
import hashlib
import json
import sys

from sqlalchemy import text
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient


async def main():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    await db.connect()

    async with db.engine.connect() as conn:
        # Fetch all events ordered by aggregate_id, sequence
        result = await conn.execute(
            text("""
                SELECT id, event_type, version, trace_id, parent_event_id,
                       aggregate_id, aggregate_type, data, metadata,
                       hash_prev, hash_self, created_at, sequence
                FROM event_store
                ORDER BY aggregate_id, sequence ASC
            """)
        )
        rows = result.fetchall()
        print(f"Found {len(rows)} events to process")

    if not rows:
        print("No events found. Nothing to fix.")
        return

    # Group by aggregate_id for hash chain
    from collections import OrderedDict

    aggregates = OrderedDict()
    for row in rows:
        agg_id = str(row[4]) if row[4] else "__no_aggregate__"
        if agg_id not in aggregates:
            aggregates[agg_id] = []
        aggregates[agg_id].append(row)

    fixed_count = 0
    for agg_id, events in aggregates.items():
        prev_hash = None
        for event in events:
            event_id = str(event[0])
            event_type = str(event[1])
            version = str(event[2])
            trace_id = str(event[3])
            parent_event_id = str(event[4]) if event[4] else None
            aggregate_id = str(event[5]) if event[5] else None
            aggregate_type = str(event[6]) if event[6] else None
            data_raw = event[7]
            meta_raw = event[8]
            stored_hash_prev = str(event[9]) if event[9] else None
            stored_hash_self = str(event[10])
            created_at = event[11]
            sequence = int(event[12])

            # Parse data and metadata
            if isinstance(data_raw, str):
                data_raw = json.loads(data_raw)
            if isinstance(meta_raw, str):
                meta_raw = json.loads(meta_raw)

            # Convert created_at to ISO string
            created_at_iso = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)

            # Rebuild content like append_event does
            content = {
                "id": event_id,
                "event_type": event_type,
                "version": version,
                "trace_id": trace_id,
                "parent_event_id": parent_event_id,
                "aggregate_id": aggregate_id,
                "aggregate_type": aggregate_type,
                "data": data_raw,
                "metadata": meta_raw or {},
                "hash_prev": prev_hash,
                "sequence": sequence,
                "created_at": created_at_iso,
            }
            expected_hash = hashlib.sha256(
                json.dumps(content, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()

            needs_update = False
            if expected_hash != stored_hash_self:
                needs_update = True
            if stored_hash_prev != prev_hash:
                needs_update = True

            if needs_update:
                async with db.engine.connect() as conn2:
                    await conn2.execute(
                        text("""
                            UPDATE event_store
                            SET hash_self = :hash_self,
                                hash_prev = :hash_prev
                            WHERE id = :id
                        """),
                        {
                            "hash_self": expected_hash,
                            "hash_prev": prev_hash,
                            "id": event_id,
                        },
                    )
                fixed_count += 1
                if fixed_count <= 5 or fixed_count % 50 == 0:
                    print(f"  Fixed seq={sequence} ({event_id[:8]}...) hash_prev={str(prev_hash)[:12] if prev_hash else 'None'}")

            prev_hash = expected_hash

    print(f"\nFixed {fixed_count} / {len(rows)} events")
    print("Done — hashes recomputed.")


if __name__ == "__main__":
    asyncio.run(main())
