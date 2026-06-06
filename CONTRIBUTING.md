# ATLAS — Contributing Guide

Welcome to the ATLAS project. This guide covers development setup, coding standards, and contribution workflow.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Project Conventions](#project-conventions)
- [Testing](#testing)
- [Code Review](#code-review)
- [Adding New Agents](#adding-new-agents)
- [Adding New Scouts](#adding-new-scouts)
- [Database Migrations](#database-migrations)
- [Documentation](#documentation)

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker (for TimescaleDB and Redis)
- Git
- An Anthropic API key (for LLM-powered agents)

### Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/<your-username>/ATLAS.git
cd ATLAS
git remote add upstream https://github.com/<org>/ATLAS.git
```

---

## Development Setup

### 1. Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Start Infrastructure

```bash
docker compose up -d
```

### 4. Configure Environment

```bash
cp .env.example .env
# Add your API keys
```

### 5. Initialize Database

```bash
python scripts/run_migration.py
python verify_setup.py
```

### 6. Run Tests

```bash
pytest atlas/tests/ -v
```

---

## Coding Standards

### Python Style

- **PEP 8** — Follow standard Python style
- **Type Hints** — Use type hints for all function signatures
- **Docstrings** — Google-style docstrings for all public methods
- **Line Length** — Max 100 characters
- **Imports** — Group: stdlib, third-party, local (alphabetical within groups)

### Example

```python
"""Strategy generation agent using LLM-powered ideation."""

from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger
from redis.asyncio import Redis

from atlas.core.agent_base import BaseAgent
from atlas.data.storage.timescale_client import TimescaleClient


class IdeatorAgent(BaseAgent):
    """Generates trading strategies from scout signals.

    This agent uses Claude LLM to design algorithmic trading strategies
    based on current market conditions and scout intelligence.

    Attributes:
        db_client: Database client for strategy persistence.
        advisory_only: Whether this agent can only produce recommendations.
    """

    def __init__(
        self,
        name: str,
        redis_client: Redis,
        db_client: TimescaleClient,
        advisory_only: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            agent_type="ideator",
            layer="L2",
            redis_client=redis_client,
            advisory_only=advisory_only,
        )
        self.db_client = db_client

    async def run(self) -> None:
        """Main execution loop for strategy generation."""
        logger.info(f"{self.name}: Starting ideation cycle")
        # Implementation...
```

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Classes | PascalCase | `BacktestRunner`, `ScoutSynthesisEngine` |
| Functions | snake_case | `compute_fitness_score`, `validate_strategy` |
| Variables | snake_case | `strategy_id`, `composite_score` |
| Constants | UPPER_SNAKE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Files | snake_case | `backtest_runner.py`, `scout_synthesis_engine.py` |
| Database tables | snake_case | `strategies`, `backtest_results` |

---

## Project Conventions

### Agent Structure

Every agent follows this pattern:

```python
class MyAgent(BaseAgent):
    def __init__(self, name, redis_client, ...):
        super().__init__(name=name, agent_type="...", layer="L?", ...)

    async def run(self) -> None:
        """Main execution loop."""
        while True:
            try:
                await self._do_work()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(5)
```

### Database Access

Always use the `TimescaleClient` for database operations:

```python
from atlas.data.storage.timescale_client import TimescaleClient

db = TimescaleClient(settings.database_url)
async with db.engine.connect() as conn:
    result = await conn.execute(text("SELECT ..."))
    rows = result.fetchall()
```

### Redis Access

Use the provided Redis client:

```python
from redis.asyncio import Redis

redis = Redis.from_url(settings.redis_url)
await redis.set("key", "value")
await redis.publish("channel", "message")
```

### Configuration

Always use the centralized settings:

```python
from atlas.config.settings import settings

db_url = settings.database_url
api_key = settings.anthropic_api_key
```

---

## Testing

### Test Structure

```
atlas/tests/
├── test_agent_base.py          # BaseAgent contract tests
├── test_db.py                  # Database client tests
├── test_ingestion.py           # Data ingestion tests
├── test_l2_agents.py           # Strategy generation tests
├── test_l3_backtest.py         # Backtesting tests
├── test_l4_risk.py             # Risk management tests
├── test_l5_execution.py        # Execution tests
├── test_l7_meta.py             # Meta-learning tests
├── test_selection.py           # Tournament selection tests
└── test_*_persistence.py       # Persistence integrity tests
```

### Writing Tests

```python
import pytest
from atlas.agents.l2_strategy.ideator_agent import IdeatorAgent


@pytest.mark.asyncio
async def test_ideator_generates_strategy():
    """Test that IdeatorAgent generates a valid strategy."""
    # Arrange
    redis_client = mock_redis()
    db_client = mock_db()
    agent = IdeatorAgent(
        name="test-ideator",
        redis_client=redis_client,
        db_client=db_client,
    )

    # Act
    strategy = await agent._generate_strategy(regime="bullish")

    # Assert
    assert strategy is not None
    assert "entry_conditions" in strategy
    assert "exit_conditions" in strategy
    assert len(strategy["entry_conditions"]) > 0
```

### Running Tests

```bash
# All tests
pytest atlas/tests/ -v

# Specific test file
pytest atlas/tests/test_selection.py -v

# With coverage
pytest atlas/tests/ --cov=atlas --cov-report=html

# Parallel execution
pytest atlas/tests/ -n auto
```

---

## Code Review

### Before Submitting

1. Run all tests: `pytest atlas/tests/ -v`
2. Check for type errors (if using mypy)
3. Verify no unused imports
4. Ensure docstrings are present
5. Update relevant documentation

### Review Checklist

- [ ] Tests pass
- [ ] Code follows style guide
- [ ] Type hints are present
- [ ] Docstrings are clear
- [ ] No security issues (API keys, credentials)
- [ ] Database changes include migrations
- [ ] Performance impact assessed

---

## Adding New Agents

### 1. Create Agent File

```python
# atlas/agents/l7_meta/my_new_agent.py

"""My new meta-learning agent."""

from atlas.core.agent_base import BaseAgent
from atlas.config.settings import settings


class MyNewAgent(BaseAgent):
    def __init__(self, name, redis_client, db_client, advisory_only=True):
        super().__init__(
            name=name,
            agent_type="my_new_agent",
            layer="L7",
            redis_client=redis_client,
            advisory_only=advisory_only,  # Meta agents are advisory-only
        )
        self.db_client = db_client

    async def run(self) -> None:
        """Main execution loop."""
        while True:
            try:
                await self._analyze_and_recommend()
                await asyncio.sleep(300)  # Run every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(30)

    async def _analyze_and_recommend(self) -> None:
        """Analyze system state and produce recommendations."""
        # 1. Gather data
        # 2. Analyze
        # 3. Persist recommendations
        pass
```

### 2. Add to MetaOrchestrator

```python
# atlas/core/meta_orchestrator.py

from atlas.agents.l7_meta.my_new_agent import MyNewAgent

# Add to PHASE31_ENGINE_TYPES if needed
```

### 3. Write Tests

```python
# atlas/tests/test_my_new_agent.py

@pytest.mark.asyncio
async def test_my_new_agent_recommends():
    ...
```

### 4. Update Documentation

Add agent to `docs/agent_ecosystem.md`.

---

## Adding New Scouts

### 1. Create Scout File

```python
# atlas/agents/scouts/my_scout.py

"""My new scout agent."""

from atlas.agents.scouts.base_scout import BaseScout


class MyScout(BaseScout):
    def __init__(self, name, redis_client, db_client):
        super().__init__(
            name=name,
            source="my_source",
            redis_client=redis_client,
            db_client=db_client,
        )

    async def collect_signals(self) -> list[dict]:
        """Collect signals from my source."""
        # 1. Fetch data
        # 2. Analyze
        # 3. Return signals
        return signals
```

### 2. Register in Scout Network

Add to the scout initialization in the orchestrator.

### 3. Add Anti-Poisoning Rules

```python
# In anti_poisoning_engine.py

_QUARANTINE_RULES["my_scout"] = {
    "max_anomaly_rate": 0.1,
    "min_confidence": 0.3,
}
```

---

## Database Migrations

### Adding New Tables

```python
# In timescale_client.py connect() method

await conn.execute(text("""
    CREATE TABLE IF NOT EXISTS my_new_table (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        -- columns...
    )
"""))
await conn.execute(text(
    "CREATE INDEX IF NOT EXISTS idx_my_table_created ON my_new_table (created_at DESC)"
))
```

### Adding Columns to Existing Tables

```python
await conn.execute(text(
    "ALTER TABLE existing_table ADD COLUMN IF NOT EXISTS new_column TYPE DEFAULT value"
))
```

### Schema Versioning

```python
await conn.execute(text(
    "INSERT INTO schema_version (version, description) "
    "VALUES ('v30.0', 'Description of changes') ON CONFLICT DO NOTHING"
))
```

---

## Documentation

### When to Update Docs

- Adding new agents → Update `docs/agent_ecosystem.md`
- Changing architecture → Update `docs/architecture.md`
- Adding API endpoints → Update API reference
- Changing deployment → Update `DEPLOYMENT.md`
- Adding configuration → Update `README.md` configuration section

### Doc Standards

- Use Markdown
- Include code examples
- Keep tables aligned
- Use consistent terminology

---

## Pull Request Process

1. **Create branch:** `git checkout -b feature/my-feature`
2. **Make changes:** Follow coding standards
3. **Write tests:** Ensure coverage
4. **Run tests:** `pytest atlas/tests/ -v`
5. **Commit:** Use conventional commits (`feat:`, `fix:`, `docs:`, etc.)
6. **Push:** `git push origin feature/my-feature`
7. **Create PR:** Fill out PR template
8. **Review:** Address feedback
9. **Merge:** Squash and merge

### Commit Messages

```
feat: add regime-aware capital allocation
fix: prevent dead-letter accumulation in copy trader
docs: update deployment guide for Kubernetes
test: add unit tests for scout synthesis engine
refactor: extract cost modeling to separate module
```

---

## Questions?

- Check existing documentation in `docs/`
- Review existing code for patterns
- Open an issue for discussion

---

*Thank you for contributing to ATLAS!*
