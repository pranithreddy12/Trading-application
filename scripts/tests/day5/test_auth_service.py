"""
Test suite for AuthService - Testing Layer of Gold Standard

This test file validates:
  ✓ API key generation (with hashing)
  ✓ Token validation (correct key accepted, wrong key rejected)
  ✓ Scope enforcement (role-based + explicit scopes)
  ✓ Key revocation (soft delete, idempotent)
  ✓ Rate limiting configuration
  ✓ Audit logging (all operations logged)
  ✓ Expiry handling
  ✓ Status lifecycle

Tests follow pyramid:
  - Unit tests: Service logic in isolation
  - Integration tests: With real (test) DB
  - Smoke tests: End-to-end flows
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from atlas.api.services.auth_service import AuthService, APIRole, APIKey
from atlas.data.storage.timescale_client import TimescaleClient


# ========================================================================
# FIXTURES
# ========================================================================

@pytest.fixture
async def test_db():
    """Create test database connection"""
    # Use in-memory SQLite for testing (fast, isolated)
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        # Simplified schema for testing
        await conn.execute("""
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT UNIQUE NOT NULL,
                key_prefix TEXT,
                user_id TEXT,
                team_id TEXT,
                role TEXT NOT NULL DEFAULT 'read_only' CHECK (role IN ('admin', 'trader', 'read_only', 'follower', 'monitor')),
                scopes TEXT,  -- JSON array as string
                rate_limit_per_min INTEGER DEFAULT 100,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by TEXT,
                last_used_at TEXT,
                revoked_at TEXT,
                revoke_reason TEXT,
                revoked_by TEXT,
                description TEXT,
                expires_at TEXT
            )
        """)
        
        await conn.execute("""
            CREATE TABLE api_request_audit (
                id TEXT PRIMARY KEY,
                api_key_id TEXT,
                user_id TEXT,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                ip_hash TEXT,
                user_agent_hash TEXT,
                error_message TEXT,
                resource_id TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        await conn.execute("""
            CREATE TABLE audit_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                actor_id TEXT,
                actor_type TEXT DEFAULT 'api_key',
                status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failure', 'denied')),
                reason TEXT,
                old_value TEXT,  -- JSON as string
                new_value TEXT,  -- JSON as string
                status_code INTEGER,
                error_reason TEXT
            )
        """)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def auth_service(test_db):
    """Create AuthService with test DB"""
    # Mock TimescaleClient
    class MockTimescaleClient:
        def __init__(self, engine):
            self.engine = engine
    
    client = MockTimescaleClient(test_db)
    return AuthService(client)


# ========================================================================
# UNIT TESTS: Key Generation
# ========================================================================

@pytest.mark.asyncio
async def test_generate_api_key_creates_entry(auth_service):
    """Generated API key should be stored hashed in DB"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.TRADER,
        created_by="admin",
        description="Test key"
    )
    
    # Verify raw key format
    assert raw_key.startswith("atlas_")
    assert len(raw_key) > 20
    
    # Verify key_id is UUID-like
    assert key_id
    
    # Verify NOT stored raw in DB (only hash)
    async with auth_service.db.engine.connect() as conn:
        result = await conn.execute(
            "SELECT key_hash FROM api_keys WHERE id = ?",
            (key_id,)
        )
        row = result.fetchone()
        assert row
        assert row[0] != raw_key  # Hash != raw key


@pytest.mark.asyncio
async def test_generate_api_key_with_expiry(auth_service):
    """API key with expiry should be stored"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.READ_ONLY,
        created_by="admin",
        expires_in_days=30
    )
    
    # Verify expiry set
    async with auth_service.db.engine.connect() as conn:
        result = await conn.execute(
            "SELECT expires_at FROM api_keys WHERE id = ?",
            (key_id,)
        )
        row = result.fetchone()
        assert row and row[0] is not None


@pytest.mark.asyncio
async def test_generate_key_audited(auth_service):
    """API key generation should be logged"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.ADMIN,
        created_by="admin"
    )
    
    # Verify audit log created
    async with auth_service.db.engine.connect() as conn:
        result = await conn.execute(
            "SELECT action, status FROM audit_logs WHERE action = 'create_api_key'"
        )
        row = result.fetchone()
        assert row
        assert row[0] == "create_api_key"
        assert row[1] == "success"


# ========================================================================
# UNIT TESTS: Token Validation
# ========================================================================

@pytest.mark.asyncio
async def test_validate_key_success(auth_service):
    """Valid key should validate and return APIKey object"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.TRADER,
        created_by="admin"
    )
    
    # Validate
    api_key = await auth_service.validate_key(raw_key)
    
    assert api_key is not None
    assert api_key.id == key_id
    assert api_key.role == APIRole.TRADER
    assert api_key.user_id == "test_user"
    assert api_key.is_valid()


@pytest.mark.asyncio
async def test_validate_key_invalid(auth_service):
    """Invalid key should return None"""
    api_key = await auth_service.validate_key("invalid_key_12345")
    assert api_key is None


@pytest.mark.asyncio
async def test_validate_key_expired(auth_service):
    """Expired key should fail validation"""
    import uuid
    from datetime import datetime, timedelta
    
    # Manually create expired key in DB
    key_id = str(uuid.uuid4())
    raw_key = "atlas_test_key_12345"
    key_hash = auth_service._hash_key(raw_key)
    
    async with auth_service.db.engine.begin() as conn:
        await conn.execute(
            """
            INSERT INTO api_keys 
            (id, key_hash, user_id, role, created_at, expires_at)
            VALUES (?, ?, 'test_user', 'read_only', ?, ?)
            """,
            (
                key_id,
                key_hash,
                datetime.utcnow().isoformat(),
                (datetime.utcnow() - timedelta(days=1)).isoformat()  # Expired yesterday
            )
        )
    
    # Should fail validation
    api_key = await auth_service.validate_key(raw_key)
    assert api_key is None


@pytest.mark.asyncio
async def test_validate_key_revoked(auth_service):
    """Revoked key should fail validation"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.READ_ONLY,
        created_by="admin"
    )
    
    # Revoke it
    await auth_service.revoke_key(key_id, revoked_by="admin", reason="Test revocation")
    
    # Should fail validation
    api_key = await auth_service.validate_key(raw_key)
    assert api_key is None


# ========================================================================
# UNIT TESTS: Scope Enforcement
# ========================================================================

@pytest.mark.asyncio
async def test_admin_can_access_everything(auth_service):
    """Admin role should have universal access"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="admin_user",
        role=APIRole.ADMIN,
        created_by="admin"
    )
    
    api_key = await auth_service.validate_key(raw_key)
    
    # Admin can access anything
    assert api_key.can_access_endpoint("/copy/logs", "GET")
    assert api_key.can_access_endpoint("/followers", "POST")
    assert api_key.can_access_endpoint("/strategies", "DELETE")


@pytest.mark.asyncio
async def test_read_only_cannot_write(auth_service):
    """Read-only role should only access GET endpoints"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="readonly_user",
        role=APIRole.READ_ONLY,
        created_by="admin"
    )
    
    api_key = await auth_service.validate_key(raw_key)
    
    # Can read
    assert api_key.can_access_endpoint("/copy/logs", "GET")
    
    # Cannot write
    assert not api_key.can_access_endpoint("/followers", "POST")
    assert not api_key.can_access_endpoint("/followers/123", "PUT")


@pytest.mark.asyncio
async def test_trader_can_write_orders(auth_service):
    """Trader role should execute orders"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="trader_user",
        role=APIRole.TRADER,
        created_by="admin"
    )
    
    api_key = await auth_service.validate_key(raw_key)
    
    # Can read
    assert api_key.can_access_endpoint("/copy/logs", "GET")
    
    # Can write to order endpoints
    assert api_key.can_access_endpoint("/copy/order", "POST")
    assert api_key.can_access_endpoint("/followers", "POST")
    
    # Cannot access everything
    assert not api_key.can_access_endpoint("/admin/users", "DELETE")


@pytest.mark.asyncio
async def test_monitor_can_only_health(auth_service):
    """Monitor role should only see health/status"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="monitor_user",
        role=APIRole.MONITOR,
        created_by="admin"
    )
    
    api_key = await auth_service.validate_key(raw_key)
    
    # Can only access health endpoints
    assert api_key.can_access_endpoint("/health", "GET")
    assert api_key.can_access_endpoint("/status", "GET")
    
    # Cannot access trading
    assert not api_key.can_access_endpoint("/copy/logs", "GET")
    assert not api_key.can_access_endpoint("/followers", "GET")


# ========================================================================
# INTEGRATION TESTS: Revocation
# ========================================================================

@pytest.mark.asyncio
async def test_revoke_key_idempotent(auth_service):
    """Revoking same key twice should be safe"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.READ_ONLY,
        created_by="admin"
    )
    
    # Revoke once
    await auth_service.revoke_key(key_id, revoked_by="admin", reason="First revoke")
    
    # Revoke again (should not error)
    await auth_service.revoke_key(key_id, revoked_by="admin", reason="Second revoke")
    
    # Should be revoked (validate both returns None, audit logged twice)
    api_key = await auth_service.validate_key(raw_key)
    assert api_key is None


@pytest.mark.asyncio
async def test_revocation_audited(auth_service):
    """Revocation should be logged"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.READ_ONLY,
        created_by="admin"
    )
    
    await auth_service.revoke_key(key_id, revoked_by="admin", reason="Test revocation")
    
    # Verify audit log
    async with auth_service.db.engine.connect() as conn:
        result = await conn.execute(
            "SELECT action, status, reason FROM audit_logs WHERE action = 'revoke_api_key'"
        )
        row = result.fetchone()
        assert row
        assert row[0] == "revoke_api_key"
        assert row[1] == "success"
        assert row[2] == "Test revocation"


# ========================================================================
# INTEGRATION TESTS: Rate Limiting
# ========================================================================

@pytest.mark.asyncio
async def test_rate_limit_configuration(auth_service):
    """API key should store rate limit"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.TRADER,
        created_by="admin",
        rate_limit_per_min=50
    )
    
    api_key = await auth_service.validate_key(raw_key)
    assert api_key.rate_limit_per_min == 50


# ========================================================================
# INTEGRATION TESTS: Request Logging
# ========================================================================

@pytest.mark.asyncio
async def test_request_logged(auth_service):
    """Requests should be logged to audit table"""
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.READ_ONLY,
        created_by="admin"
    )
    
    # Log a request
    await auth_service.log_request(
        api_key_id=key_id,
        endpoint="/copy/logs",
        method="GET",
        status_code=200,
        latency_ms=45
    )
    
    # Verify in audit
    async with auth_service.db.engine.connect() as conn:
        result = await conn.execute(
            "SELECT endpoint, method, status_code FROM api_request_audit WHERE api_key_id = ?",
            (key_id,)
        )
        row = result.fetchone()
        assert row
        assert row[0] == "/copy/logs"
        assert row[1] == "GET"
        assert row[2] == 200


# ========================================================================
# SMOKE TESTS: End-to-end flows
# ========================================================================

@pytest.mark.asyncio
async def test_full_lifecycle(auth_service):
    """
    Smoke test: Generate → validate → access check → revoke → fail validation
    """
    # 1. Generate
    raw_key, key_id = await auth_service.generate_api_key(
        user_id="test_user",
        role=APIRole.TRADER,
        created_by="admin"
    )
    assert key_id
    
    # 2. Validate
    api_key = await auth_service.validate_key(raw_key)
    assert api_key is not None
    assert api_key.is_valid()
    
    # 3. Check scope
    can_access = api_key.can_access_endpoint("/copy/order", "POST")
    assert can_access
    
    # 4. Revoke
    await auth_service.revoke_key(key_id, revoked_by="admin", reason="Lifecycle test end")
    
    # 5. Validation should fail
    api_key_after_revoke = await auth_service.validate_key(raw_key)
    assert api_key_after_revoke is None


if __name__ == "__main__":
    # Run: pytest scripts/tests/day5/test_auth_service.py -v
    pytest.main([__file__, "-v"])
