# ATLAS — Deployment Guide

This guide covers deploying ATLAS in development, staging, and production environments.

---

## Table of Contents

- [Environment Overview](#environment-overview)
- [Prerequisites](#prerequisites)
- [Infrastructure Setup](#infrastructure-setup)
- [Application Deployment](#application-deployment)
- [Database Initialization](#database-initialization)
- [Agent Deployment](#agent-deployment)
- [Monitoring & Observability](#monitoring--observability)
- [Security Configuration](#security-configuration)
- [Production Hardening](#production-hardening)
- [Backup & Recovery](#backup--recovery)
- [Scaling](#scaling)
- [Health Checks](#health-checks)

---

## Environment Overview

| Environment | Purpose | Infrastructure |
|-------------|---------|----------------|
| **Development** | Local development and testing | Docker Compose (single machine) |
| **Staging** | Pre-production validation | Docker Compose or Kubernetes |
| **Production** | Live trading | Kubernetes or dedicated servers |

### Resource Requirements

| Component | CPU | RAM | Storage | Network |
|-----------|-----|-----|---------|---------|
| TimescaleDB | 2+ cores | 2GB+ | 50GB+ SSD | Internal |
| Redis | 1+ core | 512MB+ | 5GB | Internal |
| API Server | 2+ cores | 512MB+ | — | External (443) |
| Agents (total) | 4+ cores | 2GB+ | — | Internal |
| **Total (prod)** | 8+ cores | 6GB+ | 55GB+ SSD | — |

---

## Prerequisites

### System Requirements

```bash
# Check Python version
python --version  # Must be 3.11+

# Check Docker (optional but recommended)
docker --version  # 20.10+

# Check Docker Compose
docker compose version  # 2.0+
```

### Required API Keys

| Service | Purpose | Get Key At |
|---------|---------|------------|
| Anthropic | LLM strategy generation | console.anthropic.com |
| Polygon.io | Equity market data | polygon.io |
| Binance | Crypto market data (optional) | binance.com |
| Alpaca | Broker execution (optional) | alpaca.markets |
| Slack | Alerts (optional) | api.slack.com |

---

## Infrastructure Setup

### Option 1: Docker Compose (Recommended)

```bash
# Start TimescaleDB and Redis
docker compose up -d

# Verify services are healthy
docker compose ps

# Expected output:
# atlas_timescaledb   running (healthy)   0.0.0.0:5433->5432/tcp
# atlas_redis         running (healthy)   0.0.0.0:6380->6379/tcp
```

### Option 2: Manual Installation

#### TimescaleDB

```bash
# Ubuntu/Debian
sudo apt install timescaledb-2-postgresql-15

# Configure PostgreSQL
sudo nano /etc/postgresql/15/main/postgresql.conf
# Add: shared_preload_libraries = 'timescaledb'

# Create database
sudo -u postgres createdb atlas
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
```

#### Redis

```bash
# Ubuntu/Debian
sudo apt install redis-server

# Configure
sudo nano /etc/redis/redis.conf
# Set: appendonly yes
# Set: port 6380

sudo systemctl restart redis-server
```

---

## Application Deployment

### 1. Clone Repository

```bash
git clone <repository-url>
cd ATLAS
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

```bash
pip install -e .
```

### 4. Configure Environment

```bash
# Create .env file
cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/atlas
REDIS_URL=redis://localhost:6380

# API Keys
ANTHROPIC_API_KEY=your-anthropic-key-here
POLYGON_API_KEY=your-polygon-key-here
BINANCE_API_KEY=your-binance-key-here
BINANCE_SECRET=your-binance-secret-here
ALPACA_API_KEY=your-alpaca-key-here
ALPACA_SECRET_KEY=your-alpaca-secret-here

# Trading Configuration
WATCHLIST=SPY,QQQ,AAPL,MSFT,NVDA,TSLA,GOOGL
CRYPTO_PAIRS=BTCUSDT,ETHUSDT

# Environment
ENVIRONMENT=production

# Alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
EOF
```

### 5. Verify Setup

```bash
python verify_setup.py
```

Expected output:
```
✅ Database URL: postgresql://...
✅ Redis URL: redis://...
✅ Polygon API Key: present
✅ Watchlist: SPY,QQQ,...
✅ Database connection: OK
✅ Redis connection: OK
✅ Schema contracts: VALID
```

---

## Database Initialization

### Run Migrations

```bash
python scripts/run_migration.py
```

This applies all schema changes including:
- Core tables (strategies, backtest_results, etc.)
- Scout network tables (market_regime_memory, liquidity_intelligence, etc.)
- Governance tables (event_store, audit_ledger, etc.)
- Portfolio tables (portfolio_intelligence, capital_allocation, etc.)
- Observability tables (monitoring_metrics, anomaly_observations, etc.)

### Verify Schema

```bash
python verify_migration.py
```

---

## Agent Deployment

### Option 1: Full Pipeline (Recommended)

```bash
# Start the complete autonomous pipeline
python -m atlas.scripts.run_pipeline
```

### Option 2: Individual Agents

Start each agent in a separate terminal or using a process manager:

```bash
# Terminal 1: Data Ingestion
python -m atlas.agents.l1_data.polygon_ws_agent

# Terminal 2: Feature Computation
python -m atlas.agents.l1_data.feature_agent

# Terminal 3: Strategy Ideation
python -m atlas.agents.l2_strategy.ideator_agent

# Terminal 4: Backtesting
python -m atlas.agents.l3_backtest.backtest_runner

# Terminal 5: Copy Trading
python -m atlas.agents.l5_execution.copy_trader
```

### Option 3: Process Manager (systemd)

Create service files for each agent:

```ini
# /etc/systemd/system/atlas-polygon.service
[Unit]
Description=ATLAS Polygon WebSocket Agent
After=network.target docker.service

[Service]
Type=simple
User=atlas
WorkingDirectory=/opt/ATLAS
Environment=PATH=/opt/ATLAS/.venv/bin
ExecStart=/opt/ATLAS/.venv/bin/python -m atlas.agents.l1_data.polygon_ws_agent
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable atlas-polygon
sudo systemctl start atlas-polygon
```

---

## Monitoring & Observability

### Start Monitoring

```bash
# Real-time monitoring dashboard
python scripts/monitor_dashboard.py

# Soak test with metrics collection
python scripts/phase33_performance_benchmark_soak.py --duration-minutes 60
```

### Key Metrics to Monitor

| Metric | Healthy Range | Alert Threshold |
|--------|---------------|-----------------|
| Event Loop Latency | <1ms | >5ms |
| RAM Usage | <200MB | >500MB |
| Replay Integrity | 1.000 | <0.999 |
| Dead-Letter Queue | 0 | >10 |
| Active Agents | >5 | <3 |
| DB Connection Pool | <20 | >25 |

### Slack Alerts

Configure `SLACK_WEBHOOK_URL` in `.env` to receive:
- Agent death notifications
- Kill switch activations
- System health degradation
- High-priority anomalies

---

## Security Configuration

### API Authentication

ATLAS uses Bearer token authentication for all protected endpoints:

```bash
# Generate API key
python scripts/day5/generate_role_keys.py

# Use API key
curl -H "Authorization: Bearer <api_key>" http://localhost:8000/strategies
```

### Network Security

```bash
# Firewall rules (production)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 8000/tcp   # Block direct API access
sudo ufw deny 5433/tcp   # Block direct DB access
sudo ufw deny 6380/tcp   # Block direct Redis access
```

### Environment Variables

Never commit `.env` files. Use a secrets manager in production:

```bash
# AWS Secrets Manager
aws secretsmanager create-secret --name atlas/production --secret-string file://.env

# HashiCorp Vault
vault kv put secret/atlas @.env
```

---

## Production Hardening

### Database

```sql
-- Enable connection pooling (PgBouncer)
-- Configure backup schedule
-- Set up replication for read replicas
-- Enable pg_stat_statements for query monitoring
```

### Redis

```bash
# Configure persistence
redis-cli CONFIG SET appendonly yes
redis-cli CONFIG SET appendfsync everysec

# Set memory limit
redis-cli CONFIG SET maxmemory 1gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### API Server

```bash
# Run with Gunicorn for production
gunicorn atlas.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile /var/log/atlas/access.log \
  --error-logfile /var/log/atlas/error.log
```

---

## Backup & Recovery

### Database Backup

```bash
# Full backup
pg_dump -h localhost -p 5433 -U postgres atlas > atlas_backup_$(date +%Y%m%d).sql

# Automated daily backup (cron)
0 2 * * * pg_dump -h localhost -p 5433 -U postgres atlas | gzip > /backups/atlas_$(date +\%Y\%m\%d).sql.gz
```

### Redis Backup

```bash
# Redis automatically saves to dump.rdb
# Copy for backup
cp /data/dump.rdb /backups/redis_$(date +%Y%m%d).rdb
```

### Recovery

```bash
# Restore database
psql -h localhost -p 5433 -U postgres atlas < atlas_backup.sql

# Restore Redis
cp /backups/redis_YYYYMMDD.rdb /data/dump.rdb
redis-cli SHUTDOWN NOSAVE
# Restart Redis
```

---

## Scaling

### Horizontal Scaling

```bash
# Scale strategy generation
docker compose up -d --scale ideator=3

# Scale backtesting
docker compose up -d --scale backtest-runner=2

# Scale execution
docker compose up -d --scale copy-trader=2
```

### Vertical Scaling

```yaml
# docker-compose.yml
services:
  timescaledb:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
```

### Database Scaling

```sql
-- Add read replica
-- Configure connection pooling (PgBouncer)
-- Partition large tables by time
-- Add materialized views for dashboard queries
```

---

## Health Checks

### System Health

```bash
curl http://localhost:8000/health
```

### Database Health

```bash
psql -h localhost -p 5433 -U postgres atlas -c "SELECT 1;"
```

### Redis Health

```bash
redis-cli -p 6380 ping
# Expected: PONG
```

### Agent Health

```bash
# Check agent heartbeats in Redis
redis-cli -p 6380 HGETALL "agent:<agent_id>"
```

---

## Rollback Procedure

If issues occur after deployment:

```bash
# 1. Activate kill switch
curl -X POST http://localhost:8000/kill_switch/activate

# 2. Stop all agents
pkill -f "atlas.agents"

# 3. Restore database (if needed)
psql -h localhost -p 5433 -U postgres atlas < backup.sql

# 4. Restart with previous version
git checkout <previous-tag>
pip install -e .

# 5. Start agents
python -m atlas.scripts.run_pipeline

# 6. Deactivate kill switch (when ready)
curl -X POST http://localhost:8000/kill_switch/deactivate
```

---

## Support

For deployment issues:
1. Check `verify_setup.py` output
2. Review logs in `api_server.log` and `atlas/soak.log`
3. Check database connectivity
4. Verify Redis connectivity
5. Ensure all API keys are valid

---

*Last updated: June 2026*
