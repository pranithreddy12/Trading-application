
import asyncio
import pandas as pd
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
from sqlalchemy import text
import io

async def upload_historical_data():
    settings = get_settings()
    db = TimescaleClient(settings.database_url)
    
    print("Loading atlas_historical_universe.csv...")
    df = pd.read_csv("historical_data/atlas_historical_universe.csv")
    print(f"Loaded {len(df)} rows.")

    # Convert timestamps to proper datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # We'll batch insert to avoid memory issues
    batch_size = 5000
    
    async with db.engine.begin() as conn:
        print("Inserting data into market_data_l1...")
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            
            # Prepare rows
            rows_to_insert = []
            for _, row in batch.iterrows():
                rows_to_insert.append({
                    "time": row['timestamp'],
                    "symbol": row['symbol'],
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close']),
                    "volume": float(row['volume']),
                    "source": str(row['source']),
                    "interval": "1h" if row['asset_class'] == 'crypto' else "1d",
                    "asset_class": str(row['asset_class'])
                })
            
            await conn.execute(text("""
                INSERT INTO market_data_l1 (time, symbol, open, high, low, close, volume, source, interval, asset_class)
                VALUES (:time, :symbol, :open, :high, :low, :close, :volume, :source, :interval, :asset_class)
                ON CONFLICT (time, symbol) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """), rows_to_insert)
            
            print(f"Inserted {i + len(batch)} / {len(df)} rows...")
            
    print("Historical data upload complete.")

if __name__ == '__main__':
    asyncio.run(upload_historical_data())
