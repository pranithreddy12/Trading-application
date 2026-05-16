print("=== IDEATOR FILE LOADED ===", flush=True)

import asyncio
import hashlib
import json
import random
from collections import Counter
from datetime import datetime
from loguru import logger
from redis.asyncio import Redis
from anthropic import AsyncAnthropic
import httpx

from atlas.core.agent_base import BaseAgent
from atlas.core.messaging import MessagingClient, Channel
from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.agents.l2_strategy.strategy_normalizer import (
    normalize_strategy,
    validate_strategy,
    compute_strategy_signature,
)


ARCHETYPES = ["momentum", "mean_reversion", "breakout", "volatility", "trend_following"]

ASSET_CLASSES = ["equity", "crypto"]

AVAILABLE_FEATURES = [
    "returns",
    "log_returns",
    "rsi_14",
    "macd",
    "macd_signal",
    "sma_5",
    "sma_20",
    "ema_12",
    "ema_26",
    "bollinger_upper",
    "bollinger_lower",
    "rolling_volatility",
    "vwap",
    # Normalized cross-asset features
    "price_vs_vwap_pct",
    "ema_spread_pct",
    "relative_volume",
    "bollinger_band_position",
    "volatility_regime",
    "trend_strength",
]

NORMALIZED_FEATURES = [
    "price_vs_vwap_pct",
    "ema_spread_pct",
    "relative_volume",
    "bollinger_band_position",
    "volatility_regime",
    "trend_strength",
]

EQUITY_ENTRY_TEMPLATES = {
    "momentum": ["returns > 0.0005", "macd > macd_signal"],
    "mean_reversion": ["rsi_14 < 35", "close < vwap"],
    "breakout": ["close > bollinger_upper", "relative_volume > 1.5"],
    "volatility": ["volatility_regime > 1.2", "rsi_14 < 40"],
    "trend_following": ["ema_spread_pct > 0.001", "close > sma_20"],
}

EQUITY_EXIT_TEMPLATES = {
    "momentum": ["returns < -0.0005", "rsi_14 > 70"],
    "mean_reversion": ["bollinger_band_position > 0.8", "close > vwap"],
    "breakout": ["rsi_14 > 70", "close < sma_20"],
    "volatility": ["volatility_regime < 0.8", "rsi_14 > 60"],
    "trend_following": ["ema_spread_pct < -0.001", "rsi_14 < 40"],
}

CRYPTO_ENTRY_TEMPLATES = {
    "momentum": ["returns > 0.001", "trend_strength > 0.002"],
    "mean_reversion": ["rsi_14 < 30", "price_vs_vwap_pct < -0.005"],
    "breakout": ["close > bollinger_upper", "relative_volume > 2.0"],
    "volatility": ["volatility_regime > 1.5", "rsi_14 < 35"],
    "trend_following": ["ema_12 > ema_26", "trend_strength > 0.001"],
}

CRYPTO_EXIT_TEMPLATES = {
    "momentum": ["returns < -0.001", "rsi_14 > 75"],
    "mean_reversion": ["bollinger_band_position > 0.9", "price_vs_vwap_pct > 0.005"],
    "breakout": ["rsi_14 > 75", "close < sma_20"],
    "volatility": ["volatility_regime < 0.7", "rsi_14 > 65"],
    "trend_following": ["ema_12 < ema_26", "rsi_14 < 35"],
}

TEMP_MAP = [0.3, 0.5, 0.7, 0.9, 1.0]

FEATURE_SUBSETS = {
    "A": ["vwap", "macd", "macd_signal"],
    "B": ["rsi_14", "bollinger_upper", "bollinger_lower", "bollinger_band_position"],
    "C": ["ema_12", "ema_26", "ema_spread_pct", "trend_strength"],
    "D": ["volatility_regime", "relative_volume", "returns"],
}

ARCHETYPE_FEATURES = {
    "momentum": [
        "macd",
        "macd_signal",
        "relative_volume",
        "price_vs_vwap_pct",
        "returns",
    ],
    "mean_reversion": [
        "bollinger_band_position",
        "rsi_14",
        "price_vs_vwap_pct",
        "bollinger_upper",
        "bollinger_lower",
    ],
    "breakout": [
        "bollinger_upper",
        "bollinger_lower",
        "relative_volume",
        "volatility_regime",
        "vwap",
    ],
    "volatility": ["volatility_regime", "bollinger_band_position", "rsi_14", "returns"],
    "trend_following": ["ema_spread_pct", "trend_strength", "vwap", "ema_12", "ema_26"],
}

ALLOWED_SYMBOLS = [
    "NVDA",
    "TSLA",
    "AAPL",
    "SPY",
    "QQQ",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
    "AMD",
]


class IdeatorAgent(BaseAgent):
    """
    Generates trading strategy specifications using Claude API (with local fallback).
    Runs as 5 parallel instances with different temperatures and archetypes.
    """

    def __init__(
        self,
        instance_id: int,
        temperature: float,
        redis_client: Redis,
        db_client: TimescaleClient,
    ):
        super().__init__(
            name=f"IdeatorAgent_{instance_id}",
            agent_type="ideator",
            layer="L2",
            redis_client=redis_client,
        )
        self.instance_id = instance_id
        self.temperature = max(0.0, min(1.0, temperature))
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=20.0),
            verify=True,
        )
        self.client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url="https://api.anthropic.com",
            http_client=self.http_client,
        )
        self.db_client = db_client
        self.signal_buffer = []
        self.SIGNAL_THRESHOLD = 10
        self.messaging = MessagingClient(redis_client)
        self._archetype = ARCHETYPES[instance_id % len(ARCHETYPES)]
        self._asset_class = ASSET_CLASSES[instance_id % len(ASSET_CLASSES)]
        self._feature_cycle = 0

    async def stop(self):
        await super().stop()
        await self.http_client.aclose()

    async def run(self):
        logger.info(
            f"{self.name}: RUN LOOP START "
            f"(temp={self.temperature}, archetype={self._archetype})"
        )

        while True:
            try:
                logger.info(f"{self.name}: Fetching latest features")

                features = await asyncio.wait_for(
                    self.db_client.get_latest_features(ALLOWED_SYMBOLS, limit=5),
                    timeout=15,
                )

                logger.info(
                    f"{self.name}: Features fetched = {len(features) if features else 0}"
                )

                if not features:
                    logger.warning(f"{self.name}: No features available")
                    await asyncio.sleep(10)
                    continue

                self._feature_cycle = (self._feature_cycle + 1) % 4

                strategy_spec, prompt, raw_response = await self._generate_strategy(
                    features
                )

                if not isinstance(strategy_spec, dict):
                    raise TypeError(
                        f"Expected strategy_spec to be dict, got {type(strategy_spec)}"
                    )
                if "strategy_name" not in strategy_spec:
                    raise ValueError(
                        f"Missing strategy_name in generated spec: {strategy_spec}"
                    )

                signature = compute_strategy_signature(strategy_spec)
                existing = await self.db_client.get_strategy_signatures(limit=200)
                if signature in existing:
                    logger.warning(
                        f"{self.name}: Duplicate signature '{strategy_spec['strategy_name']}', skipping"
                    )
                    await asyncio.sleep(5)
                    continue

                logger.info(f"{self.name}: Writing strategy to DB")

                strategy_id = await asyncio.wait_for(
                    self.db_client.save_strategy(
                        strategy_spec,
                        status="pending_code",
                        author_agent=self.name,
                        prompt=prompt,
                        raw_response=raw_response,
                        strategy_signature=signature,
                    ),
                    timeout=15,
                )

                logger.info(
                    f"{self.name}: Strategy inserted successfully: "
                    f"{strategy_spec['strategy_name']} ({strategy_id})"
                )

                await self.messaging.publish(
                    Channel.STRATEGY_SIGNALS,
                    {
                        "event": "new_strategy",
                        "strategy_id": strategy_id,
                        "agent": self.name,
                        "archetype": self._archetype,
                    },
                )

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"{self.name}: Run loop error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _handle_signal(self, message: dict):
        self.signal_buffer.append(message)
        if len(self.signal_buffer) >= self.SIGNAL_THRESHOLD:
            features = {
                k: v
                for m in self.signal_buffer
                for k, v in m.get("features", {}).items()
            }
            spec, _, _ = await self._generate_strategy(features)
            logger.info(
                f"{self.name}: Generated signal-based strategy: {spec.get('strategy_name', 'unknown')}"
            )
            self.signal_buffer.clear()

    async def _generate_strategy(
        self, features: dict
    ) -> tuple[dict, str | None, str | None]:
        try:
            if settings.anthropic_api_key in (None, "", "test_key"):
                raise RuntimeError("No valid Anthropic API key")
            return await self._generate_via_claude(features)
        except Exception as e:
            logger.warning(
                f"{self.name}: Claude generation failed ({e}), using local fallback"
            )
            return await self._generate_local(features)

    def _extract_json(self, raw: str) -> str:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace == -1 or last_brace == -1:
            raise json.JSONDecodeError("No JSON object found", cleaned, 0)
        return cleaned[first_brace : last_brace + 1]

    def _get_feature_ranges(self) -> dict:
        is_equity = self._asset_class == "equity"
        if is_equity:
            return {
                "rsi_14": "0-100",
                "returns": "-0.005 to 0.005",
                "price_vs_vwap_pct": "-0.01 to 0.01",
                "relative_volume": "0.1-5",
                "volatility_regime": "0.3-3",
                "ema_spread_pct": "-0.01 to 0.01",
            }
        return {
            "rsi_14": "0-100",
            "returns": "-0.01 to 0.01",
            "price_vs_vwap_pct": "-0.02 to 0.02",
            "relative_volume": "0.1-5",
            "volatility_regime": "0.3-3",
            "trend_strength": "0.0-0.01",
            "ema_spread_pct": "-0.02 to 0.02",
        }

    def _build_minimal_prompt(
        self, regime: str, used_combos: list[str] | None = None
    ) -> tuple[str, str]:
        is_equity = self._asset_class == "equity"
        domain = "US EQUITIES" if is_equity else "CRYPTO (Binance)"
        asset_tag = "equity" if is_equity else "crypto"
        returns_range = "-0.005 to 0.005" if is_equity else "-0.01 to 0.01"
        vwap_range = "-0.01 to 0.01" if is_equity else "-0.02 to 0.02"

        arch_features = ARCHETYPE_FEATURES.get(self._archetype, AVAILABLE_FEATURES)
        subset_key = list(FEATURE_SUBSETS.keys())[self._feature_cycle % 4]
        rotated = FEATURE_SUBSETS[subset_key]
        primary_features = [f for f in arch_features if f in rotated] or arch_features[
            :3
        ]
        allowed = ", ".join(primary_features)

        novelty_hint = ""
        if used_combos:
            top = ", ".join(used_combos[:3])
            novelty_hint = (
                f"\nAvoid repeating these recently used feature combinations: {top}"
            )

        system_prompt = f"""You are a quantitative trading strategist for 1-minute {domain} markets.
Generate ONE realistic intraday {self._archetype} strategy.
Rules:
- 2-3 entry conditions, 1-2 exit conditions
- Use only approved features
- Use realistic thresholds
- No raw price thresholds
- No natural language in conditions
- Output valid JSON only"""

        user_prompt = f"""Asset class: {asset_tag}
Archetype: {self._archetype}
Features: {allowed}

Typical ranges:
rsi_14: 0-100
returns: {returns_range}
price_vs_vwap_pct: {vwap_range}
relative_volume: 0.1-5
volatility_regime: 0.3-3

Market regime: {regime}
Target 5-50 weekly entries. Avoid overly restrictive conditions.{novelty_hint}

Generate a realistic strategy with moderate trigger frequency.
Output valid JSON only:
{{"strategy_name":"descriptive_snake_case_name","hypothesis":"one sentence","entry_conditions":["feature > threshold","feature < threshold"],"exit_conditions":["feature > threshold","feature < threshold"],"stop_loss":"0.5% below entry","take_profit":"1% above entry","position_sizing":"10% of portfolio","timeframe":"1m","asset_class":"{asset_tag}","expected_sharpe":1.5,"expected_win_rate":0.55,"risk_level":"medium","tags":["{self._archetype}"]}}"""

        return system_prompt, user_prompt

    async def _generate_via_claude(
        self, features: dict
    ) -> tuple[dict, str | None, str | None]:
        regime = "neutral"
        try:
            rsi_vals = [
                f.get("rsi_14", 50) for f in features.values() if isinstance(f, dict)
            ]
            if rsi_vals:
                avg_rsi = sum(rsi_vals) / len(rsi_vals)
                if avg_rsi < 35:
                    regime = "bearish"
                elif avg_rsi > 65:
                    regime = "bullish"
        except Exception:
            pass

        # Fetch recent feature combos for novelty avoidance
        used_combos = None
        try:
            recent = await self.db_client.get_recent_feature_combos(limit=50)
            same_arch = [
                ", ".join(sorted(fs)) for fs, a in recent if a == self._archetype
            ]
            freq = Counter(same_arch)
            used_combos = [c for c, _ in freq.most_common(5)]
        except Exception:
            pass

        system_prompt, user_prompt = self._build_minimal_prompt(regime, used_combos)

        models = ["claude-sonnet-4-6"]

        last_error = None
        for model in models:
            try:
                response = await self.client.messages.create(
                    model=model,
                    max_tokens=500,
                    temperature=self.temperature,
                    messages=[
                        {"role": "user", "content": user_prompt},
                    ],
                    system=system_prompt,
                )
                raw = response.content[0].text

                logger.info(f"{self.name}: Claude raw response ({model}): {raw}")

                cleaned = self._extract_json(raw)
                strategy_spec = json.loads(cleaned)

                strategy_spec["asset_class"] = self._asset_class

                strategy_spec = normalize_strategy(strategy_spec)

                if "tags" not in strategy_spec:
                    strategy_spec["tags"] = []
                if self._archetype not in strategy_spec["tags"]:
                    strategy_spec["tags"].append(self._archetype)

                valid, reason = validate_strategy(strategy_spec)
                if not valid:
                    raise ValueError(
                        f"Strategy failed validation: {reason} | spec={strategy_spec}"
                    )

                await self.db_client.log(
                    agent_id=self.agent_id,
                    level="INFO",
                    message=f"Generated strategy via Claude ({model})",
                    metadata={
                        "prompt": user_prompt[:500],
                        "response": raw,
                        "model": model,
                        "features_used": list(features.keys()),
                        "archetype": self._archetype,
                        "temperature": self.temperature,
                        "agent_name": self.name,
                        "normalized_spec": strategy_spec,
                        "regime": regime,
                    },
                )

                return strategy_spec, user_prompt, raw

            except json.JSONDecodeError as e:
                logger.warning(
                    f"{self.name}: Claude model {model} returned invalid JSON: {e}"
                )
                last_error = e
                continue
            except Exception as e:
                logger.warning(
                    f"{self.name}: Claude model {model} failed ({e}), trying next"
                )
                last_error = e
                continue

        raise last_error or RuntimeError("All Claude models failed")

    async def _generate_local(self, features: dict) -> tuple[dict, None, None]:
        is_equity = self._asset_class == "equity"
        entry_map = EQUITY_ENTRY_TEMPLATES if is_equity else CRYPTO_ENTRY_TEMPLATES
        exit_map = EQUITY_EXIT_TEMPLATES if is_equity else CRYPTO_EXIT_TEMPLATES
        entry = entry_map.get(self._archetype, ["ema_12 > ema_26"])
        exit_ = exit_map.get(self._archetype, ["ema_12 < ema_26"])
        suffix = datetime.utcnow().strftime("%H%M%S")
        domain = "equity" if is_equity else "crypto"
        spec = {
            "strategy_name": (
                f"{self._archetype.title()}_{domain}_{self.name}_{suffix}"
            ),
            "hypothesis": (
                f"{self._archetype.replace('_', ' ').title()} "
                f"strategy for 1m {domain} data."
            ),
            "entry_conditions": entry,
            "exit_conditions": exit_,
            "stop_loss": "0.5% below entry",
            "take_profit": "1% above entry",
            "position_sizing": (f"{random.choice(['5', '10', '15'])}% of portfolio"),
            "timeframe": "1m",
            "asset_class": domain,
            "expected_sharpe": round(random.uniform(0.8, 2.0), 2),
            "expected_win_rate": round(random.uniform(0.45, 0.65), 2),
            "risk_level": random.choice(["low", "medium", "high"]),
            "tags": [self._archetype],
        }
        await self.db_client.log(
            agent_id=self.agent_id,
            level="INFO",
            message="Generated equity strategy via local fallback",
            metadata={
                "archetype": self._archetype,
                "temperature": self.temperature,
                "strategy_name": spec["strategy_name"],
                "agent_name": self.name,
            },
        )
        return spec, None, None


async def main():
    print("=== IDEATOR MAIN STARTED ===", flush=True)
    print("=== CONNECTING DB ===", flush=True)

    db_client = TimescaleClient(settings.database_url)
    await db_client.connect()
    redis_client = Redis.from_url(settings.redis_url)

    print("=== GENERATING STRATEGIES ===", flush=True)

    agents = [IdeatorAgent(i, TEMP_MAP[i], redis_client, db_client) for i in range(5)]

    await asyncio.gather(*(agent.start() for agent in agents))

    await asyncio.Event().wait()


if __name__ == "__main__":
    print("=== IDEATOR EXECUTION HIT ===", flush=True)
    asyncio.run(main())
