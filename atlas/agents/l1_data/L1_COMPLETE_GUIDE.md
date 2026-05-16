# ATLAS L1 Data Ingestion Layer - Complete Guide

## Overview

The L1 Data Ingestion Layer provides **dual-source real-time market data acquisition**:

- **Polygon.io**: Stock and options market data (US equities, forex, crypto via derivatives)
- **Binance**: Cryptocurrency spot trading data (real-time order flow and depth)

Both sources feed into a unified TimescaleDB schema for seamless downstream processing.

## Architecture

```
┌─────────────────────────────────────────┬──────────────────────────────────────┐
│      Polygon.io WebSocket API           │    Binance WebSocket API             │
│  (Stock & Derivatives Data)             │  (Crypto Spot Trading)               │
└────────────────┬────────────────────────┴──────────────────┬───────────────────┘
                 │                                           │
                 ▼                                           ▼
    ┌────────────────────────────┐        ┌─────────────────────────────┐
    │ PolygonWebSocketClient     │        │ BinanceWebSocketClient      │
    │                            │        │                             │
    │ • Q.* Quotes              │        │ • @trade               │
    │ • T.* Trades              │        │ • @depth20@100ms       │
    │ • A.* Aggregates          │        │                             │
    │ • Exponential backoff      │        │ • Exponential backoff       │
    └────────────┬───────────────┘        └────────────┬────────────────┘
                 │                                      │
                 ▼                                      ▼
    ┌────────────────────────────┐        ┌─────────────────────────────┐
    │ PolygonWebSocketAgent      │        │ BinanceWebSocketAgent       │
    │ (Extends BaseAgent)        │        │ (Extends BaseAgent)         │
    │                            │        │                             │
    │ • Quote → market_data_l2   │        │ • Trade → order_flow        │
    │ • Trade → order_flow       │        │ • Depth → market_data_l2    │
    │ • Agg → market_data_l1     │        │ • Error handling & metrics  │
    └────────────┬───────────────┘        └────────────┬────────────────┘
                 │                                      │
                 └──────────────────┬───────────────────┘
                                    ▼
                  ┌──────────────────────────────────┐
                  │   TimescaleDB (Unified Schema)   │
                  │                                  │
                  │ • market_data_l1 (OHLCV)        │
                  │ • market_data_l2 (Orderbook)    │
                  │ • order_flow (Trades)           │
                  │ • features (Computed features)  │
                  │ • agent_registry                │
                  │ • system_logs                   │
                  └──────────────────────────────────┘
                                    ▼
                  ┌──────────────────────────────────┐
                  │    L2-L5 Agents (Consumers)      │
                  │                                  │
                  │ • L2: Strategy layer             │
                  │ • L3: Backtesting layer          │
                  │ • L4: Risk management            │
                  │ • L5: Execution layer            │
                  └──────────────────────────────────┘
```

## Unified Database Schema

Both agents write to the same tables with different `source` identifiers:

### market_data_l1 (OHLCV)
```
Field    | Type       | Source
---------|-----------|--------
time     | TIMESTAMP | Both
symbol   | TEXT      | Both (AAPL, BTCUSDT)
open     | NUMERIC   | Polygon aggregates only
high     | NUMERIC   | Polygon aggregates only
low      | NUMERIC   | Polygon aggregates only
close    | NUMERIC   | Polygon aggregates only
volume   | NUMERIC   | Both
source   | TEXT      | "polygon" or "binance"
interval | TEXT      | "1m" (Polygon), varies (Binance)
```

### market_data_l2 (Orderbook)
```
Field    | Type       | Source
---------|-----------|--------
time     | TIMESTAMP | Both
symbol   | TEXT      | Both
bids     | JSONB     | Both
asks     | JSONB     | Both
spread   | NUMERIC   | Both (calculated)
mid_price| NUMERIC   | Both (calculated)
source   | TEXT      | "polygon" or "binance"
```

### order_flow (Trades)
```
Field    | Type       | Source
---------|-----------|--------
time     | TIMESTAMP | Both
symbol   | TEXT      | Both
price    | NUMERIC   | Both
size     | NUMERIC   | Both
side     | TEXT      | Both ("buy", "sell", "unknown")
aggressor| TEXT      | Both (exchange or trade ID)
source   | TEXT      | "polygon" or "binance"
```

## Running Both Agents Simultaneously

### Systemd (Production)

Create two service files:

**`/etc/systemd/system/atlas-polygon-l1.service`**
```ini
[Unit]
Description=ATLAS Polygon WebSocket L1 Agent
After=network.target postgresql.service redis.service

[Service]
Type=simple
ExecStart=/opt/atlas/venv/bin/python -m atlas.agents.l1_data.polygon_ws_agent
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/atlas-binance-l1.service`**
```ini
[Unit]
Description=ATLAS Binance WebSocket L1 Agent
After=network.target postgresql.service redis.service

[Service]
Type=simple
ExecStart=/opt/atlas/venv/bin/python -m atlas.agents.l1_data.binance_ws_agent
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl enable atlas-polygon-l1 atlas-binance-l1
sudo systemctl start atlas-polygon-l1 atlas-binance-l1
sudo systemctl status atlas-polygon-l1 atlas-binance-l1
```

### Docker Compose

```yaml
version: '3.8'
services:
  polygon-l1:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - ENVIRONMENT=production
      - POLYGON_API_KEY=${POLYGON_API_KEY}
      - WATCHLIST=${WATCHLIST}
    depends_on:
      - timescaledb
      - redis
    networks:
      - atlas

  binance-l1:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - ENVIRONMENT=production
      - CRYPTO_PAIRS=${CRYPTO_PAIRS}
    depends_on:
      - timescaledb
      - redis
    networks:
      - atlas

  timescaledb:
    image: timescale/timescaledb:latest-pg14
    environment:
      POSTGRES_DB: atlas_db
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - atlas

  redis:
    image: redis:7-alpine
    networks:
      - atlas

volumes:
  pgdata:

networks:
  atlas:
```

### Python (Development)

```python
import asyncio
import redis.asyncio as redis
from atlas.agents.l1_data import PolygonWebSocketAgent, BinanceWebSocketAgent
from atlas.config.settings import get_settings

async def main():
    redis_client = await redis.from_url("redis://localhost")
    settings = get_settings()
    
    # Create both agents
    polygon_agent = PolygonWebSocketAgent(redis_client, settings.database_url)
    binance_agent = BinanceWebSocketAgent(redis_client, settings.database_url)
    
    try:
        # Start both
        await polygon_agent.start()
        await binance_agent.start()
        
        print("Both agents running...")
        
        # Monitor
        while True:
            await asyncio.sleep(60)
            
            print(f"\nPolygon: {polygon_agent._messages_received} messages")
            print(f"Binance: {binance_agent._messages_received} messages")
            
    finally:
        await polygon_agent.stop()
        await binance_agent.stop()
        await redis_client.close()

asyncio.run(main())
```

## Configuration

### Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/atlas_db
REDIS_URL=redis://localhost:6379

# Polygon (Stocks & Derivatives)
POLYGON_API_KEY=your_polygon_key
WATCHLIST=AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META,AMD,NFLX,DISH

# Binance (Crypto)
CRYPTO_PAIRS=BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,DOGEUSDT,MATICUSDT,SOLUSDT

# Optional
ENVIRONMENT=production
BINANCE_API_KEY=your_binance_key  # For authenticated endpoints if needed
BINANCE_SECRET=your_binance_secret
```

## Database Queries

### Compare Stock vs Crypto

**Stock quotes (Polygon)**
```sql
SELECT time, symbol, bid, ask, mid_price, spread
FROM market_data_l2
WHERE source = 'polygon' AND time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC LIMIT 20;
```

**Crypto quotes (Binance)**
```sql
SELECT time, symbol, mid_price, spread
FROM market_data_l2
WHERE source = 'binance' AND time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC LIMIT 20;
```

**Combined trade volume (stocks)**
```sql
SELECT 
  DATE_TRUNC('minute', time) as minute,
  symbol,
  COUNT(*) as trades,
  SUM(size) as volume
FROM order_flow
WHERE source = 'polygon' AND time > NOW() - INTERVAL '1 hour'
GROUP BY 1, 2
ORDER BY 1 DESC;
```

**Combined trade volume (crypto)**
```sql
SELECT 
  DATE_TRUNC('minute', time) as minute,
  symbol,
  COUNT(*) as trades,
  SUM(size) as volume
FROM order_flow
WHERE source = 'binance' AND time > NOW() - INTERVAL '1 hour'
GROUP BY 1, 2
ORDER BY 1 DESC;
```

## Monitoring Both Sources

### Agent Status via Redis

```python
import redis.asyncio as redis

async def check_status():
    redis_client = await redis.from_url("redis://localhost")
    
    # Get metrics for all agents
    agents = await redis_client.keys("metrics:*")
    
    for agent_key in agents:
        metrics = await redis_client.hgetall(agent_key)
        agent_id = agent_key.decode().split(":")[1]
        print(f"\nAgent {agent_id[:8]}...")
        for k, v in metrics.items():
            print(f"  {k.decode()}: {v.decode()}")
    
    await redis_client.close()

asyncio.run(check_status())
```

### Prometheus Metrics

```yaml
# /etc/prometheus/prometheus.yml
scrape_configs:
  - job_name: 'atlas-polygon-l1'
    static_configs:
      - targets: ['localhost:8081']
  
  - job_name: 'atlas-binance-l1'
    static_configs:
      - targets: ['localhost:8082']
```

**Alert Rules:**
```yaml
groups:
- name: atlas-l1-data
  rules:
  - alert: PolygonDisconnected
    expr: atlas_polygon_connected == 0
    for: 2m
  
  - alert: BinanceDisconnected
    expr: atlas_binance_connected == 0
    for: 2m
  
  - alert: L1DataLag
    expr: time() - max(atlas_data_timestamp) > 300
    for: 5m
    annotations:
      summary: "L1 data is stale (>5 min old)"
```

## Use Cases

### Real-time arbitrage (Stocks + Crypto)
- Monitor price differences between traditional and crypto markets
- Track correlated assets

### Cross-asset analysis
- Analyze correlations between stocks and crypto
- Build multi-asset strategies

### Risk management
- Track exposure across both markets
- Monitor liquidity and spreads

### Feature engineering
- Combine market microstructure from both sources
- Train models on unified data

## Performance & Scaling

### Estimated Throughput
- **Polygon**: 10,000+ messages/sec (1000+ symbols)
- **Binance**: 50,000+ messages/sec (100+ pairs)
- **Combined**: 60,000+ messages/sec

### Resource Usage
- **Memory**: ~100MB base + scalable
- **CPU**: <10% under full load
- **Network**: ~5 Mbps (stock) + ~10 Mbps (crypto)

### Database Impact
- **Write rate**: 1000+ writes/sec
- **Storage**: ~100GB per month (uncompressed)
- **Compression**: Automatic, ~10:1 ratio

## Integration with Downstream Layers

### L2 Strategy Layer
```python
# Access both stock and crypto market data
stock_df = await ts_client.get_bars('AAPL', start, end, '1m')  # Polygon
crypto_df = await ts_client.get_bars('BTCUSDT', start, end, '1m')  # Binance
```

### L3 Backtest Layer
```sql
-- Backtest on combined historical data
SELECT * FROM market_data_l2
WHERE time BETWEEN '2024-01-01' AND '2024-12-31'
ORDER BY time ASC;
```

### L4 Risk Layer
```sql
-- Monitor current exposure across both markets
SELECT source, symbol, SUM(size) as total_exposure
FROM order_flow
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY source, symbol;
```

## Troubleshooting

### Both agents running but no data
1. Check TimescaleDB is accepting writes
2. Verify API keys (POLYGON_API_KEY in .env)
3. Check firewall allows outbound WebSocket connections
4. Review logs for both agents

### Polygon running, Binance failing
- Verify CRYPTO_PAIRS format (must be uppercase, e.g., BTCUSDT)
- Check Binance WebSocket endpoint availability
- Confirm no rate limiting from Binance

### High memory usage with both agents
- Reduce number of symbols (WATCHLIST, CRYPTO_PAIRS)
- Split into separate instances by pair category
- Increase database cleanup frequency

## Files & Structure

```
atlas/agents/l1_data/
├── polygon_ws_agent.py      # Stock data agent
├── binance_ws_agent.py       # Crypto data agent
├── examples.py               # Polygon examples
├── binance_examples.py       # Binance examples
├── README.md                 # Polygon documentation
└── BINANCE.md                # Binance documentation

atlas/data/ingestion/
├── polygon_ws_client.py      # Stock client
├── binance_ws_client.py      # Crypto client
└── __init__.py               # Module exports

atlas/data/storage/
└── timescale_client.py       # Unified database layer
```

## Next Steps

1. **Verify Setup**: Run `python verify_setup.py`
2. **Start Agents**: Use systemd/Docker/Python to start both
3. **Monitor**: Check logs and database
4. **Integrate**: Build L2-L5 strategies using combined data

## Support

- **Polygon**: See `atlas/agents/l1_data/README.md`
- **Binance**: See `atlas/agents/l1_data/BINANCE.md`
- **Deployment**: See root `DEPLOYMENT.md`
- **Setup**: See `verify_setup.py`

---

**L1 Data Layer Complete**: Both stock and crypto data sources integrated!
