print("=== IDEATOR V2 LOADED ===", flush=True)

import asyncio
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
    "momentum", "mean_reversion",
    "breakout", "volatility_regime", "trend_following",
]

TEMP_MAP = [0.4, 0.7, 0.5, 0.85, 1.0]

ALLOWED_FEATURES = [
    "returns", "rsi_14", "macd", "macd_signal",
    "ema_12", "ema_26", "sma_20",
    "bollinger_upper", "bollinger_lower",
    "vwap", "close", "open", "high", "low", "volume",
    "price_vs_vwap_pct", "ema_spread_pct",
    "relative_volume", "bollinger_band_position",
    "volatility_regime", "trend_strength",
]

# Proven fallback templates — these DO generate trades
LOCAL_TEMPLATES = {
    ("equity", "momentum"):
        (["ema_spread_pct > 0.001", "relative_volume > 1.3"],
         ["ema_spread_pct < 0.0", "rsi_14 > 68"]),
    ("equity", "mean_reversion"):
        (["bollinger_band_position < 0.15", "rsi_14 < 38"],
         ["bollinger_band_position > 0.75"]),
    ("equity", "breakout"):
        (["bollinger_band_position > 0.92", "relative_volume > 1.8"],
         ["rsi_14 > 72"]),
    ("equity", "trend_following"):
        (["ema_12 > ema_26", "price_vs_vwap_pct > 0.001"],
         ["ema_12 < ema_26"]),
    ("equity", "volatility_regime"):
        (["volatility_regime > 1.4", "bollinger_band_position < 0.3"],
         ["volatility_regime < 0.9"]),
    ("crypto", "momentum"):
        (["ema_spread_pct > 0.002", "relative_volume > 1.5"],
         ["ema_spread_pct < 0.0", "rsi_14 > 70"]),
    ("crypto", "mean_reversion"):
        (["rsi_14 < 32", "price_vs_vwap_pct < -0.004"],
         ["rsi_14 > 58"]),
    ("crypto", "breakout"):
        (["bollinger_band_position > 0.9", "relative_volume > 2.0"],
         ["rsi_14 > 75"]),
    ("crypto", "trend_following"):
        (["ema_12 > ema_26", "trend_strength > 0.001"],
         ["ema_12 < ema_26"]),
    ("crypto", "volatility_regime"):
        (["volatility_regime > 1.5", "rsi_14 < 40"],
         ["volatility_regime < 0.8"]),
}


class IdeatorAgentV2(BaseAgent):
    """
    Optimized ideator — real context, compressed prompts, cached DB.
    max_tokens=1500, context refreshed every 10 cycles.
    """

    def __init__(
        self,
        instance_id: int,
        temperature: float,
        redis_client: Redis,
        db_client: TimescaleClient,
        mode: str = "rich",  # "rich" | "lean" | "local"
    ):
        super().__init__(
            name=f"IdeatorV2_{instance_id}_{mode[:1].upper()}",
            agent_type="ideator",
            layer="L2",
            redis_client=redis_client,
        )
        self.instance_id = instance_id
        self.temperature = max(0.0, min(1.0, temperature))
        self.mode = mode
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=30.0),
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

        # Context cache — refresh every 10 cycles
        self._ctx_cache: dict = {}
        self._ctx_cycle: int = 0
        self._CACHE_TTL: int = 10

    async def stop(self):
        await super().stop()
        await self.http_client.aclose()

    async def run(self):
        logger.info(
            f"{self.name}: START mode={self.mode} "
            f"arch={self._archetype} asset={self._asset_class}"
        )
        while True:
            try:
                # Refresh context every 10 cycles only
                if self._ctx_cycle % self._CACHE_TTL == 0:
                    self._ctx_cache = await self._build_context()
                    logger.debug(f"{self.name}: Context refreshed")
                self._ctx_cycle += 1

                spec, prompt, raw = await self._generate(self._ctx_cache)

                if not spec:
                    await asyncio.sleep(15)
                    continue

                # Dedup
                sig = compute_strategy_signature(spec)
                existing = await self.db_client.get_strategy_signatures(
                    limit=500
                )
                if sig in existing:
                    logger.info(f"{self.name}: Duplicate — skip")
                    await asyncio.sleep(5)
                    continue

                strategy_id = await self.db_client.save_strategy(
                    spec,
                    status="pending_code",
                    author_agent=self.name,
                    prompt=prompt,
                    raw_response=raw,
                    strategy_signature=sig,
                )

                logger.info(
                    f"{self.name}: ✅ {spec['strategy_name']} "
                    f"entry={spec.get('entry_conditions')}"
                )

                await self.messaging.publish(
                    Channel.STRATEGY_SIGNALS,
                    {"event": "new_strategy",
                     "strategy_id": strategy_id,
                     "agent": self.name},
                )

                # Lean agents run faster
                sleep = 8 if self.mode == "lean" else 12
                await asyncio.sleep(sleep)

            except Exception as e:
                logger.error(f"{self.name}: {e}", exc_info=True)
                await asyncio.sleep(10)

    # ─────────────────────────────────────────────────────────
    # CONTEXT — cached, compressed
    # ─────────────────────────────────────────────────────────
    async def _build_context(self) -> dict:
        ctx = {
            "archetype": self._archetype,
            "asset_class": self._asset_class,
            "regime": "neutral",
            "snapshot_line": "",
            "failure_summary": "No failures yet.",
            "success_summary": "No validated strategies yet.",
            "recent_names": [],
        }

        try:
            symbols = (
                ["NVDA", "SPY", "AAPL", "TSLA"]
                if self._asset_class == "equity"
                else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
            )
            features = await self.db_client.get_latest_features(
                symbols, limit=1
            )
            if features:
                best = max(
                    features.items(),
                    key=lambda x: len(x[1]) if isinstance(x[1], dict) else 0,
                )
                sym, vals = best
                if isinstance(vals, dict):
                    # Compressed: just key values as one line
                    picks = {
                        k: round(float(v), 4)
                        for k, v in vals.items()
                        if k in [
                            "rsi_14", "ema_spread_pct",
                            "bollinger_band_position",
                            "relative_volume", "volatility_regime",
                            "price_vs_vwap_pct",
                        ] and v is not None
                    }
                    ctx["snapshot_line"] = (
                        f"{sym}: "
                        + ", ".join(f"{k}={v}" for k, v in picks.items())
                    )
                    rsi = float(vals.get("rsi_14", 50))
                    vol = float(vals.get("volatility_regime", 1.0))
                    ema = float(vals.get("ema_spread_pct", 0))
                    if rsi < 35:
                        ctx["regime"] = "oversold"
                    elif rsi > 65:
                        ctx["regime"] = "overbought"
                    elif vol > 1.4:
                        ctx["regime"] = "high_volatility"
                    elif abs(ema) > 0.003:
                        ctx["regime"] = "trending"
                    else:
                        ctx["regime"] = "ranging"

        except Exception as e:
            logger.warning(f"{self.name}: Feature fetch: {e}")

        try:
            # Summarize failures as ONE compressed line
            failed = await self.db_client.get_strategies_with_backtest(
                status="failed_validation", limit=8
            )
            if failed:
                reasons = []
                zero_trade_count = 0
                low_sharpe_count = 0
                for s in failed:
                    params = s.get("parameters", {})
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except Exception:
                            params = {}
                    notes = params.get("validation_notes", "")
                    trades = s.get("total_trades", 0) or 0
                    sharpe = s.get("sharpe_ratio", 0) or 0
                    if int(trades) < 3:
                        zero_trade_count += 1
                    if float(sharpe) < 0:
                        low_sharpe_count += 1
                    if "trades" in str(notes):
                        reasons.append("too few trades")
                    elif "sharpe" in str(notes):
                        reasons.append("negative sharpe")
                    elif "drawdown" in str(notes):
                        reasons.append("high drawdown")

                parts = []
                if zero_trade_count > 0:
                    parts.append(
                        f"{zero_trade_count}/{len(failed)} had <3 trades "
                        f"(thresholds too extreme)"
                    )
                if low_sharpe_count > 0:
                    parts.append(
                        f"{low_sharpe_count}/{len(failed)} had negative sharpe"
                    )
                ctx["failure_summary"] = (
                    "; ".join(parts) if parts
                    else f"{len(failed)} failed: " + ", ".join(set(reasons))
                )

        except Exception as e:
            logger.warning(f"{self.name}: Failure fetch: {e}")

        try:
            # Summarize successes as ONE compressed line
            wins = await self.db_client.get_top_strategies_by_sharpe(
                min_sharpe=0.1, max_sharpe=10.0, limit=3
            )
            if wins:
                lines = []
                for w in wins:
                    params = w.get("parameters", {})
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except Exception:
                            params = {}
                    entry = params.get("entry_conditions", [])
                    sh = round(float(w.get("sharpe_ratio", 0)), 2)
                    lines.append(f"entry={entry} sharpe={sh}")
                ctx["success_summary"] = " | ".join(lines)

        except Exception as e:
            logger.warning(f"{self.name}: Success fetch: {e}")

        try:
            ctx["recent_names"] = (
                await self.db_client.get_recent_strategy_names(limit=15)
            )
        except Exception:
            pass

        return ctx

    # ─────────────────────────────────────────────────────────
    # GENERATE — routes by mode
    # ─────────────────────────────────────────────────────────
    async def _generate(
        self, ctx: dict
    ) -> tuple[dict | None, str | None, str | None]:
        if self.mode == "local":
            return await self._generate_local(ctx)
        elif self.mode == "lean":
            return await self._call_claude(ctx, max_tokens=800)
        else:  # rich
            return await self._call_claude(ctx, max_tokens=1500)

    # ─────────────────────────────────────────────────────────
    # CLAUDE CALL — 800 or 1500 tokens
    # ─────────────────────────────────────────────────────────
    async def _call_claude(
        self, ctx: dict, max_tokens: int
    ) -> tuple[dict | None, str | None, str | None]:

        asset = ctx["asset_class"]
        archetype = ctx["archetype"]
        regime = ctx["regime"]
        recent = ", ".join(ctx["recent_names"][:8]) or "none"

        returns_range = (
            "-0.003 to 0.003" if asset == "equity"
            else "-0.008 to 0.008"
        )

        system_prompt = (
            f"You are a quant researcher designing 1-minute {asset} "
            f"intraday strategies. Output ONLY valid JSON. "
            f"Reason internally. No markdown, no prose outside JSON."
        )

        user_prompt = f"""Design ONE {archetype} strategy for 1-minute {asset} data.

Market: {ctx['snapshot_line'] or 'no live data'}
Regime: {regime}

Recent failures: {ctx['failure_summary']}
Working strategies: {ctx['success_summary']}
Avoid names: {recent}

APPROVED FEATURES (use ONLY these exact names):
  rsi_14, macd, macd_signal, ema_12, ema_26, sma_20,
  bollinger_upper, bollinger_lower, vwap,
  returns, close, volume,
  price_vs_vwap_pct, ema_spread_pct,
  relative_volume, bollinger_band_position,
  volatility_regime, trend_strength

REALISTIC THRESHOLDS for {asset} 1m:
  rsi_14: 30-70 range (NOT <20 or >80 — too rare)
  returns: {returns_range} per bar
  relative_volume: 1.2-2.5 (NOT >4 — too rare)
  bollinger_band_position: 0.1-0.9
  ema_spread_pct: 0.0005-0.005
  volatility_regime: 0.8-2.0

CRITICAL: Each condition must trigger on 5-15% of bars minimum.
Too restrictive = 0 trades = automatic failure.

✅ CORRECT conditions: "rsi_14 < 38", "relative_volume > 1.4",
   "bollinger_band_position < 0.2", "ema_spread_pct > 0.001"
❌ WRONG: "For LONG: close breaks above..." (natural language)
❌ WRONG: "rsi_14 < 15" (too extreme, never fires)

Output ONLY this JSON:
{{"strategy_name":"unique_name","hypothesis":"one sentence",
"reasoning":"why these thresholds trigger realistically",
"entry_conditions":["feature op value","feature op value"],
"exit_conditions":["feature op value"],
"stop_loss":"0.5% below entry","take_profit":"1.0% above entry",
"position_sizing":"10% of portfolio","timeframe":"1m",
"asset_class":"{asset}","expected_sharpe":1.2,
"expected_win_rate":0.52,"risk_level":"medium",
"tags":["{archetype}","{asset}"]}}"""

        try:
            resp = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = resp.content[0].text
            logger.info(f"{self.name}: Raw ({max_tokens}t):\n{raw[:400]}")

            # Extract JSON
            cleaned = raw.strip()
            if "```" in cleaned:
                start = cleaned.find("\n", cleaned.find("```")) + 1
                end = cleaned.rfind("```")
                cleaned = cleaned[start:end].strip()
            f = cleaned.find("{")
            l = cleaned.rfind("}")
            if f == -1:
                raise ValueError("No JSON in response")

            spec = json.loads(cleaned[f:l+1])
            spec["asset_class"] = asset
            spec = normalize_strategy(spec)

            valid, reason = validate_strategy(spec)
            if not valid:
                raise ValueError(f"Invalid: {reason}")

            await self.db_client.log(
                agent_id=self.agent_id,
                level="INFO",
                message=f"Generated: {spec['strategy_name']}",
                metadata={
                    "mode": self.mode,
                    "tokens": max_tokens,
                    "tokens_used": resp.usage.output_tokens,
                    "archetype": archetype,
                    "reasoning": spec.get("reasoning", "")[:200],
                    "entry": spec.get("entry_conditions"),
                },
            )
            return spec, user_prompt, raw

        except json.JSONDecodeError as e:
            logger.warning(f"{self.name}: JSON error: {e}")
            return await self._generate_local(ctx)
        except Exception as e:
            logger.warning(f"{self.name}: Claude error: {e}")
            return await self._generate_local(ctx)

    # ─────────────────────────────────────────────────────────
    # LOCAL FALLBACK — proven templates, always generates trades
    # ─────────────────────────────────────────────────────────
    async def _generate_local(
        self, ctx: dict
    ) -> tuple[dict, None, None]:
        asset = ctx["asset_class"]
        archetype = ctx["archetype"]
        key = (asset, archetype)
        entry, exit_ = LOCAL_TEMPLATES.get(
            key,
            (["ema_12 > ema_26"], ["ema_12 < ema_26"])
        )
        suffix = datetime.utcnow().strftime("%H%M%S")
        spec = {
            "strategy_name": f"{archetype}_{asset}_tmpl_{suffix}",
            "hypothesis": f"Template {archetype} on {asset} 1m",
            "reasoning": "Proven template — guaranteed signal generation",
            "entry_conditions": entry,
            "exit_conditions": exit_,
            "stop_loss": "0.5% below entry",
            "take_profit": "1.0% above entry",
            "position_sizing": "10% of portfolio",
            "timeframe": "1m",
            "asset_class": asset,
            "expected_sharpe": 1.0,
            "expected_win_rate": 0.50,
            "risk_level": "medium",
            "tags": [archetype, asset, "template"],
        }
        return normalize_strategy(spec), None, None


# ─────────────────────────────────────────────────────────────
# MAIN — 2 rich + 2 lean + 1 local
# ─────────────────────────────────────────────────────────────
async def main():
    print("=== IDEATOR V2 MAIN ===", flush=True)
    db = TimescaleClient(settings.database_url)
    await db.connect()
    redis = Redis.from_url(settings.redis_url)

    agents = [
        # 2 rich-context Claude agents (1500 tokens)
        IdeatorAgentV2(0, 0.5, redis, db, mode="rich"),
        IdeatorAgentV2(1, 0.7, redis, db, mode="rich"),
        # 2 lean Claude agents (800 tokens, faster)
        IdeatorAgentV2(2, 0.4, redis, db, mode="lean"),
        IdeatorAgentV2(3, 0.85, redis, db, mode="lean"),
        # 1 local template agent (no API cost, always works)
        IdeatorAgentV2(4, 0.0, redis, db, mode="local"),
    ]

    await asyncio.gather(*(a.start() for a in agents))
    await asyncio.Event().wait()


if __name__ == "__main__":
    print("=== IDEATOR V2 HIT ===", flush=True)
    asyncio.run(main())
