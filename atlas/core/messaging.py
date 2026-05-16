import json
import asyncio
from enum import Enum
from redis.asyncio import Redis

class Channel(str, Enum):
    MARKET_DATA = "market_data"
    STRATEGY_SIGNALS = "strategy_signals"
    RISK_ALERTS = "risk_alerts"
    EXECUTION_FILLS = "execution_fills"
    SYSTEM_EVENTS = "system_events"

class MessagingClient:
    def __init__(self, redis_pool: Redis):
        self.redis = redis_pool
        # Shared connection pool: pool_size=10 is assumed to be handled by the redis_pool provided
        
    async def publish(self, channel: Channel, message: dict) -> None:
        try:
            payload = json.dumps(message)
            await self.redis.publish(channel.value, payload)
        except Exception:
            pass

    async def subscribe(self, channel: Channel, callback: callable) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel.value)
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    # Mocking dead letter logic for callback
                    success = False
                    for _ in range(3):
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(data)
                            else:
                                callback(data)
                            success = True
                            break
                        except Exception:
                            pass
                            
                    if not success:
                        await self.redis.rpush(f"dead_letter:{channel.value}", message["data"])
                except Exception:
                    pass
