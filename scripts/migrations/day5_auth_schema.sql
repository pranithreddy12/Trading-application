-- DAY 5: Authentication & Security Schema
-- Purpose: Implements RBAC, API key management, audit logging
-- Status: Idempotent (all operations use IF NOT EXISTS)
-- Date: May 16, 2026

-- =====================================================================
-- TABLE 1: API KEYS (Persistent credential storage)
-- =====================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Key storage
    key_hash VARCHAR(255) NOT NULL UNIQUE,        -- bcrypt hash, never raw
    key_prefix VARCHAR(20),                       -- "atlas_" prefix for UX (optional)
    
    -- Ownership
    user_id VARCHAR(100),                         -- user identifier (email, etc.)
    team_id UUID,                                 -- team for multi-tenant (future)
    
    -- Permissions
    role VARCHAR(50) NOT NULL DEFAULT 'read_only'
        CHECK (role IN ('admin', 'trader', 'read_only', 'follower', 'monitor')),
    scopes JSONB DEFAULT '[]'::jsonb,            -- endpoint restrictions (optional)
    
    -- Rate limiting
    rate_limit_per_min INT DEFAULT 100,
    
    -- State machine
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- Audit columns
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),                      -- API key or user that created this
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- Soft delete
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoke_reason VARCHAR(500),
    revoked_by VARCHAR(100),
    
    -- Metadata
    description VARCHAR(255),                     -- human-readable label
    expires_at TIMESTAMP WITH TIME ZONE,         -- optional expiry
    
    -- Indexes
    CONSTRAINT api_keys_valid_dates CHECK (created_at <= revoked_at OR revoked_at IS NULL),
    CONSTRAINT api_keys_valid_expiry CHECK (created_at <= expires_at OR expires_at IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_api_keys_role ON api_keys(role) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_api_keys_created_at ON api_keys(created_at);

COMMENT ON TABLE api_keys IS 'Persistent API credentials with RBAC + audit trail';
COMMENT ON COLUMN api_keys.key_hash IS 'bcrypt hash of API key (never store raw key)';
COMMENT ON COLUMN api_keys.key_prefix IS 'Visible prefix for key identification (e.g., atlas_abc123...)';
COMMENT ON COLUMN api_keys.role IS 'Primary role assignment (admin, trader, read_only, follower, monitor)';
COMMENT ON COLUMN api_keys.scopes IS 'JSON array of endpoint restrictions [{endpoint: /copy/logs, method: GET}]';
COMMENT ON COLUMN api_keys.rate_limit_per_min IS 'Requests per minute (0 = unlimited)';
COMMENT ON COLUMN api_keys.revoked_at IS 'Soft delete marker; NULL means active';

-- =====================================================================
-- TABLE 2: API REQUEST AUDIT LOG (Observability + security)
-- =====================================================================

CREATE TABLE IF NOT EXISTS api_request_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identification
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    user_id VARCHAR(100),
    
    -- Request details
    endpoint VARCHAR(255) NOT NULL,              -- /copy/logs, /health, etc.
    method VARCHAR(10) NOT NULL,                 -- GET, POST, etc.
    status_code INT NOT NULL,                    -- 200, 400, 401, 403, 500, etc.
    
    -- Performance
    latency_ms INT NOT NULL,
    
    -- Security
    ip_hash VARCHAR(128),                        -- hashed IP for privacy
    user_agent_hash VARCHAR(128),                -- hashed User-Agent
    
    -- Response context
    error_message VARCHAR(500),                  -- if status >= 400
    resource_id VARCHAR(100),                    -- what resource was accessed
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Indexes for queries
    CONSTRAINT api_request_audit_valid_status CHECK (status_code >= 100 AND status_code < 600),
    CONSTRAINT api_request_audit_valid_latency CHECK (latency_ms >= 0)
);

CREATE INDEX IF NOT EXISTS idx_api_request_audit_api_key_id ON api_request_audit(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_request_audit_created_at ON api_request_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_request_audit_endpoint ON api_request_audit(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_request_audit_status_code ON api_request_audit(status_code);
CREATE INDEX IF NOT EXISTS idx_api_request_audit_user_id ON api_request_audit(user_id);

-- Cleanup old audit logs (keep last 30 days)
-- Can be run as cron job
-- DELETE FROM api_request_audit WHERE created_at < NOW() - INTERVAL '30 days';

COMMENT ON TABLE api_request_audit IS 'Every API request logged for security, debugging, and analytics';
COMMENT ON COLUMN api_request_audit.api_key_id IS 'Foreign key to api_keys (NULL if auth failed)';
COMMENT ON COLUMN api_request_audit.ip_hash IS 'SHA256(ip_address) for privacy';
COMMENT ON COLUMN api_request_audit.status_code IS 'HTTP response code (200, 401, 403, 500, etc.)';
COMMENT ON COLUMN api_request_audit.latency_ms IS 'Time to process request in milliseconds';

-- =====================================================================
-- TABLE 3: AUDIT LOG (For high-stakes operations)
-- =====================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What happened
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    action VARCHAR(100) NOT NULL,               -- create_follower, revoke_key, etc.
    resource_type VARCHAR(50) NOT NULL,         -- api_key, follower, strategy, etc.
    resource_id UUID,                           -- ID of affected resource
    
    -- Who did it
    actor_id VARCHAR(100),                      -- API key ID or user ID
    actor_type VARCHAR(50) DEFAULT 'api_key',  -- api_key, system, admin
    
    -- Details
    status VARCHAR(20) NOT NULL DEFAULT 'success'
        CHECK (status IN ('success', 'failure', 'denied')),
    reason VARCHAR(255),                        -- why this action was taken
    
    -- Old/new values for tracking changes
    old_value JSONB,                            -- previous state
    new_value JSONB,                            -- new state
    
    -- Result
    status_code INT,                            -- HTTP code if applicable
    error_reason VARCHAR(500),                  -- if status = failure
    
    -- Indexes
    CONSTRAINT audit_logs_valid_status CHECK (status_code IS NULL OR (status_code >= 100 AND status_code < 600))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status);

COMMENT ON TABLE audit_logs IS 'High-stakes operation audit trail (api_key changes, follower creation, etc.)';
COMMENT ON COLUMN audit_logs.action IS 'Specific action: create_api_key, revoke_key, create_follower, delete_follower, etc.';
COMMENT ON COLUMN audit_logs.actor_type IS 'Who performed the action: api_key (programmatic), admin (manual), system (automated)';
COMMENT ON COLUMN audit_logs.old_value IS 'Previous state before change (JSON)';
COMMENT ON COLUMN audit_logs.new_value IS 'New state after change (JSON)';

-- =====================================================================
-- SEED DATA: Demo API keys (for Day 5 testing)
-- =====================================================================

-- Skip seed data in migration — will be inserted via AuthService.generate_api_key()

-- =====================================================================
-- MIGRATION METADATA
-- =====================================================================

INSERT INTO audit_logs (action, resource_type, actor_type, status, reason, new_value)
VALUES (
    'migration_applied',
    'schema',
    'system',
    'success',
    'Day 5 auth schema applied',
    jsonb_build_object('migration', 'day5_auth_schema.sql', 'tables', ARRAY['api_keys', 'api_request_audit', 'audit_logs'])
)
ON CONFLICT DO NOTHING;
