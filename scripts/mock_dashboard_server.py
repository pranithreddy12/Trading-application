#!/usr/bin/env python3
"""
Minimal HTTP server that simulates selected dashboard API endpoints with dynamic sample data.
Run with: python scripts/mock_dashboard_server.py
"""

import json
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8001


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, status=200):
        b = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        t = time.time()
        # dynamic values
        if path == "/dashboard/api/overview":
            obj = {
                "system": {"status": random.choice(["ok", "degraded", "healthy"])},
                "strategies": {
                    "total": random.randint(10, 50),
                    "by_status": {"active": random.randint(5, 20)},
                },
                "lineage": {
                    "total_events": random.randint(1000, 5000),
                    "total_traces": random.randint(100, 500),
                },
                "patterns": {"total": random.randint(0, 200)},
                "portfolio": {
                    "intel_runs": random.randint(0, 10),
                    "allocations": random.randint(1, 6),
                },
                "validation": {"walk_forward": 1, "monte_carlo": 0},
                "monitoring": {"drift_events": random.randint(0, 5)},
                "scouts": {"internal_signals": random.randint(0, 200)},
            }
            self._send(obj)
            return
        if path == "/dashboard/api/scouts":
            obj = {
                "internal": {
                    "by_source": {
                        "regime_scout": random.randint(0, 100),
                        "liquidity_scout": random.randint(0, 100),
                    },
                    "total_signals": random.randint(0, 200),
                    "recent": [],
                },
                "external": {
                    "by_source": {"news": random.randint(0, 50)},
                    "total_signals": random.randint(0, 100),
                    "recent": [],
                },
            }
            self._send(obj)
            return
        if path == "/dashboard/api/governance/system-health":
            obj = {
                "composite_score": random.random() * 100,
                "system_mode": random.choice(["prod", "dev", "maintenance"]),
                "n_degraded": random.randint(0, 2),
                "n_total": 10,
            }
            self._send(obj)
            return
        if path == "/dashboard/api/governance/deployments":
            n = random.randint(0, 8)
            deployments = []
            for i in range(n):
                deployments.append(
                    {
                        "id": f"d{i}",
                        "status": random.choice(["running", "failed", "completed"]),
                    }
                )
            obj = {"deployments": deployments, "total_deployments": len(deployments)}
            self._send(obj)
            return
        if path == "/dashboard/api/traces":
            limit = int(qs.get("limit", [20])[0])
            recent = []
            for i in range(min(limit, 20)):
                recent.append(
                    {
                        "trace_id": f"t{i}",
                        "stage": "run",
                        "status": random.choice(["completed", "failed"]),
                        "actor": "system",
                        "strategy_id": f"s{i}",
                        "created_at": time.time(),
                    }
                )
            obj = {
                "recent_events": recent,
                "most_active_traces": {
                    f"t{i}": random.randint(1, 50) for i in range(5)
                },
            }
            self._send(obj)
            return
        if path == "/dashboard/api/strategies/rejected":
            reasons_pool = [
                {
                    "reason": "HIGH TRADE FREQUENCY RISK: >150 estimated trades on 1m data. Rejected — strategies with high frequency will not survive execution costs.",
                    "source": "ideator",
                    "archetype": "momentum",
                    "asset": "BTC/USD",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "single feature family only (trend)",
                    "source": "ideator",
                    "archetype": "mean_reversion",
                    "asset": "ETH/USD",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": f"exact clone overlap {random.uniform(0.7, 0.99):.0%} with breakout",
                    "source": "ideator",
                    "archetype": "breakout",
                    "asset": "AAPL",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "incompatible conditions",
                    "source": "ideator",
                    "archetype": "momentum",
                    "asset": "BTC/USD",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "threshold realism check failed",
                    "source": "ideator",
                    "archetype": "mean_reversion",
                    "asset": "ETH/USD",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "validation failed — deployment gate not passed",
                    "source": "deployment_governor",
                    "archetype": "breakout",
                    "asset": "TSLA",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "total_exposure_limit_exceeded",
                    "source": "copy_capital_allocator",
                    "archetype": "momentum",
                    "asset": "BTC/USD",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "below_minimum_order_value",
                    "source": "copy_capital_allocator",
                    "archetype": "mean_reversion",
                    "asset": "SOL/USD",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "max_open_positions reached",
                    "source": "risk_controller",
                    "archetype": "breakout",
                    "asset": "ETH/USD",
                    "timestamp": t - random.randint(60, 3600),
                },
                {
                    "reason": "max_single_position_pct breached",
                    "source": "risk_controller",
                    "archetype": "momentum",
                    "asset": "AAPL",
                    "timestamp": t - random.randint(60, 3600),
                },
            ]
            n = random.randint(3, len(reasons_pool))
            rejected = random.sample(reasons_pool, n)
            by_source = {}
            for r in rejected:
                by_source.setdefault(r["source"], 0)
                by_source[r["source"]] += 1
            self._send(
                {
                    "total_rejected": len(rejected),
                    "by_source": by_source,
                    "rejected_strategies": rejected,
                }
            )
            return
        if path == "/dashboard/api/strategies":
            self._send(
                {
                    "total": random.randint(10, 50),
                    "active": random.randint(5, 20),
                    "rejected": random.randint(3, 15),
                    "by_status": {
                        "pending_code": random.randint(2, 10),
                        "active": random.randint(3, 15),
                        "rejected": random.randint(3, 15),
                    },
                }
            )
            return
        if path == "/dashboard/api/patterns":
            by_type = {
                "mean_reversion": random.randint(0, 20),
                "momentum": random.randint(0, 20),
            }
            patterns = [
                {
                    "type": "momentum",
                    "archetype": "A",
                    "composite_score": random.random() * 100,
                    "confidence": random.random(),
                    "recommendation": "watch",
                }
                for _ in range(5)
            ]
            self._send({"by_type": by_type, "patterns": patterns})
            return
        # default 404
        self._send({"error": "not found"}, status=404)


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Mock dashboard server running on http://127.0.0.1:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        print("Shutting down")
