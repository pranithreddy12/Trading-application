# Binance WebSocket Agent - Quick Reference

## 5-Minute Quick Start

### 1. Configuration
```bash
# Add to .env
CRYPTO_PAIRS=BTCUSDT,ETHUSDT,BNBUSDT
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/atlas_db
REDIS_URL=redis://localhost:6379
```

### 2. Run Example
```bash
cd atlas/agents/l1_data
python binance_examples.py
```

### 3. Check Logs
```bash
tail -f /tmp/atlas_binance_*.log
```

### 4. Query Data
```sql
-- Recent trades
SELECT * FROM order_flow WHERE source='binance' 
ORDER BY time DESC LIMIT 10;

-- Recent depth
SELECT * FROM market_data_l2 WHERE source='binance'
ORDER BY time DESC LIMIT 10;
```

## API Reference

### Client Usage
```python
from atlas.data.ingestion import BinanceWebSocketClient

# Create client
client = BinanceWebSocketClient(
    trading_pairs=["BTCUSDT", "ETHUSDT"],
    message_handler=async_handler,
    stream_types=["trade", "depth20@100ms"]
)

# Start/stop
await client.start()    # Connect and listen
await client.stop()     # Graceful shutdown

# Status
status = client.get_status()
# Returns: {connected, subscribed_pairs, retry_count, stream_types}
```

### Agent Usage
```python
from atlas.agents.l1_data import BinanceWebSocketAgent
import redis.asyncio as redis

# Create agent
redis_client = await redis.from_url("redis://localhost")
agent = BinanceWebSocketAgent(redis_client, db_url)

# Lifecycle
await agent.start()      # Start agent
await agent.stop()       # Stop agent
await agent.pause()      # Pause processing
await agent.resume()     # Resume processing

# Metrics
agent._messages_received     # Total messages
agent._trades_received       # Trade count
agent._depth_received        # Depth updates
agent._db_errors             # Database errors
```

## Database Schema

### order_flow (Trades)
```sql
CREATE TABLE order_flow (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC NOT NULL,
    size NUMERIC NOT NULL,
    side TEXT NOT NULL,              -- "buy", "sell", "unknown"
    aggressor TEXT NOT NULL,         -- trade ID for Binance
    source TEXT DEFAULT 'binance'
);

-- Query last hour
SELECT * FROM order_flow 
WHERE source='binance' AND time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC;
```

### market_data_l2 (Orderbook Depth)
```sql
CREATE TABLE market_data_l2 (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    bids JSONB NOT NULL,             -- {"price": quantity, ...}
    asks JSONB NOT NULL,             -- {"price": quantity, ...}
    spread NUMERIC,                   -- ask - bid
    mid_price NUMERIC,                -- (bid + ask) / 2
    source TEXT DEFAULT 'binance'
);

-- Query latest depth
SELECT * FROM market_data_l2 
WHERE source='binance' AND time > NOW() - INTERVAL '1 minute'
ORDER BY time DESC LIMIT 1 PARTITION BY symbol;
```

## Stream Types

### @trade (Real-time Trades)
```json
{
  "e": "trade",                  // Event type
  "E": 1672531200000,            // Event time (ms)
  "s": "BTCUSDT",                // Symbol
  "t": 12345,                    // Trade ID
  "p": "65000.0",                // Price
  "q": "0.5",                    // Quantity
  "b": 88,                       // Buyer order ID
  "a": 50,                       // Seller order ID
  "T": 1672531200123,            // Trade time (ms)
  "m": true                      // Is buyer maker?
}
```
**Frequency**: Real-time (1-10 ms between trades)
**Use**: Trade flow analysis, execution tracking

### @depth20@100ms (Orderbook Depth)
```json
{
  "e": "depthUpdate",            // Event type
  "E": 1672531200000,            // Event time (ms)
  "s": "ETHUSDT",                // Symbol
  "U": 123456,                   // First update ID
  "u": 123457,                   // Final update ID
  "b": [                         // Bids
    ["3500.0", "10.5"],          // [price, quantity]
    ["3499.9", "20.0"]
  ],
  "a": [                         // Asks
    ["3500.1", "15.0"],          // [price, quantity]
    ["3500.2", "25.5"]
  ]
}
```
**Frequency**: Every 100ms per pair
**Use**: Orderbook analysis, spread monitoring, liquidity assessment

## Common Tasks

### Monitor Agent in Real-Time
```python
import asyncio
import redis.asyncio as redis
from atlas.agents.l1_data import BinanceWebSocketAgent

async def monitor():
    redis_client = await redis.from_url("redis://localhost")
    agent = BinanceWebSocketAgent(redis_client, db_url)
    
    await agent.start()
    
    try:
        while True:
            await asyncio.sleep(10)
            print(f"Messages: {agent._messages_received}")
            print(f"Trades: {agent._trades_received}")
            print(f"Depth: {agent._depth_received}")
            print(f"Errors: {agent._db_errors}")
    finally:
        await agent.stop()

asyncio.run(monitor())
```

### Add New Trading Pairs Dynamically
```python
# Update trading pairs at runtime
agent.trading_pairs.extend(["LTCUSDT", "XRPUSDT"])

# Or replace entirely
agent.trading_pairs = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
```

### Query Trade Volume by Pair
```sql
SELECT 
  symbol,
  COUNT(*) as trade_count,
  SUM(size) as total_volume,
  AVG(price) as avg_price,
  MIN(price) as low_price,
  MAX(price) as high_price
FROM order_flow
WHERE source='binance' AND time > NOW() - INTERVAL '1 day'
GROUP BY symbol
ORDER BY total_volume DESC;
```

### Query Spread Over Time
```sql
SELECT 
  time,
  symbol,
  spread,
  mid_price
FROM market_data_l2
WHERE source='binance' AND symbol='BTCUSDT' 
  AND time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC;
```

### Calculate VWAP from Trades
```sql
SELECT 
  symbol,
  SUM(price * size) / SUM(size) as vwap
FROM order_flow
WHERE source='binance' AND time > NOW() - INTERVAL '1 hour'
GROUP BY symbol;
```

## Configuration Settings

### agent.trading_pairs
List of USDT pairs to subscribe to.
```python
agent.trading_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
```

### agent.stream_types
Stream types to subscribe to.
```python
agent.stream_types = ["trade", "depth20@100ms"]
# or individual: ["trade"] or ["depth20@100ms"]
```

### Exponential Backoff Settings
```python
BASE_BACKOFF = 1          # Start at 1 second
MAX_BACKOFF = 32          # Cap at 32 seconds
# Automatically: 1s → 2s → 4s → 8s → 16s → 32s → 32s...
```

## Error Handling

### Connection Errors
```
ConnectionRefused → Automatic reconnection with backoff
```

### Message Parsing Errors
```
Invalid JSON → Logged, skipped, continue
```

### Database Write Errors
```
DB Connection Lost → Error counted, agent continues
DB Write Timeout → Error counted, message skipped
```

## Monitoring

### Redis Metrics
```python
redis_client = await redis.from_url("redis://localhost")

# Get agent metrics
metrics = await redis_client.hgetall(f"metrics:BinanceWebSocketAgent")
# Returns: {_messages_received: X, _trades_received: Y, ...}
```

### Log Files
```bash
# Rotate logs
tail -f /tmp/atlas_binance_*.log

# Search for errors
grep ERROR /tmp/atlas_binance_*.log
```

### Database Queries for Health
```sql
-- Last message time
SELECT MAX(time) as last_update FROM order_flow 
WHERE source='binance';

-- Records per symbol (last hour)
SELECT symbol, COUNT(*) as count
FROM order_flow
WHERE source='binance' AND time > NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY count DESC;

-- Records per symbol (last hour, depth)
SELECT symbol, COUNT(*) as count
FROM market_data_l2
WHERE source='binance' AND time > NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY count DESC;
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| No trades appearing | Pair format wrong | Use uppercase USDT format: BTCUSDT not btcusd |
| High error rate | DB connection lost | Restart agent, check PostgreSQL |
| Memory growing | Message queue buildup | Reduce number of pairs or restart |
| Reconnecting often | Network unstable | Check internet, firewall rules |
| Missing trades | Lag in processing | Check CPU/memory, reduce pairs |

## Code Examples

### Example 1: Basic Usage
```python
import asyncio
import redis.asyncio as redis
from atlas.agents.l1_data import BinanceWebSocketAgent

async def main():
    redis_client = await redis.from_url("redis://localhost")
    agent = BinanceWebSocketAgent(redis_client, "postgresql://localhost/atlas")
    
    await agent.start()
    print(f"Agent started: {agent.agent_id}")
    
    await asyncio.sleep(30)  # Run for 30 seconds
    await agent.stop()

asyncio.run(main())
```

### Example 2: Multiple Pairs with Monitoring
```python
async def monitor_pairs():
    redis_client = await redis.from_url("redis://localhost")
    agent = BinanceWebSocketAgent(redis_client, db_url)
    
    agent.trading_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    await agent.start()
    
    for _ in range(10):
        await asyncio.sleep(5)
        print(f"Received: {agent._messages_received} | "
              f"Trades: {agent._trades_received} | "
              f"Depth: {agent._depth_received}")
    
    await agent.stop()

asyncio.run(monitor_pairs())
```

### Example 3: Query Results
```python
import asyncpg

async def query_recent_trades():
    conn = await asyncpg.connect("postgresql://localhost/atlas")
    
    rows = await conn.fetch("""
        SELECT time, symbol, price, size, side
        FROM order_flow
        WHERE source='binance' AND time > NOW() - INTERVAL '1 hour'
        ORDER BY time DESC
        LIMIT 100
    """)
    
    for row in rows:
        print(f"{row['time']} | {row['symbol']} | ${row['price']} x {row['size']} ({row['side']})")
    
    await conn.close()

asyncio.run(query_recent_trades())
```

## Performance Tuning

### Optimize for High Throughput
- Increase number of worker threads in database
- Use connection pooling (default: 20 connections)
- Enable database query parallelization

### Optimize for Low Latency
- Reduce number of trading pairs
- Decrease database batch sizes
- Use SSD storage for TimescaleDB

### Monitor Performance
```sql
-- Check database write rate
SELECT time_bucket('1 minute', time) as minute, COUNT(*) as writes
FROM order_flow
WHERE source='binance' AND time > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;
```

## Integration with L2 Strategy

```python
# Read crypto OHLCV data for strategy
from atlas.data.storage import TimescaleClient

async def get_crypto_bars():
    ts_client = TimescaleClient(db_url)
    
    # Get last hour of 1-minute bars
    bars = await ts_client.get_bars(
        symbol="BTCUSDT",
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-01 01:00:00",
        interval="1m"
    )
    
    for bar in bars:
        print(f"{bar.time}: OHLCV = {bar.open}/{bar.high}/{bar.low}/{bar.close}/{bar.volume}")
```

## Quick Diagnostics

```bash
# Check agent is running
ps aux | grep BinanceWebSocketAgent

# Check database connectivity
psql -U user -d atlas_db -c "SELECT COUNT(*) FROM order_flow WHERE source='binance' AND time > NOW() - INTERVAL '1 hour';"

# Check Redis connectivity
redis-cli KEYS "metrics:*"

# Check recent logs
journalctl -u atlas-binance-l1 -n 50 -f
```

## References

- [Binance WebSocket API](https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams)
- [Trade Streams](https://binance-docs.github.io/apidocs/spot/en/#trade-streams)
- [Depth Streams](https://binance-docs.github.io/apidocs/spot/en/#top-20-bid-ask-information-streams)
- [TimescaleDB Queries](https://docs.timescale.com/api/latest/)
