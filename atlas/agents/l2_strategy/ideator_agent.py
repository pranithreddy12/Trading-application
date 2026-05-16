print("=== IDEATOR FILE LOADED ===", flush=True)

import asyncio
import hashlib
import json
import random
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

ARCHETYPES = [
    "momentum",
    "mean_reversion",
    "breakout",
    "volatility_regime",
    "trend_following",
]

TEMP_MAP = [0.4, 0.6, 0.7, 0.85, 1.0]

ALLOWED_FEATURES = [
    "returns",
    "rsi_14",
    "macd",
    "macd_signal",
    "ema_12",
    "ema_26",
    "sma_20",
    "bollinger_upper",
    "bollinger_lower",
    "vwap",
    "volume",
    "close",
    "open",
    "high",
    "low",
    "price_vs_vwap_pct",
    "ema_spread_pct",
    "relative_volume",
    "bollinger_band_position",
    "volatility_regime",
    "trend_strength",
]


class IdeatorAgent(BaseAgent):
    """
    Generates high-quality trading strategy specs using Claude.
    Uses real market context, backtest feedback, and chain-of-thought.
    3000 token budget — Claude actually thinks, not just fills templates.
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
            timeout=httpx.Timeout(120.0, connect=30.0),
            verify=True,
        )
        self.client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            http_client=self.http_client,
        )
        self.db_client = db_client
        self.messaging = MessagingClient(redis_client)
        self._archetype = ARCHETYPES[instance_id % len(ARCHETYPES)]
        self._asset_class = "equity" if instance_id % 2 == 0 else "crypto"

    async def stop(self):
        await super().stop()
        await self.http_client.aclose()

    async def run(self):
        logger.info(
            f"{self.name}: START — archetype={self._archetype}, "
            f"asset={self._asset_class}, temp={self.temperature}"
        )
        while True:
            try:
                # 1. Gather rich context
                context = await self._build_context()

                # 2. Generate strategy with full Claude reasoning
                spec, prompt, raw = await self._generate_strategy(context)

                if not spec:
                    await asyncio.sleep(15)
                    continue

                # 3. Dedup check
                sig = compute_strategy_signature(spec)
                existing = await self.db_client.get_strategy_signatures(limit=500)
                if sig in existing:
                    logger.info(f"{self.name}: Duplicate — skipping")
                    await asyncio.sleep(5)
                    continue

                # 4. Save
                strategy_id = await self.db_client.save_strategy(
                    spec,
                    status="pending_code",
                    author_agent=self.name,
                    prompt=prompt,
                    raw_response=raw,
                )

                logger.info(
                    f"{self.name}: ✅ Saved: {spec['strategy_name']} [{strategy_id}]"
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

                await asyncio.sleep(12)

            except Exception as e:
                logger.error(f"{self.name}: Loop error: {e}", exc_info=True)
                await asyncio.sleep(10)

    # =========================================================
    # CONTEXT BUILDER — gives Claude real data to reason from
    # =========================================================
    async def _build_context(self) -> dict:
        """
        Fetch real market state + backtest feedback.
        Claude gets actual numbers, not placeholders.
        """
        context = {
            "archetype": self._archetype,
            "asset_class": self._asset_class,
            "market_snapshot": {},
            "regime": "neutral",
            "failed_patterns": [],
            "successful_patterns": [],
            "recent_names": [],
            "bars_available": {},
        }

        try:
            # Real feature values for top symbols
            symbols = (
                ["NVDA", "SPY", "AAPL", "TSLA", "QQQ"]
                if self._asset_class == "equity"
                else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
            )

            features = await self.db_client.get_latest_features(symbols, limit=1)

            if features:
                # Pick the symbol with richest feature data
                best_sym = max(
                    features.items(),
                    key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0,
                )
                sym_name, sym_features = best_sym

                if isinstance(sym_features, dict):
                    context["market_snapshot"] = {
                        k: round(float(v), 6)
                        for k, v in sym_features.items()
                        if v is not None and k in ALLOWED_FEATURES
                    }
                    context["primary_symbol"] = sym_name

                    # Determine regime from real data
                    rsi = sym_features.get("rsi_14", 50)
                    vol = sym_features.get("volatility_regime", 1.0)
                    trend = sym_features.get("ema_spread_pct", 0)
                    if rsi and float(rsi) < 35:
                        context["regime"] = "oversold/bearish"
                    elif rsi and float(rsi) > 65:
                        context["regime"] = "overbought/bullish"
                    elif vol and float(vol) > 1.5:
                        context["regime"] = "high_volatility"
                    elif trend and abs(float(trend)) > 0.003:
                        context["regime"] = "strong_trend"
                    else:
                        context["regime"] = "ranging/neutral"

        except Exception as e:
            logger.warning(f"{self.name}: Feature fetch error: {e}")

        try:
            # What has FAILED — learn from mistakes (temporal-aware)
            failed = await self.db_client.get_strategies_with_backtest(
                statuses=["failed_validation", "repair_candidate"], limit=10
            )
            for s in failed:
                results = s.get("results", {})
                if isinstance(results, str):
                    try:
                        results = json.loads(results)
                    except Exception:
                        results = {}
                params = s.get("parameters", {})
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except Exception:
                        params = {}
                entry_conds = params.get("entry_conditions", [])
                win_rate = results.get("win_rate", 0)
                context["failed_patterns"].append(
                    {
                        "entry": entry_conds,
                        "composite_score": s.get("composite_score", "N/A"),
                        "short_window_score": s.get("short_window_score", "N/A"),
                        "trades": s.get("total_trades", 0),
                        "win_rate": win_rate
                        if isinstance(win_rate, (int, float))
                        else 0,
                        "reason": params.get("validation_notes", "unknown"),
                    }
                )

        except Exception as e:
            logger.warning(f"{self.name}: Failed patterns fetch: {e}")

        try:
            # What has WORKED — learn from successes (temporal-aware)
            validated = await self.db_client.get_top_strategies_by_composite_score(
                min_score=30, max_score=100, limit=5
            )
            for s in validated:
                params = s.get("parameters", {})
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except Exception:
                        params = {}
                context["successful_patterns"].append(
                    {
                        "entry": params.get("entry_conditions", []),
                        "temporal_score": s.get("short_window_score", "N/A"),
                        "archetype": params.get("archetype", "unknown"),
                    }
                )

        except Exception as e:
            logger.warning(f"{self.name}: Successful patterns fetch: {e}")

        try:
            # Recent strategy names to avoid duplicates
            names = await self.db_client.get_recent_strategy_names(limit=20)
            context["recent_names"] = names

        except Exception as e:
            logger.warning(f"{self.name}: Recent names fetch: {e}")

        try:
            # How many bars we have per symbol (tells Claude data richness)
            from sqlalchemy import text

            async with self.db_client.engine.connect() as conn:
                result = await conn.execute(
                    text("""
                        SELECT symbol, COUNT(*) as bars
                        FROM market_data_l1
                        GROUP BY symbol
                        ORDER BY bars DESC
                        LIMIT 10
                    """)
                )
                context["bars_available"] = {
                    row[0]: row[1] for row in result.fetchall()
                }
        except Exception as e:
            logger.warning(f"{self.name}: Bars count fetch: {e}")

        return context

    # =========================================================
    # PROMPT BUILDER — real context, chain-of-thought
    # =========================================================
    def _build_prompt(self, context: dict) -> tuple[str, str]:
        asset = context["asset_class"]
        archetype = context["archetype"]
        regime = context["regime"]
        snapshot = context["market_snapshot"]
        failed = context["failed_patterns"]
        successful = context["successful_patterns"]
        recent_names = context["recent_names"]
        bars = context["bars_available"]
        primary_sym = context.get("primary_symbol", "NVDA")

        # Format market snapshot as real numbers
        snapshot_str = (
            "\n".join(f"  {k}: {v}" for k, v in list(snapshot.items())[:15])
            or "  No live features available"
        )

        # Format failure lessons
        if failed:
            failed_lines = []
            for f in failed[:5]:
                wr = f["win_rate"]
                wr_str = f"{wr:.0%}" if isinstance(wr, (int, float)) else str(wr)
                failed_lines.append(
                    f"  Entry: {f['entry']} | Sharpe: {f['sharpe']} | "
                    f"Trades: {f['trades']} | Win rate: {wr_str} | "
                    f"Failed because: {f['reason']}"
                )
            failed_str = "\n".join(failed_lines)
        else:
            failed_str = "  No failed strategies yet."

        # Format success lessons
        if successful:
            success_str = "\n".join(
                f"  Entry: {s['entry']} | Sharpe: {s['sharpe']} | "
                f"Type: {s['archetype']}"
                for s in successful[:3]
            )
        else:
            success_str = "  No validated strategies yet."

        # Data richness context
        bars_str = (
            "\n".join(f"  {sym}: {count} bars" for sym, count in list(bars.items())[:8])
            or "  No bar counts available"
        )

        names_str = ", ".join(recent_names[:10]) if recent_names else "none yet"

        system_prompt = """You are a senior quantitative researcher at a proprietary trading fund.
You design algorithmic trading strategies that run on 1-minute OHLCV bar data.
Your strategies must be mathematically sound and produce real trading signals.

You think step by step:
1. Analyze the current market conditions
2. Identify why recent strategies failed
3. Reason about what market inefficiency to exploit
4. Design conditions that will actually trigger on the available data
5. Validate your logic before outputting

Your output will be converted directly to executable Python code.
Entry/exit conditions must be pure Python boolean comparisons — no English prose."""

        user_prompt = f"""=== MISSION ===
Design ONE {archetype.upper().replace("_", " ")} strategy for 1-minute {asset.upper()} data.

=== CURRENT MARKET STATE (real values from live data) ===
Primary symbol: {primary_sym}
Market regime: {regime}
Live feature snapshot:
{snapshot_str}

=== DATA AVAILABLE FOR BACKTESTING ===
{bars_str}
Use this to calibrate how many trades your strategy should generate.
With ~2800 bars, a strategy triggering every 50 bars = ~56 trades.
Target: 20-100 trades over the available data period.

=== WHAT HAS FAILED (learn from these mistakes) ===
{failed_str}

=== WHAT HAS WORKED ===
{success_str}

=== DESIGN CONSTRAINTS ===
Asset class: {asset}
Archetype: {archetype}

Approved features (ONLY use these exact names):
  returns, rsi_14, macd, macd_signal,
  ema_12, ema_26, sma_20,
  bollinger_upper, bollinger_lower,
  vwap, close, open, high, low, volume,
  price_vs_vwap_pct, ema_spread_pct,
  relative_volume, bollinger_band_position,
  volatility_regime, trend_strength

Realistic value ranges for {asset} 1-minute data:
  rsi_14:              0-100 (typical range: 30-70)
  returns:             {"-0.003 to 0.003" if asset == "equity" else "-0.008 to 0.008"}
  price_vs_vwap_pct:   {"-0.005 to 0.005" if asset == "equity" else "-0.015 to 0.015"}
  relative_volume:     0.2 to 4.0 (>1.5 = elevated, >2.5 = very high)
  ema_spread_pct:      {"-0.005 to 0.005" if asset == "equity" else "-0.01 to 0.01"}
  bollinger_band_pos:  0.0 to 1.0 (0=lower band, 1=upper band, 0.5=middle)
  volatility_regime:   0.3 to 2.5 (>1.3 = elevated vol)
  trend_strength:      0.0 to 0.008

Condition format rules:
  CORRECT: "rsi_14 < 35"
  CORRECT: "price_vs_vwap_pct < -0.002"
  CORRECT: "relative_volume > 1.5"
  CORRECT: "bollinger_band_position < 0.2"
  CORRECT: "ema_spread_pct > 0.001"
  WRONG: "For LONG: close breaks above..."
  WRONG: "when RSI crosses below 30"
  WRONG: "if trend is bullish"
  WRONG: "rsi_14 < 20" (too extreme — triggers almost never)
  WRONG: "relative_volume > 5.0" (almost never happens)

Avoid these recently used strategy names: {names_str}

=== YOUR THINKING PROCESS ===
Before outputting JSON, think through:
1. What market condition does {archetype} exploit right now given regime={regime}?
2. Which 2-3 features best capture this condition?
3. What threshold values will trigger realistically (check the ranges above)?
4. Will entry AND exit conditions both fire with enough frequency?
5. Why would this strategy make money rather than lose it?

=== OUTPUT FORMAT ===
Output ONLY valid JSON. No markdown, no explanation, no code fences.
{{
  "strategy_name": "unique_descriptive_snake_case_name",
  "hypothesis": "precise one-sentence explanation of the market inefficiency",
  "reasoning": "2-3 sentences explaining WHY this works and HOW you calibrated the thresholds",
  "entry_conditions": ["feature > threshold", "feature < threshold"],
  "exit_conditions": ["feature > threshold"],
  "stop_loss": "0.5% below entry",
  "take_profit": "1.0% above entry",
  "position_sizing": "10% of portfolio",
  "timeframe": "1m",
  "asset_class": "{asset}",
  "expected_sharpe": 1.2,
  "expected_win_rate": 0.52,
  "expected_trades_per_week": 25,
  "risk_level": "medium",
  "tags": ["{archetype}", "{asset}"]
}}"""

        return system_prompt, user_prompt

    # =========================================================
    # GENERATION — 3000 tokens, chain-of-thought
    # =========================================================
    async def _generate_strategy(
        self, context: dict
    ) -> tuple[dict | None, str | None, str | None]:

        system_prompt, user_prompt = self._build_prompt(context)

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw = response.content[0].text
            logger.info(f"{self.name}: Claude response:\n{raw[:500]}...")

            # Extract JSON
            cleaned = raw.strip()
            if "```" in cleaned:
                start = cleaned.find("\n", cleaned.find("```")) + 1
                end = cleaned.rfind("```")
                cleaned = cleaned[start:end].strip()

            first = cleaned.find("{")
            last = cleaned.rfind("}")
            if first == -1 or last == -1:
                raise ValueError("No JSON found in response")

            spec = json.loads(cleaned[first : last + 1])
            spec["asset_class"] = context["asset_class"]
            spec = normalize_strategy(spec)

            valid, reason = validate_strategy(spec)
            if not valid:
                raise ValueError(f"Validation failed: {reason}")

            logger.info(
                f"{self.name}: Generated '{spec['strategy_name']}' | "
                f"entry={spec.get('entry_conditions')} | "
                f"reasoning={spec.get('reasoning', 'N/A')[:100]}"
            )

            await self.db_client.log(
                agent_id=self.agent_id,
                level="INFO",
                message=f"Strategy generated: {spec['strategy_name']}",
                metadata={
                    "strategy_name": spec["strategy_name"],
                    "archetype": self._archetype,
                    "asset_class": context["asset_class"],
                    "regime": context["regime"],
                    "entry_conditions": spec.get("entry_conditions"),
                    "reasoning": spec.get("reasoning", ""),
                    "tokens_used": response.usage.output_tokens,
                },
            )

            return spec, user_prompt, raw

        except json.JSONDecodeError as e:
            logger.error(f"{self.name}: JSON parse error: {e}\nRaw: {raw[:300]}")
            return None, user_prompt, None

        except Exception as e:
            logger.error(f"{self.name}: Generation error: {e}", exc_info=True)
            # Fallback to local template
            return await self._generate_local(context)

    async def _generate_local(self, context: dict) -> tuple[dict, None, None]:
        """Fallback when Claude fails — uses proven template conditions."""
        asset = context["asset_class"]
        archetype = context["archetype"]
        suffix = datetime.utcnow().strftime("%H%M%S")

        TEMPLATES = {
            ("equity", "momentum"): {
                "entry": ["ema_spread_pct > 0.001", "relative_volume > 1.3"],
                "exit": ["ema_spread_pct < 0.0", "rsi_14 > 68"],
            },
            ("equity", "mean_reversion"): {
                "entry": ["bollinger_band_position < 0.15", "rsi_14 < 38"],
                "exit": ["bollinger_band_position > 0.75"],
            },
            ("equity", "breakout"): {
                "entry": ["bollinger_band_position > 0.92", "relative_volume > 1.8"],
                "exit": ["rsi_14 > 72"],
            },
            ("equity", "trend_following"): {
                "entry": ["ema_12 > ema_26", "price_vs_vwap_pct > 0.001"],
                "exit": ["ema_12 < ema_26"],
            },
            ("equity", "volatility_regime"): {
                "entry": ["volatility_regime > 1.4", "bollinger_band_position < 0.3"],
                "exit": ["volatility_regime < 0.9", "rsi_14 > 60"],
            },
            ("crypto", "momentum"): {
                "entry": ["ema_spread_pct > 0.002", "relative_volume > 1.5"],
                "exit": ["ema_spread_pct < 0.0", "rsi_14 > 70"],
            },
            ("crypto", "mean_reversion"): {
                "entry": ["rsi_14 < 32", "price_vs_vwap_pct < -0.004"],
                "exit": ["rsi_14 > 58"],
            },
            ("crypto", "breakout"): {
                "entry": ["bollinger_band_position > 0.9", "relative_volume > 2.0"],
                "exit": ["rsi_14 > 75"],
            },
            ("crypto", "trend_following"): {
                "entry": ["ema_12 > ema_26", "trend_strength > 0.001"],
                "exit": ["ema_12 < ema_26"],
            },
            ("crypto", "volatility_regime"): {
                "entry": ["volatility_regime > 1.5", "rsi_14 < 40"],
                "exit": ["volatility_regime < 0.8"],
            },
        }

        t = TEMPLATES.get(
            (asset, archetype),
            {"entry": ["ema_12 > ema_26"], "exit": ["ema_12 < ema_26"]},
        )

        spec = {
            "strategy_name": f"{archetype}_{asset}_local_{suffix}",
            "hypothesis": f"Local template: {archetype} on {asset} 1m data",
            "reasoning": "Fallback template — Claude unavailable",
            "entry_conditions": t["entry"],
            "exit_conditions": t["exit"],
            "stop_loss": "0.5% below entry",
            "take_profit": "1.0% above entry",
            "position_sizing": "10% of portfolio",
            "timeframe": "1m",
            "asset_class": asset,
            "expected_sharpe": 1.0,
            "expected_win_rate": 0.5,
            "expected_trades_per_week": 20,
            "risk_level": "medium",
            "tags": [archetype, asset, "local_fallback"],
        }
        return spec, None, None


async def main():
    print("=== IDEATOR MAIN STARTED ===", flush=True)
    db_client = TimescaleClient(settings.database_url)
    await db_client.connect()
    redis_client = Redis.from_url(settings.redis_url)

    agents = [IdeatorAgent(i, TEMP_MAP[i], redis_client, db_client) for i in range(5)]
    await asyncio.gather(*(agent.start() for agent in agents))
    await asyncio.Event().wait()


if __name__ == "__main__":
    print("=== IDEATOR EXECUTION HIT ===", flush=True)
    asyncio.run(main())
