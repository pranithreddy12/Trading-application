import asyncio
import json

from atlas.api.services.auth_service import APIRole, AuthService
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient


async def main():
    db = TimescaleClient(settings.database_url)
    await db.connect()
    service = AuthService(db)

    created = {}
    for role in [APIRole.ADMIN, APIRole.TRADER, APIRole.READ_ONLY, APIRole.FOLLOWER, APIRole.MONITOR]:
        raw_key, key_id = await service.generate_api_key(
            user_id=f"day5_{role.value}",
            role=role,
            created_by="day5_audit",
            description=f"Day5 governance audit key ({role.value})",
            expires_in_days=30,
        )
        created[role.value] = {"key_id": key_id, "raw_key": raw_key}

    print(json.dumps(created, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
