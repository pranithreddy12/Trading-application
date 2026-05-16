import asyncio
import json
from datetime import datetime
from loguru import logger
from redis.asyncio import Redis
import uvicorn
from fastapi import FastAPI
import aiohttp

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings

app = FastAPI(title="Kill Switch API")

class KillSwitch(BaseAgent):
    name = "KillSwitch"
    agent_type = "kill_switch"
    layer = "L4"
    
    # Store globally to access via FastAPI
    _instance = None

    def __init__(self, redis_client: Redis, db_client: TimescaleClient):
        super().__init__(
            name=self.name,
            agent_type=self.agent_type,
            layer=self.layer,
            redis_client=redis_client
        )
        self.db_client = db_client
        self.messaging = MessagingClient(redis_client)
        self._is_active: bool = False
        self._activated_at: datetime | None = None
        self._reason: str = ""
        self._api_task = None
        KillSwitch._instance = self

    async def start(self):
        # FIRST: read persisted state from Redis AND DB
        # If either shows active=True, restore _is_active=True
        redis_active = await self.is_active(self._redis)
        db_meta = await self.db_client.get_agent_metadata(self.name)
        db_active = db_meta.get("active", False) if db_meta else False

        if redis_active or db_active:
            self._is_active = True
            self._activated_at = datetime.utcnow()
            reason_redis = await self._redis.hget("kill_switch:state", "reason")
            self._reason = reason_redis.decode('utf-8') if reason_redis else "restored from DB"
            logger.warning(f"Kill Switch restored as ACTIVE: {self._reason}")

        await super().start()

    async def run(self):
        # Start FastAPI
        config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="warning")
        server = uvicorn.Server(config)
        self._api_task = asyncio.create_task(server.serve())

        # Subscribe to risk_alerts channel
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(Channel.RISK_ALERTS.value)
        
        while self.status == "running":
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                try:
                    data = json.loads(message["data"])
                    if data.get("type") == "limit_breach":
                        reason = data.get("reason", "automated")
                        await self.activate(reason)
                except Exception as e:
                    logger.error(f"Error parsing pubsub message: {e}")
            await asyncio.sleep(0.1)

    async def stop(self):
        if self._api_task:
            self._api_task.cancel()
        await super().stop()

    async def activate(self, reason: str = "automated"):
        self._is_active = True
        self._reason = reason
        self._activated_at = datetime.utcnow()
        
        # 2. HSET kill_switch:state
        await self._redis.hset("kill_switch:state", mapping={
            "active": "1",
            "reason": reason
        })
        
        # 3. UPDATE agent_registry
        await self.db_client.update_agent_metadata_active(self.name, True)
        
        # 4. Publish to ALL channels
        channels = [Channel.SYSTEM_EVENTS, Channel.STRATEGY_SIGNALS, Channel.RISK_ALERTS, Channel.MARKET_DATA, Channel.EXECUTION_FILLS]
        for ch in channels:
            await self.messaging.publish(ch, {
                "type": "KILL_SWITCH_ACTIVATED",
                "reason": reason
            })
            
        # 5. Log CRITICAL
        await self.db_client.log(
            self.agent_id,
            "CRITICAL",
            "KILL SWITCH ACTIVATED",
            {"reason": reason}
        )
        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        
        # 6. POST Slack
        await self._post_slack(f"🚨 KILL SWITCH ACTIVATED — Reason: {reason}")

    async def deactivate(self):
        self._is_active = False
        self._reason = ""
        self._activated_at = None
        
        # 2. Clear Redis kill_switch:state
        await self._redis.delete("kill_switch:state")
        
        # 3. Update DB metadata
        await self.db_client.update_agent_metadata_active(self.name, False)
        
        # 4. Publish
        await self.messaging.publish(Channel.SYSTEM_EVENTS, {
            "type": "KILL_SWITCH_DEACTIVATED"
        })
        
        # 5. POST Slack
        await self._post_slack("✅ Kill switch deactivated — trading resumed")
        logger.info("Kill switch deactivated")

    async def _post_slack(self, text: str):
        url = settings.slack_webhook_url
        if not url:
            return
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"text": text})
        except Exception as e:
            logger.error(f"Slack post error: {e}")

    @staticmethod
    async def is_active(redis: Redis) -> bool:
        result = await redis.hget("kill_switch:state", "active")
        return result == b"1"


@app.post("/kill")
async def api_kill():
    if KillSwitch._instance:
        await KillSwitch._instance.activate("manual")
        return {"status": "activated"}
    return {"status": "error", "message": "KillSwitch not running"}

@app.post("/resume")
async def api_resume():
    if KillSwitch._instance:
        await KillSwitch._instance.deactivate()
        return {"status": "deactivated"}
    return {"status": "error", "message": "KillSwitch not running"}

@app.get("/status")
async def api_status():
    if KillSwitch._instance:
        return {
            "active": KillSwitch._instance._is_active,
            "activated_at": KillSwitch._instance._activated_at,
            "reason": KillSwitch._instance._reason,
            "agent_count_halted": 0  # Placeholder, usually queried from DB or meta orchestrator
        }
    return {"status": "error", "message": "KillSwitch not running"}
