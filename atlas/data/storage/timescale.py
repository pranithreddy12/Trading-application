from loguru import logger
from typing import Any

class TimescaleClient:
    async def write(self, table: str, data: Any):
        logger.debug(f"Writing to {table}: {data}")
