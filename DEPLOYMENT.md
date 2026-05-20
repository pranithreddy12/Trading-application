# Polygon WebSocket Agent - Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   ATLAS System Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  L1 Data Ingestion Layer                               │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  PolygonWebSocketAgent (Async)                   │  │   │
│  │  │  - Main agent loop                              │  │   │
│  │  │  - Metrics & heartbeat                          │  │   │
│  │  │  - Error handling & recovery                    │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                    │                                    │   │
│  │                    ▼                                    │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  PolygonWebSocketClient                          │  │   │
│  │  │  - WebSocket connection pool                     │  │   │
│  │  │  - Auth & subscription mgmt                      │  │   │
│  │  │  - Exponential backoff reconnect                 │  │   │
│  │  │  - Message dispatch                             │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                    │                                    │   │
│  └────────────────────┼────────────────────────────────────┘   │
│                       │                                         │
│     ┌─────────────────┼─────────────────┐                      │
│     │                 │                 │                      │
│     ▼                 ▼                 ▼                      │
│  ┌─────────────┐  ┌──────────┐  ┌────────────┐               │
│  │TimescaleDB  │  │  Redis   │  │ Prometheus │               │
│  │ (market data)  │(IPC/cache)  │ (metrics)  │               │
│  └─────────────┘  └──────────┘  └────────────┘               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  L2-L5 Processing Layers (Consumers)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+) or macOS
- **Python**: 3.10+
- **RAM**: 2GB minimum (4GB recommended for multiple agents)
- **Disk**: 10GB SSD for database
- **Network**: 10 Mbps minimum for 1000 symbols

### External Services
- **Polygon.io**: Active subscription with WebSocket access
- **PostgreSQL**: 13+ with TimescaleDB extension
- **Redis**: 6.0+ for caching and IPC

### Network Requirements
- Outbound HTTPS: `https://api.polygon.io` (REST)
- Outbound WSS: `wss://socket.polygon.io` (WebSocket)
- Internal: Database and Redis on same network (can be local)

## Installation Steps

### 1. Clone and Setup Project
```bash
cd /opt/atlas
git clone <repo_url> .

# Create Python virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r atlas/requirements.txt

# Install development dependencies (testing)
pip install pytest pytest-asyncio pytest-cov
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**.env Example:**
```env
# Database
DATABASE_URL=postgresql+asyncpg://atlas:password@localhost:5432/atlas_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Polygon.io
POLYGON_API_KEY=YOUR_POLYGON_API_KEY
WATCHLIST=AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META,AMD,NFLX,DISH

# Crypto
BINANCE_API_KEY=YOUR_KEY
BINANCE_SECRET=YOUR_SECRET

# Other
ENVIRONMENT=production
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
CRYPTO_PAIRS=BTCUSDT,ETHUSDT
```

### 3. Setup PostgreSQL & TimescaleDB

**Option A: Docker Compose**
```yaml
# docker-compose.yml
version: '3.8'
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg14
    environment:
      POSTGRES_DB: atlas_db
      POSTGRES_USER: atlas
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    command: >
      postgres
      -c shared_preload_libraries=timescaledb
      -c timescaledb.enable_hypertable_compression=on
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

Run: `docker-compose up -d`

**Option B: Local Installation**
```bash
# macOS
brew install postgresql timescaledb-cli redis

# Ubuntu
sudo apt-get install postgresql postgresql-contrib
sudo apt-get install timescaledb-postgresql-14
sudo apt-get install redis-server

# Initialize
sudo systemctl start postgresql
sudo systemctl start redis-server
```

### 4. Initialize Database
```bash
# Create database
createdb atlas_db -U postgres

# Load TimescaleDB
psql -U postgres -d atlas_db -c "CREATE EXTENSION timescaledb;"

# Load schema
psql -U postgres -d atlas_db -f atlas/data/storage/schema.sql

# Verify
psql -U postgres -d atlas_db -c "\dt"
```

### 5. Test Configuration
```bash
# Test database connection
python -c "
from atlas.config.settings import get_settings
from atlas.data.storage.timescale_client import TimescaleClient
import asyncio

async def test():
    settings = get_settings()
    client = TimescaleClient(settings.database_url)
    await client.connect()
    print('✓ Database connection OK')

asyncio.run(test())
"

# Test Redis connection
redis-cli ping
# Output: PONG

# Test Polygon API key
curl -X GET "https://api.polygon.io/v1/markets/stocks/quotes" \
  -H "Authorization: Bearer $POLYGON_API_KEY" | jq .
```

## Running the Agent

### Development (Direct)
```bash
# Run agent directly
python -c "
import asyncio
import redis.asyncio as redis
from atlas.agents.l1_data import PolygonWebSocketAgent
from atlas.config.settings import get_settings
from loguru import logger

async def main():
    redis_client = await redis.from_url('redis://localhost')
    settings = get_settings()
    agent = PolygonWebSocketAgent(redis_client, settings.database_url)
    
    try:
        await agent.start()
        print(f'Agent started: {agent.agent_id}')
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print('Stopping...')
    finally:
        await agent.stop()
        await redis_client.close()

asyncio.run(main())
"
```

### Production (Systemd Service)

**Create service file:**
```bash
sudo tee /etc/systemd/system/atlas-polygon-l1.service > /dev/null <<EOF
[Unit]
Description=ATLAS Polygon WebSocket L1 Agent
After=network.target postgresql.service redis.service
Wants=network-online.target

[Service]
Type=simple
User=atlas
WorkingDirectory=/opt/atlas
Environment="PATH=/opt/atlas/venv/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="ENVIRONMENT=production"

ExecStart=/opt/atlas/venv/bin/python -m atlas.agents.l1_data.polygon_ws_agent

# Restart on failure
Restart=on-failure
RestartSec=5s

# Resource limits
LimitNOFILE=65536
LimitNPROC=32768
MemoryLimit=2G
CPUQuota=100%

[Install]
WantedBy=multi-user.target
EOF
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable atlas-polygon-l1
sudo systemctl start atlas-polygon-l1

# Monitor
sudo systemctl status atlas-polygon-l1
sudo journalctl -u atlas-polygon-l1 -f
```

### Production (Supervisor)

**Create config:**
```ini
; /etc/supervisor/conf.d/atlas-polygon-l1.conf
[program:atlas-polygon-l1]
directory=/opt/atlas
command=/opt/atlas/venv/bin/python -m atlas.agents.l1_data.polygon_ws_agent
user=atlas
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=10
stdout_logfile=/var/log/atlas/polygon-l1.log
stderr_logfile=/var/log/atlas/polygon-l1-error.log
environment=ENVIRONMENT=production,PYTHONUNBUFFERED=1

[group:atlas]
programs=atlas-polygon-l1
priority=999
```

**Deploy:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status atlas-polygon-l1
```

### Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc postgresql-client redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy code
COPY atlas/ /app/atlas/
COPY requirements.txt /app/
COPY .env /app/

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import redis.asyncio as r; r.from_url('redis://localhost')" || exit 1

# Run agent
CMD ["python", "-m", "atlas.agents.l1_data.polygon_ws_agent"]
```

**Kubernetes Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atlas-polygon-l1
  namespace: atlas
spec:
  replicas: 2  # High availability
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      app: atlas-polygon-l1
  template:
    metadata:
      labels:
        app: atlas-polygon-l1
    spec:
      containers:
      - name: agent
        image: atlas:polygon-l1-latest
        imagePullPolicy: Always
        
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: atlas-secrets
              key: database-url
        - name: POLYGON_API_KEY
          valueFrom:
            secretKeyRef:
              name: atlas-secrets
              key: polygon-api-key
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        
        resources:
          requests:
            cpu: 250m
            memory: 512Mi
          limits:
            cpu: 500m
            memory: 1Gi
        
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - |
              import redis.asyncio as r
              import asyncio
              async def check():
                  client = await r.from_url('redis://localhost:6379')
                  await client.ping()
              asyncio.run(check())
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3

---
apiVersion: v1
kind: Service
metadata:
  name: atlas-polygon-l1
  namespace: atlas
spec:
  selector:
    app: atlas-polygon-l1
  ports:
  - port: 8080
    targetPort: 8080
```

## Monitoring & Observability

### Logs
```bash
# View logs
tail -f /var/log/atlas/polygon-l1.log

# Search for errors
grep ERROR /var/log/atlas/polygon-l1.log

# Real-time filtering
journalctl -u atlas-polygon-l1 -f | grep "error\|failed"
```

### Metrics Collection

**Prometheus scrape config:**
```yaml
scrape_configs:
  - job_name: 'atlas-polygon-l1'
    static_configs:
      - targets: ['localhost:8081']
    scrape_interval: 30s
```

**Key metrics to monitor:**
```
# Messages
atlas_polygon_messages_received_total
atlas_polygon_messages_processed_total
atlas_polygon_messages_failed_total

# Database
atlas_polygon_db_writes_total
atlas_polygon_db_errors_total
atlas_polygon_db_write_latency_seconds

# Connectivity
atlas_polygon_websocket_connected
atlas_polygon_websocket_authenticated
atlas_polygon_reconnect_attempts_total
```

### Alerts (Prometheus AlertManager)
```yaml
groups:
- name: atlas-polygon-l1
  rules:
  - alert: PolygonWebSocketDisconnected
    expr: atlas_polygon_websocket_connected == 0
    for: 1m
    annotations:
      summary: "Polygon WebSocket disconnected"
  
  - alert: HighMessageFailureRate
    expr: |
      rate(atlas_polygon_messages_failed_total[5m]) /
      rate(atlas_polygon_messages_received_total[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High message failure rate (>5%)"
  
  - alert: DatabaseWriteErrors
    expr: rate(atlas_polygon_db_errors_total[5m]) > 10
    for: 5m
    annotations:
      summary: "Excessive database errors (>10/sec)"
```

### Database Monitoring
```sql
-- Current subscriptions
SELECT symbol, COUNT(*) as events
FROM market_data_l2
WHERE time > NOW() - INTERVAL '1 minute'
GROUP BY symbol
ORDER BY events DESC
LIMIT 20;

-- Message rate
SELECT 
  DATE_TRUNC('minute', time) as minute,
  COUNT(*) as messages,
  COUNT(DISTINCT symbol) as symbols
FROM order_flow
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY 1
ORDER BY 1 DESC;

-- Data freshness
SELECT symbol, MAX(time) as last_update
FROM market_data_l1
GROUP BY symbol
ORDER BY last_update DESC;
```

## Troubleshooting

### Agent won't start
```bash
# Check Python version
python --version  # Should be 3.10+

# Check dependencies
pip list | grep -E "websockets|sqlalchemy|loguru"

# Verify environment file
python -c "from atlas.config.settings import get_settings; print(get_settings())"
```

### Connection issues
```bash
# Test Polygon API
curl -H "Authorization: Bearer $POLYGON_API_KEY" \
  "https://api.polygon.io/v1/last/stocks/AAPL/trade"

# Test database
psql postgresql://user:pass@localhost/atlas_db -c "SELECT NOW();"

# Test Redis
redis-cli -h localhost -p 6379 PING
```

### Performance issues
```bash
# Check process resource usage
ps aux | grep polygon_ws_agent
top -p <pid>

# Check database connections
psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='atlas_db';"

# Check disk space
df -h /var/lib/postgresql/data
```

### Debug mode
```bash
# Run with debug logging
RUST_LOG=debug python -m atlas.agents.l1_data.polygon_ws_agent

# With verbose output
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
import asyncio
# ... run agent
"
```

## Upgrade & Maintenance

### Schema Migrations
```bash
# Backup database
pg_dump atlas_db > backup_$(date +%Y%m%d).sql

# Run migration
psql atlas_db < migrations/001_add_column.sql

# Verify
psql atlas_db -c "\d market_data_l1"
```

### Rolling Updates
```bash
# Graceful shutdown
sudo systemctl stop atlas-polygon-l1

# Backup current version
cp -r atlas/ atlas.backup.$(date +%Y%m%d)

# Update code
git pull origin main
pip install -r atlas/requirements.txt

# Restart
sudo systemctl start atlas-polygon-l1
```

### Data Retention
```sql
-- Set retention policy (90 days)
SELECT add_retention_policy('market_data_l1', INTERVAL '90 days');
SELECT add_retention_policy('market_data_l2', INTERVAL '90 days');
SELECT add_retention_policy('order_flow', INTERVAL '90 days');
```

## Performance Tuning

### PostgreSQL Configuration
```ini
# /etc/postgresql/14/main/postgresql.conf
shared_buffers = 256MB           # 25% of system RAM
effective_cache_size = 1GB       # 50-75% of system RAM
work_mem = 4MB                   # Per operation
maintenance_work_mem = 50MB
max_connections = 200
```

### TimescaleDB Compression
```sql
-- Enable compression for old data
ALTER TABLE market_data_l1 SET (timescaledb.compress, timescaledb.compress_interval_length = '1 day');

-- Add policy to compress after 1 day
SELECT add_compression_policy('market_data_l1', INTERVAL '1 day');
```

## Support & Documentation

- [Polygon.io API Docs](https://polygon.io/docs/)
- [TimescaleDB Docs](https://docs.timescale.com/)
- [AsyncIO Guide](https://docs.python.org/3/library/asyncio.html)
- Project README: `atlas/agents/l1_data/README.md`
