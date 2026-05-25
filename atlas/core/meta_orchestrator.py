import asyncio
import httpx
from loguru import logger
from atlas.core.agent_registry import AgentRegistry
from atlas.config.settings import get_settings
from atlas.agents.l7_meta.regime_stress_engine import RegimeStressEngine
from atlas.agents.l7_meta.dominant_organism_tracker import DominantOrganismTracker
from atlas.agents.l7_meta.mutation_lineage_tracker import MutationLineageTracker
from atlas.agents.l7_meta.regime_specialization_engine import RegimeSpecializationEngine
from atlas.agents.l7_meta.scout_divergence_engine import ScoutDivergenceEngine
from atlas.agents.l6_portfolio.portfolio_evolution_pressure import PortfolioEvolutionPressure


# ─────────────────────────────────────────────────────────
# PHASE 31 ENGINE TYPES — used for selective startup
# ─────────────────────────────────────────────────────────
PHASE31_ENGINE_TYPES = (
    RegimeStressEngine,
    DominantOrganismTracker,
    MutationLineageTracker,
    RegimeSpecializationEngine,
    ScoutDivergenceEngine,
    PortfolioEvolutionPressure,
)


class MetaOrchestrator:
    def __init__(self, registry: AgentRegistry, agents: list):
        self.registry = registry
        self.agents = agents
        # Holds registry of all agent instances
        self.agent_map = {a.agent_id: a for a in agents}
        self._monitor_task: asyncio.Task | None = None
        self._phase31_engines: list = []

    async def start_all(self):
        # Phase 31: Start all L7/L6 evolutionary engines in background
        phase31_engines = [
            a for a in self.agents
            if isinstance(a, PHASE31_ENGINE_TYPES)
        ]
        if phase31_engines:
            self._phase31_engines = phase31_engines
            await asyncio.gather(*(a.start() for a in phase31_engines), return_exceptions=True)
            names = [a.name for a in phase31_engines]
            logger.info(
                f"Phase 31 engines started: {len(phase31_engines)} instances "
                f"({', '.join(names)})"
            )

        # Spawn agents in order:
        # 1. EquityIngestorAgent + CryptoIngestorAgent (parallel)
        l1_agents = [
            a
            for a in self.agents
            if a.name in ["EquityIngestorAgent", "CryptoIngestorAgent"]
        ]
        await asyncio.gather(*(a.start() for a in l1_agents), return_exceptions=True)

        # 2. Wait 5s, then FeatureAgent
        await asyncio.sleep(5)
        feature_agents = [a for a in self.agents if a.name == "FeatureAgent"]
        for a in feature_agents:
            await a.start()

        # 3. Wait until FeatureAgent status=running, then IdeatorAgent x5
        if feature_agents:
            feature_agent = feature_agents[0]
            while feature_agent.status != "running":
                await asyncio.sleep(1)

        ideator_agents = [a for a in self.agents if "IdeatorAgent" in a.name]
        if ideator_agents:
            await asyncio.gather(
                *(a.start() for a in ideator_agents), return_exceptions=True
            )

        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        # runs every 30 seconds
        try:
            while True:
                await asyncio.sleep(30)
                dead_agents = await self.registry.health_check()
                for dead_agent in dead_agents:
                    agent_id = dead_agent["agent_id"]
                    if agent_id in self.agent_map:
                        a = self.agent_map[agent_id]
                        logger.warning(
                            f"Agent {a.name} died on {a.layer}. Restarting..."
                        )

                        # POST to SLACK_WEBHOOK_URL
                        try:
                            async with httpx.AsyncClient() as client:
                                payload = {
                                    "text": f"Agent {a.name} died on {a.layer}. Restarting..."
                                }
                                settings = get_settings()
                                webhook_url = getattr(
                                    settings, "slack_webhook_url", "http://localhost"
                                )
                                if webhook_url:
                                    await client.post(webhook_url, json=payload)
                        except Exception as e:
                            logger.error(f"Failed to post to Slack: {e}")

                        # Wait 5s then restart
                        await asyncio.sleep(5)
                        await a.start()
        except asyncio.CancelledError:
            pass

    async def status_report(self) -> dict:
        report = {}
        agents = await self.registry.list_agents()
        for a in agents:
            layer = a.get("layer", "unknown")
            status = a.get("status", "unknown")
            if layer not in report:
                report[layer] = {"alive": 0, "dead": 0}
            if status == "running":
                report[layer]["alive"] += 1
            else:
                report[layer]["dead"] += 1
        return report
