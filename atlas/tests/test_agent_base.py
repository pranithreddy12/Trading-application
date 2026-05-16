import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from atlas.core.agent_base import BaseAgent
from atlas.core.agent_registry import AgentRegistry

class DummyAgent(BaseAgent):
    def __init__(self, name, agent_type, layer, redis_client):
        super().__init__(name, agent_type, layer, redis_client)
        self.run_called = 0
        self.should_fail = False

    async def run(self):
        self.run_called += 1
        if self.should_fail:
            raise ValueError("Simulated run exception")
        # Keep running to simulate normal work
        await asyncio.sleep(1)

@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.hset = AsyncMock()
    mock.expire = AsyncMock()
    return mock

@pytest.fixture
def mock_db():
    mock = AsyncMock()
    return mock

@pytest.mark.asyncio
async def test_agent_starts_and_sets_status(mock_redis):
    agent = DummyAgent("TestAgent", "Dummy", "L1", mock_redis)
    await agent.start()
    assert agent.status == "running"
    await agent.stop()
    assert agent.status == "stopped"

@pytest.mark.asyncio
async def test_heartbeat_writes_redis_keys(mock_redis):
    agent = DummyAgent("TestAgent", "Dummy", "L1", mock_redis)
    await agent.start()
    
    # allow heartbeat to run once
    await asyncio.sleep(0.1)
    
    # check that hset was called
    key = f"agent:{agent.agent_id}"
    mock_redis.hset.assert_called_with(key, mapping={
        "status": "running",
        "layer": "L1",
        "name": "TestAgent"
    })
    mock_redis.expire.assert_called_with(key, 30)
    
    await agent.stop()

@pytest.mark.asyncio
async def test_auto_restart_on_run_exception(mock_redis):
    agent = DummyAgent("FailAgent", "Dummy", "L1", mock_redis)
    agent.should_fail = True
    
    original_sleep = asyncio.sleep
    async def custom_sleep(delay):
        await original_sleep(0)
    
    with patch("atlas.core.agent_base.asyncio.sleep", side_effect=custom_sleep):
        await agent.start()
        
        # Give event loop time to run retries
        for _ in range(50):
            if agent.run_called > 1:
                break
            await asyncio.sleep(0.01)
        
        # it should have called run multiple times (initial + retries)
        assert agent.run_called > 1
        
    await agent.stop()

@pytest.mark.asyncio
async def test_max_retries_stops_retrying_and_sets_error(mock_redis):
    agent = DummyAgent("FailAgentMax", "Dummy", "L1", mock_redis)
    agent.should_fail = True
    
    original_sleep = asyncio.sleep
    async def custom_sleep(delay):
        await original_sleep(0)
    
    with patch("atlas.core.agent_base.asyncio.sleep", side_effect=custom_sleep):
        # call _run_with_retry directly to easily await its completion
        agent.status = "running"
        await agent._run_with_retry()
        
        assert agent._retry_count == agent.MAX_RETRIES + 1
        assert agent.status == "error"

@pytest.mark.asyncio
async def test_health_check_stale_heartbeat(mock_redis, mock_db):
    registry = AgentRegistry(mock_redis, mock_db)
    
    # Simulate DB having a running agent
    mock_db.fetch = AsyncMock(return_value=[
        {"agent_id": "123", "name": "StaleAgent", "status": "running"}
    ])
    
    # Simulate Redis NOT having the key (expired)
    mock_redis.exists = AsyncMock(return_value=False)
    
    dead_agents = await registry.health_check()
    
    assert len(dead_agents) == 1
    assert dead_agents[0]["agent_id"] == "123"
