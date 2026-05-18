import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from atlas.core.agent_base import BaseAgent, AgentLayer, AgentStatus
from atlas.core.agent_registry import AgentRegistry

class DummyAgent(BaseAgent):
    def __init__(self, redis_client):
        super().__init__(name="Dummy", agent_type="Test", layer=AgentLayer.L1, redis_client=redis_client)
        self.run_called = 0
        self.fail_times = 0

    async def run(self):
        self.run_called += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise Exception("Simulated crash")
        # Keep running
        await asyncio.sleep(0.5)

@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    # Setup some basic returns if needed
    mock.set = AsyncMock()
    mock.hset = AsyncMock()
    mock.hgetall = AsyncMock(return_value={b'agent_id': b'123', b'name': b'Dummy', b'agent_type': b'Test', b'layer': b'L1', b'status': b'running'})
    mock.get = AsyncMock(return_value=b'running')
    mock.exists = AsyncMock(return_value=True)
    return mock

@pytest.fixture
def mock_db_engine():
    with patch("atlas.core.agent_registry.create_async_engine") as mock_engine:
        yield mock_engine

@pytest.mark.asyncio
async def test_agent_registration(mock_redis, mock_db_engine):
    agent = DummyAgent(mock_redis)
    registry = AgentRegistry(mock_redis, "sqlite+aiosqlite:///:memory:")
    
    # Mocking the session and execute
    registry.async_session = MagicMock()
    mock_session = AsyncMock()
    registry.async_session.return_value.__aenter__.return_value = mock_session
    
    await registry.register(agent)
    
    mock_redis.hset.assert_called_once()
    mock_session.execute.assert_called_once()

@pytest.mark.asyncio
async def test_agent_heartbeat(mock_redis):
    agent = DummyAgent(mock_redis)
    await agent.start()
    
    # Let it run for a bit to send heartbeat
    await asyncio.sleep(0.1)
    
    # It should have called redis.hset for heartbeat
    assert mock_redis.hset.call_count >= 1
    call_args = mock_redis.hset.call_args[0]
    assert call_args[0] == f"agent:{agent.agent_id}"
    kwargs = mock_redis.hset.call_args[1]
    assert "mapping" in kwargs
    assert kwargs["mapping"]["status"] == AgentStatus.RUNNING.value
    
    # And expire
    assert mock_redis.expire.call_count >= 1
    
    await agent.stop()

@pytest.mark.asyncio
async def test_agent_auto_restart_on_crash(mock_redis):
    agent = DummyAgent(mock_redis)
    agent.fail_times = 1  # It will fail once
    
    await agent.start()
    
    # Let the event loop process the tasks
    await asyncio.sleep(0.1)
    
    # Stop it gracefully
    await agent.stop()
        
    assert agent.run_called >= 1

@pytest.mark.asyncio
async def test_health_check_detection(mock_redis, mock_db_engine):
    registry = AgentRegistry(mock_redis, "sqlite+aiosqlite:///:memory:")
    
    # Setup mock to return an agent from list_agents
    mock_agent = MagicMock()
    mock_agent.agent_id = "test-123"
    mock_agent.status = AgentStatus.RUNNING
    
    with patch.object(registry, 'list_agents', return_value=[mock_agent]):
        # Simulate missing heartbeat
        mock_redis.exists.return_value = False
        
        dead_agents = await registry.health_check()
        assert "test-123" in dead_agents
        
        # Simulate active heartbeat
        mock_redis.exists.return_value = True
        dead_agents = await registry.health_check()
        assert "test-123" not in dead_agents
