-- ============================================================================
-- P6 T1 — system_config: key/value store backing the stack authority flag.
-- ADDITIVE ONLY. Creates a NEW table; alters/drops NOTHING existing.
-- Safe to run repeatedly (CREATE TABLE IF NOT EXISTS + ON CONFLICT DO NOTHING).
--
-- NOTE: The T1 stack_flag.py accessor reads ATLAS_STACK_VERSION (env/settings)
-- and does NOT depend on this table — so applying this migration is OPTIONAL
-- for T1 and changes no behavior. The DB-backed hot-reload read is wired in a
-- later consumer-branch task; this seeds the row so that wiring has a default.
-- This is NOT the T6 *_v1 metric-column migration.
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO system_config (key, value)
VALUES ('stack_version', 'legacy')
ON CONFLICT (key) DO NOTHING;
