import asyncio
import pandas as pd
from sqlalchemy import text, create_engine
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_bootstrap_table(db: TimescaleClient):
    async with db.engine.begin() as conn:
        logger.info("Creating market_data_l1_bootstrap table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS market_data_l1_bootstrap (
                time TIMESTAMPTZ NOT NULL,
                symbol TEXT NOT NULL,
                open NUMERIC NOT NULL,
                high NUMERIC NOT NULL,
                low NUMERIC NOT NULL,
                close NUMERIC NOT NULL,
                volume NUMERIC NOT NULL,
                source TEXT NOT NULL,
                interval TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                ingestion_time TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (time, symbol)
            );
        """))
        try:
            await conn.execute(text("SELECT create_hypertable('market_data_l1_bootstrap', 'time', if_not_exists => TRUE);"))
            logger.info("Created hypertable market_data_l1_bootstrap")
        except Exception as e:
            logger.info(f"Hypertable notice: {e}")

async def ingest_crypto():
    csv_path = r"C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS\atlas\historical_data\all_crypto_master.csv"
    logger.info(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Filter for BTC and ETH
    df = df[df['symbol'].isin(['BTCUSDT', 'ETHUSDT'])].copy()
    
    # Add required columns
    df['interval'] = '1h'
    df['source'] = 'historical_backfill'
    df['time'] = pd.to_datetime(df['timestamp'])
    
    # Drop old timestamp if exists
    if 'timestamp' in df.columns:
        df = df.drop(columns=['timestamp'])
        
    df['ingestion_time'] = pd.Timestamp.utcnow()
    
    cols = ['time', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'source', 'interval', 'asset_class', 'ingestion_time']
    df = df[cols]
    
    # Deduplicate before insertion just in case
    df = df.drop_duplicates(subset=['time', 'symbol'])
    
    logger.info(f"Data shape to ingest: {df.shape}")
    
    db = TimescaleClient(settings.database_url)
    await db.connect()
    await create_bootstrap_table(db)
    
    logger.info("Inserting data into market_data_l1_bootstrap...")
    # create sync engine for pandas
    sync_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = create_engine(sync_url)
    
    try:
        # Use ON CONFLICT DO NOTHING by doing it manually or just let to_sql try and if it fails, we handle it
        # Since we use UNIQUE constraint, and we deduplicated, standard append should work if table is empty
        # If it's not empty, it might throw duplicate key value violates unique constraint.
        # Let's clear the bootstrap table for idempotency
        async with db.engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE market_data_l1_bootstrap;"))
            logger.info("Truncated market_data_l1_bootstrap for fresh insertion.")

        df.to_sql('market_data_l1_bootstrap', sync_engine, if_exists='append', index=False, chunksize=5000, method='multi')
        logger.info("Ingestion completed successfully.")
        
        # Verify row counts
        async with db.engine.connect() as conn:
            res = await conn.execute(text("SELECT symbol, count(*) FROM market_data_l1_bootstrap GROUP BY symbol;"))
            for row in res.fetchall():
                logger.info(f"DB COUNT: {row[0]} -> {row[1]}")

    except Exception as e:
        logger.error(f"Error during ingestion: {e}")

if __name__ == "__main__":
    asyncio.run(ingest_crypto())
