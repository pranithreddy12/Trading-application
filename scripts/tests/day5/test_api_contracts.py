from datetime import datetime

import pytest

from atlas.api.services.copy_service import CopyService
from atlas.api.services.risk_service import RiskService


class FakeResult:
    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows or []
        self._scalar = scalar_value

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar


class FakeConn:
    def __init__(self, script):
        self.script = script

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "COUNT(*) FROM copy_leader_accounts" in sql:
            return FakeResult(scalar_value=self.script["leader_count"])
        if "COUNT(*) FROM copy_follower_accounts" in sql:
            return FakeResult(scalar_value=self.script["follower_count"])
        if "FROM copy_execution_log" in sql and "SELECT\n                id" in sql:
            return FakeResult(rows=self.script["copy_logs"])
        if "FROM copy_leader_accounts" in sql and "SELECT leader_id" in sql:
            return FakeResult(rows=self.script["leaders"])
        if "FROM copy_follower_accounts" in sql and "SELECT" in sql:
            return FakeResult(rows=self.script["followers"])
        if "COUNT(*) FROM copy_execution_log WHERE status = 'filled'" in sql:
            return FakeResult(scalar_value=self.script["filled"])
        if "COUNT(*) FROM copy_execution_log WHERE status = 'failed'" in sql:
            return FakeResult(scalar_value=self.script["failed"])
        if "AVG(latency_ms)" in sql:
            return FakeResult(scalar_value=self.script["avg_latency"])
        return FakeResult()


class FakeEngine:
    def __init__(self, script):
        self.script = script

    def connect(self):
        return FakeConn(self.script)


class FakeDB:
    def __init__(self, script):
        self.engine = FakeEngine(script)


@pytest.mark.asyncio
async def test_contract_copy_logs_matches_db_rows():
    now = datetime.utcnow()
    script = {
        "copy_logs": [
            ("id1", "l1", "f1", "leader", "follower", "BTCUSDT", "buy", 1.0, 0.5, 42, "filled", None, now)
        ],
        "leaders": [],
        "followers": [],
        "filled": 0,
        "failed": 0,
        "avg_latency": 0,
        "leader_count": 0,
        "follower_count": 0,
    }
    svc = CopyService(FakeDB(script), RiskService())

    payload = await svc.get_copy_logs(limit=10)

    assert payload["count"] == 1
    assert payload["logs"][0]["id"] == "id1"
    assert payload["logs"][0]["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_contract_leaders_matches_db_rows():
    now = datetime.utcnow()
    script = {
        "copy_logs": [],
        "leaders": [("lid", "acc1", "sim", True, now, {"tier": "gold"})],
        "followers": [],
        "filled": 0,
        "failed": 0,
        "avg_latency": 0,
        "leader_count": 1,
        "follower_count": 0,
    }
    svc = CopyService(FakeDB(script), RiskService())

    payload = await svc.get_leaders()

    assert payload["count"] == 1
    assert payload["leaders"][0]["leader_id"] == "lid"


@pytest.mark.asyncio
async def test_contract_followers_matches_db_rows():
    now = datetime.utcnow()
    script = {
        "copy_logs": [],
        "leaders": [],
        "followers": [("fid", "lid", "acc2", "sim", 0.7, 0.1, True, now, {"mode": "copy"})],
        "filled": 0,
        "failed": 0,
        "avg_latency": 0,
        "leader_count": 0,
        "follower_count": 1,
    }
    svc = CopyService(FakeDB(script), RiskService())

    payload = await svc.get_followers()

    assert payload["count"] == 1
    assert payload["followers"][0]["follower_id"] == "fid"


@pytest.mark.asyncio
async def test_contract_healthful_copy_status_truthful():
    script = {
        "copy_logs": [],
        "leaders": [],
        "followers": [],
        "filled": 12,
        "failed": 2,
        "avg_latency": 35,
        "leader_count": 3,
        "follower_count": 11,
    }
    svc = CopyService(FakeDB(script), RiskService())

    payload = await svc.get_copy_status()

    assert payload["filled_orders"] == 12
    assert payload["failures"] == 2
    assert payload["active_leaders"] == 3
    assert payload["active_followers"] == 11
