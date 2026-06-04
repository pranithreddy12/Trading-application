from redis.asyncio import Redis
from loguru import logger

class AgentRegistry:
    def __init__(self, redis: Redis, db_client):
        self.redis = redis
        self.db = db_client
    
    async def register(self, agent) -> None:
        # Write to Redis hash
        key = f"agent:{agent.agent_id}"
        await self.redis.hset(key, mapping={
            "status": agent.status,
            "layer": agent.layer,
            "name": agent.name
        })
        
        # Write to agent_registry DB table
        if self.db:
            query = """
                INSERT INTO agent_registry (agent_id, name, layer, status)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (agent_id) DO UPDATE 
                SET status = EXCLUDED.status
            """
            try:
                await self.db.execute(query, agent.agent_id, agent.name, agent.layer, agent.status)
            except Exception as exc:
                logger.warning(f"AgentRegistry register DB write failed for {agent.agent_id}: {exc}")

    async def deregister(self, agent_id: str) -> None:
        # Set status=stopped in Redis and DB
        key = f"agent:{agent_id}"
        await self.redis.hset(key, "status", "stopped")
        
        if self.db:
            query = "UPDATE agent_registry SET status = 'stopped' WHERE agent_id = $1"
            try:
                await self.db.execute(query, agent_id)
            except Exception as exc:
                logger.warning(f"AgentRegistry deregister DB write failed for {agent_id}: {exc}")

    async def get_agent(self, agent_id: str) -> dict:
        key = f"agent:{agent_id}"
        data = await self.redis.hgetall(key)
        if data:
            return {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in data.items()}
            
        if self.db:
            query = "SELECT * FROM agent_registry WHERE agent_id = $1"
            try:
                row = await self.db.fetchrow(query, agent_id)
                if row:
                    return dict(row)
            except Exception as exc:
                logger.warning(f"AgentRegistry DB lookup failed for {agent_id}: {exc}")
        return {}
        
    async def list_agents(self, layer=None, status=None) -> list[dict]:
        agents = []
        keys = await self.redis.keys("agent:*")
        for key in keys:
            data = await self.redis.hgetall(key)
            decoded = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in data.items()}
            if layer and decoded.get("layer") != layer:
                continue
            if status and decoded.get("status") != status:
                continue
            decoded["agent_id"] = key.decode().split(":")[1] if isinstance(key, bytes) else key.split(":")[1]
            agents.append(decoded)
        return agents
        
    async def health_check(self) -> list[dict]:
        dead_agents = []
        # Return agents where last heartbeat > 30 seconds ago
        # Since we use Redis EXPIRE 30, keys that disappeared are dead,
        # but if we just check db vs redis:
        if self.db:
            # Simplistic representation
            query = "SELECT * FROM agent_registry WHERE status = 'running'"
            try:
                rows = await self.db.fetch(query)
                for row in rows:
                    agent_id = row['agent_id']
                    exists = await self.redis.exists(f"agent:{agent_id}")
                    if not exists:
                        dead_agents.append(dict(row))
            except Exception as exc:
                logger.warning(f"AgentRegistry health_check DB query failed: {exc}")
        return dead_agents
        
    async def update_heartbeat(self, agent_id: str) -> None:
        key = f"agent:{agent_id}"
        await self.redis.expire(key, 30)
