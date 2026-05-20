# Polygon WebSocket Agent - Quick Reference Guide

## Start Here

### 1. Setup Verification (2 minutes)
```bash
python verify_setup.py
```
Checks:
- ✅ Configuration (.env)
- ✅ Database connectivity
- ✅ Redis connectivity
- ✅ Polygon API key
- ✅ Agent import

### 2. Run Agent (Production)
```bash
# Systemd
sudo systemctl start atlas-polygon-l1

# Direct
python -m atlas.agents.l1_data.polygon_ws_agent

# Docker
docker-compose up -d atlas-polygon-l1
```

### 3. Monitor
```bash
# View logs
tail -f /var/log/atlas/polygon-l1.log

# Check status
redis-cli HGET metrics:{agent_id} connected

# Query database
psql -d atlas_db -c "SELECT COUNT(*) FROM market_data_l2 WHERE time > NOW() - INTERVAL '1 hour';"
```

---

## API Quick Reference

### Initialize Agent
```python
from atlas.agents.l1_data import PolygonWebSocketAgent
import redis.asyncio as redis
from atlas.config.settings import get_settings

redis_client = await redis.from_url("redis://localhost")
settings = get_settings()
agent = PolygonWebSocketAgent(redis_client, settings.database_url)
```

### Start Agent
```python
await agent.start()
# Agent runs with:
# - Automatic heartbeat every 10 seconds
# - WebSocket reconnection with exponential backoff
# - Message processing and database writes
# - Metrics collection

await asyncio.sleep(300)  # Run for 5 minutes
await agent.stop()
```

### Access WebSocket Client
```python
status = agent.ws_client.get_status()
# Returns:
# {
#     'connected': True,
#     'authenticated': True,
#     'subscribed_symbols': ['AAPL', 'MSFT'],
#     'retry_count': 0,
#     'stream_types': ['Q', 'T', 'A']
# }
```

### Add/Remove Symbols
```python
await agent.ws_client.add_symbols(["TSLA", "NVDA"])
await agent.ws_client.remove_symbols(["MSFT"])
```

### Check Metrics
```python
print(f"Received: {agent._messages_received}")
print(f"Processed: {agent._messages_processed}")
print(f"Failed: {agent._messages_failed}")
print(f"DB Errors: {agent._db_errors}")
```

---

## Database Schema

### Tables

**market_data_l2** (Quotes)
```
time       | TIMESTAMPTZ
symbol     | TEXT
bids       | JSONB
asks       | JSONB
spread     | NUMERIC
mid_price  | NUMERIC
```

**order_flow** (Trades)
```
time      | TIMESTAMPTZ
symbol    | TEXT
price     | NUMERIC
size      | NUMERIC
side      | TEXT (buy/sell/unknown)
aggressor | TEXT (exchange)
```

**market_data_l1** (OHLCV)
```
time     | TIMESTAMPTZ
symbol   | TEXT
open     | NUMERIC
high     | NUMERIC
low      | NUMERIC
close    | NUMERIC
volume   | NUMERIC
source   | TEXT (polygon)
interval | TEXT (1m)
```

### Query Examples

**Last quote for AAPL**
```sql
SELECT bid, ask, bid_size, ask_size, time
FROM market_data_l2
WHERE symbol = 'AAPL'
ORDER BY time DESC
LIMIT 1;
```

**Trade volume last hour**
```sql
SELECT COUNT(*) as trades, SUM(size) as volume
FROM order_flow
WHERE symbol = 'AAPL' AND time > NOW() - INTERVAL '1 hour';
```

**1-day OHLCV**
```sql
SELECT time, open, high, low, close, volume
FROM market_data_l1
WHERE symbol = 'AAPL' AND interval = '1m'
ORDER BY time DESC
LIMIT 1440;
```

---

## Stream Types

| Stream | Type | Data | Table | Frequency |
|--------|------|------|-------|-----------|
| Q.* | Quote | bid/ask/size | market_data_l2 | 100-1000 ms |
| T.* | Trade | price/size/side | order_flow | milliseconds |
| A.* | Aggregate | OHLCV | market_data_l1 | 1 minute |

---

## Configuration

### Environment Variables
```env
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/atlas_db
REDIS_URL=redis://localhost:6379
POLYGON_API_KEY=your_key_here
WATCHLIST=AAPL,MSFT,GOOGL

# Optional
ENVIRONMENT=production
BINANCE_API_KEY=...
BINANCE_SECRET=...
SLACK_WEBHOOK_URL=...
```

### Runtime Configuration
```python
# Edit in agent
agent.symbols = ["AAPL", "MSFT"]
agent.stream_types = ["Q", "T", "A"]
```

---

## Common Issues & Solutions

### "Connection refused"
```bash
# Check Redis
redis-cli ping

# Check Database
psql -d atlas_db -c "SELECT 1;"

# Check Polygon API
curl -H "Authorization: Bearer $POLYGON_API_KEY" \
  https://api.polygon.io/v1/markets/stocks/quotes
```

### "No data in database"
```bash
# Check agent is running
ps aux | grep polygon_ws_agent

# Check logs
tail -f /var/log/atlas/polygon-l1.log

# Check subscriptions
redis-cli GET "metrics:{agent_id}"

# Verify symbols
SELECT DISTINCT symbol FROM market_data_l2 LIMIT 10;
```

### "High failure rate"
```bash
# Check error logs
grep -i "error" /var/log/atlas/polygon-l1.log

# Check database disk space
df -h /var/lib/postgresql/data

# Check connection pool
SELECT count(*) FROM pg_stat_activity WHERE datname='atlas_db';
```

### "Memory usage high"
```bash
# Check process memory
ps aux | grep polygon_ws_agent
top -p <pid>

# Reduce symbols
WATCHLIST=AAPL,MSFT  # Smaller watchlist

# Adjust database retention
SELECT add_retention_policy('market_data_l1', INTERVAL '30 days');
```

---

## Performance Tuning

### Increase Throughput
```python
# Parallel message processing
# (Modify _handle_message in agent)
asyncio.create_task(self._process_message_async(msg))
```

### Reduce Memory Usage
```python
# Fewer symbols
WATCHLIST=AAPL,MSFT,GOOGL

# Fewer stream types
agent.stream_types = ["Q", "A"]  # Skip trades
```

### Lower Database Load
```sql
-- Add compression
ALTER TABLE market_data_l1 SET (timescaledb.compress);
SELECT add_compression_policy('market_data_l1', INTERVAL '1 day');

-- Add retention policy
SELECT add_retention_policy('market_data_l1', INTERVAL '90 days');
```

---

## Monitoring Commands

### Real-time Metrics
```bash
# Watch messages/sec
watch -n1 'redis-cli HGET metrics:{agent_id} messages_received'

# Watch connection status
watch -n5 'redis-cli HGET metrics:{agent_id} connected'

# Watch database writes
watch -n10 'psql -d atlas_db -c "SELECT COUNT(*) FROM market_data_l2 WHERE time > NOW() - INTERVAL '\'1 min\'';"'
```

### Historical Analysis
```sql
-- Messages by minute
SELECT 
  DATE_TRUNC('minute', time) as minute,
  COUNT(*) as count
FROM market_data_l2
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY 1
ORDER BY 1;

-- Symbols with highest volume
SELECT symbol, COUNT(*) as trades
FROM order_flow
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY trades DESC
LIMIT 10;

-- Data freshness
SELECT symbol, MAX(time) as last_update
FROM market_data_l1
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY last_update DESC
LIMIT 10;
```

---

## File Locations

```
atlas/
├── data/
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── polygon_ws_client.py        ← WebSocket client
│   └── storage/
│       ├── timescale_client.py         ← Data models & DB methods (modified)
│       └── schema.sql                  ← Database schema
├── agents/
│   └── l1_data/
│       ├── __init__.py
│       ├── polygon_ws_agent.py         ← Agent implementation
│       ├── examples.py                 ← Usage examples
│       └── README.md                   ← Full documentation
├── core/
│   └── agent_base.py                   ← Base agent class (not modified)
├── config/
│   └── settings.py                     ← Settings loader (not modified)
└── requirements.txt                    ← Dependencies (not modified)

tests/
└── test_polygon_ws_agent.py            ← Unit tests

root/
├── DEPLOYMENT.md                       ← Production setup
├── IMPLEMENTATION_SUMMARY.md           ← This file context
└── verify_setup.py                     ← Setup verification
```

---

## Development Workflow

### 1. Local Development
```bash
# Activate environment
source venv/bin/activate

# Run verification
python verify_setup.py

# Run examples
python atlas/agents/l1_data/examples.py

# Run tests
pytest tests/test_polygon_ws_agent.py -v

# Start agent
python -m atlas.agents.l1_data.polygon_ws_agent
```

### 2. Add Custom Handler
```python
# Extend PolygonWebSocketAgent
class CustomAgent(PolygonWebSocketAgent):
    async def _handle_quote(self, message):
        await super()._handle_quote(message)
        # Add custom logic
        await self._send_to_kafka(message)
```

### 3. Integration with L2-L5
```python
# Read data in downstream agent
async def run(self):
    df = await ts_client.get_bars(
        'AAPL', 
        start=datetime.now() - timedelta(hours=1),
        end=datetime.now(),
        interval='1m'
    )
    # Process bars for strategy
```

---

## Related Components

- **L2 Strategy Layer**: Reads L1 data, generates signals
- **L3 Backtest Layer**: Analyzes historical L1 data
- **L4 Risk Layer**: Monitors position risk
- **L5 Execution Layer**: Executes based on signals
- **Meta Orchestrator**: Coordinates all layers
- **Redis**: Inter-agent communication
- **TimescaleDB**: Time-series data storage

---

## Resources

- [README](atlas/agents/l1_data/README.md) - Full API documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production setup guide
- [Tests](tests/test_polygon_ws_agent.py) - Example usage
- [Examples](atlas/agents/l1_data/examples.py) - Working examples
- [Polygon Docs](https://polygon.io/docs/) - Polygon API reference

---

## Support

**Quick checks:**
1. `python verify_setup.py` - Verify configuration
2. `tail -f /var/log/atlas/polygon-l1.log` - Check logs
3. `redis-cli HGET metrics:{id} connected` - Check connection
4. `psql -d atlas_db -c "SELECT COUNT(*) FROM market_data_l2;"` - Check data

**For help:**
- See DEPLOYMENT.md Troubleshooting section
- Review README.md for detailed documentation
- Check test file for usage examples

---

**Last Updated**: May 11, 2026  
**Version**: 1.0.0
