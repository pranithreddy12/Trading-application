"""
update_dashboard_api.py — Adds:
1. code, parameters, prompt to strategy detail response
2. /dashboard/api/agents/live endpoint from Redis heartbeats
"""

import re
import sys

ROUTER_PATH = "atlas/dashboard/router.py"

with open(ROUTER_PATH, "r", encoding="utf-8") as f:
    content = f.read()

changes = 0

# === 1. Add code, parameters, prompt to strategy detail endpoint ===
old_select = (
    "                       compile_error, trace_id, generation_batch,\n"
    "                       created_at\n"
    "                FROM strategies\n"
    "                WHERE id = :sid"
)
new_select = (
    "                       compile_error, trace_id, generation_batch,\n"
    "                       created_at, code, parameters, prompt\n"
    "                FROM strategies\n"
    "                WHERE id = :sid"
)

if old_select in content and "code, parameters, prompt" not in content:
    content = content.replace(old_select, new_select)
    print("Updated strategy detail SELECT to include code, parameters, prompt")
    changes += 1

# Add parameters parsing block
old_params_section = """            row = r.fetchone()
            if not row:
                return {"error": f"Strategy {strategy_id} not found"}

            strategy = {"""

new_params_section = """            row = r.fetchone()
            if not row:
                return {"error": f"Strategy {strategy_id} not found"}

            params_raw = row[13]
            if isinstance(params_raw, str):
                try:
                    params_parsed = json.loads(params_raw)
                except Exception:
                    params_parsed = {}
            else:
                params_parsed = params_raw or {}

            strategy = {"""

if old_params_section in content and "params_raw = row[13]" not in content:
    content = content.replace(old_params_section, new_params_section)
    print("Added parameters parsing block")
    changes += 1

# Add code, parameters, prompt to strategy dict
old_dict_end = (
    '                "created_at": str(row[11]) if row[11] else "",\n'
    "            }\n"
    "\n"
    "            # 2. Backtest results"
)
new_dict_end = (
    '                "created_at": str(row[11]) if row[11] else "",\n'
    '                "code": row[12],\n'
    '                "parameters": params_parsed,\n'
    '                "prompt": row[14],\n'
    "            }\n"
    "\n"
    "            # 2. Backtest results"
)

if old_dict_end in content and '"code": row[12]' not in content:
    content = content.replace(old_dict_end, new_dict_end)
    print("Added code/parameters/prompt to strategy dict")
    changes += 1

# === 2. Add live agents endpoint ===
live_agents_endpoint = """

@router.get("/dashboard/api/agents/live")
async def dashboard_agents_live():
    \"\"\"Read live agent statuses from Redis heartbeats.\"\"\"
    try:
        from redis.asyncio import Redis
        from atlas.config.settings import get_settings as get_stg
        stg = get_stg()
        redis_client = Redis.from_url(stg.redis_url)
        try:
            cursor = 0
            live_agents = []
            while True:
                cursor, keys = await redis_client.scan(cursor=cursor, match="agent:*", count=100)
                for key in keys:
                    data = await redis_client.hgetall(key)
                    if data:
                        agent_id = key.decode() if isinstance(key, bytes) else key
                        agent_id = agent_id.replace("agent:", "", 1)
                        decoded = {}
                        for k, v in data.items():
                            k_str = k.decode() if isinstance(k, bytes) else k
                            v_str = v.decode() if isinstance(v, bytes) else v
                            decoded[k_str] = v_str
                        live_agents.append({
                            "agent_id": agent_id,
                            "name": decoded.get("name", "unknown"),
                            "type": decoded.get("agent_type", ""),
                            "layer": decoded.get("layer", ""),
                            "status": decoded.get("status", "stopped"),
                            "advisory_only": decoded.get("advisory_only", "false"),
                        })
                if cursor == 0:
                    break
            return {"agents": live_agents, "count": len(live_agents)}
        finally:
            try:
                await redis_client.aclose()
            except Exception:
                pass
    except Exception as exc:
        logger.error(f"Dashboard live agents error: {exc}")
        return {"error": str(exc), "agents": [], "count": 0}
"""

# Insert before the STRATEGY DETAIL section
section_marker = "# ================================================================\n# STRATEGY DETAIL"

if section_marker in content and "agents/live" not in content:
    content = content.replace(
        section_marker,
        live_agents_endpoint + "\n" + section_marker
    )
    print("Added live agents endpoint")
    changes += 1

with open(ROUTER_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nRouter.py update complete: {changes} changes applied")
sys.exit(0)
