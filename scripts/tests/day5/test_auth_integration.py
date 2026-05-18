import asyncio
import time
from datetime import datetime
import importlib.util

import pytest

if importlib.util.find_spec("bcrypt") is None:
    pytest.skip("bcrypt is required for auth integration tests", allow_module_level=True)

from atlas.api.middleware.auth_middleware import AuthMiddleware
from atlas.api.services.auth_service import APIKey, APIRole
from atlas.api.services.rate_limit_service import RateLimitService


class StubAuthService:
    def __init__(self, key: APIKey | None = None):
        self.key = key
        self.logged = []

    async def validate_key(self, raw_key: str):
        if raw_key == "valid_token":
            return self.key
        return None

    async def check_scope(self, key: APIKey, endpoint: str, method: str = "GET"):
        return key.can_access_endpoint(endpoint, method)

    async def log_request(self, **kwargs):
        self.logged.append(kwargs)


class Req:
    def __init__(self, path="/health", method="GET"):
        self.url = type("U", (), {"path": path})
        self.method = method
        self.headers = {"authorization": "Bearer valid_token"}
        self.client = type("C", (), {"host": "127.0.0.1"})
        self.state = type("S", (), {})()


@pytest.mark.asyncio
async def test_permission_matrix_roles_enforced():
    admin = APIKey("1", "h", APIRole.ADMIN, "u", [], 100, True, datetime.utcnow(), None, None)
    trader = APIKey("2", "h", APIRole.TRADER, "u", [], 100, True, datetime.utcnow(), None, None)
    reader = APIKey("3", "h", APIRole.READ_ONLY, "u", [], 100, True, datetime.utcnow(), None, None)
    follower = APIKey("4", "h", APIRole.FOLLOWER, "u", [], 100, True, datetime.utcnow(), None, None)
    monitor = APIKey("5", "h", APIRole.MONITOR, "u", [], 100, True, datetime.utcnow(), None, None)

    assert admin.can_access_endpoint("/followers", "DELETE")
    assert trader.can_access_endpoint("/copy/order", "POST")
    assert reader.can_access_endpoint("/leaders", "GET")
    assert not reader.can_access_endpoint("/followers", "POST")
    assert follower.can_access_endpoint("/copy/logs", "GET")
    assert not follower.can_access_endpoint("/leaders", "GET")
    assert monitor.can_access_endpoint("/health", "GET")
    assert not monitor.can_access_endpoint("/copy/logs", "GET")


@pytest.mark.asyncio
async def test_failure_mode_missing_auth_header():
    key = APIKey("2", "h", APIRole.TRADER, "u", [], 100, True, datetime.utcnow(), None, None)
    mw = AuthMiddleware(StubAuthService(key))
    req = Req()
    req.headers = {}

    with pytest.raises(Exception):
        await mw.verify_token(req)


@pytest.mark.asyncio
async def test_rate_limit_role_quota_enforced():
    key = APIKey("r1", "h", APIRole.READ_ONLY, "u", [], 2, True, datetime.utcnow(), None, None)
    limiter = RateLimitService(redis_url=None)

    one = await limiter.check_and_consume(key)
    two = await limiter.check_and_consume(key)
    three = await limiter.check_and_consume(key)

    assert one.allowed is True
    assert two.allowed is True
    assert three.allowed is False


@pytest.mark.asyncio
async def test_audit_log_invoked_for_request():
    key = APIKey("k1", "h", APIRole.READ_ONLY, "u", [], 100, True, datetime.utcnow(), None, None)
    auth = StubAuthService(key)
    mw = AuthMiddleware(auth)
    req = Req(path="/leaders", method="GET")
    req.state.api_key = key

    await mw.log_request(req, response_status=200, latency_ms=13)

    assert len(auth.logged) == 1
    assert auth.logged[0]["endpoint"] == "/leaders"
    assert auth.logged[0]["status_code"] == 200


@pytest.mark.asyncio
async def test_latency_budget_for_governance_path():
    key = APIKey("k2", "h", APIRole.TRADER, "u", [], 100, True, datetime.utcnow(), None, None)
    limiter = RateLimitService(redis_url=None)

    start = time.perf_counter()
    await limiter.check_and_consume(key)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 500
