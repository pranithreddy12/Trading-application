import asyncio
import math
import numpy as np
import pandas as pd
from loguru import logger
import asyncpg
from sqlalchemy import create_engine, text

from atlas.config.settings import get_settings

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 50:
        return pd.DataFrame()
        
    df = df.copy()
    
    # ── MINIMAL FEATURES FOR CONTROL BENCHMARK ──
    df["sma_10"] = df["close"].rolling(10).mean()
    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    
    df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()
    
    # MACD
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    
    # RSI (Wilder's Smoothing method usually uses EMA, but sticking to rolling mean for simplicity as in original agent)
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    df = df.dropna()
    return df


async def main():
    settings = get_settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(db_url)

    logger.info("Setting up bootstrap tables...")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS features_wide_bootstrap (
                time TIMESTAMPTZ NOT NULL,
                symbol TEXT NOT NULL,
                sma_10 NUMERIC,
                sma_20 NUMERIC,
                sma_50 NUMERIC,
                ema_12 NUMERIC,
                ema_26 NUMERIC,
                macd NUMERIC,
                macd_signal NUMERIC,
                rsi_14 NUMERIC,
                UNIQUE (time, symbol)
            );
        """))
        conn.execute(text("TRUNCATE TABLE features_wide_bootstrap;"))
        
    symbols = ["BTCUSDT", "ETHUSDT"]
    
    pool = await asyncpg.create_pool(db_url)
    
    for symbol in symbols:
        logger.info(f"=== Processing Features for {symbol} ===")
        query = """
            SELECT time AS timestamp, open, high, low, close, volume
            FROM market_data_l1_bootstrap
            WHERE symbol = $1
            ORDER BY time ASC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, symbol)
            
        if not rows:
            logger.warning(f"No data found for {symbol} in market_data_l1_bootstrap")
            continue
            
        df = pd.DataFrame([dict(r) for r in rows])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
        logger.info(f"Loaded {len(df)} rows from DB for {symbol}")
        
        feature_df = compute_features(df)
        logger.info(f"Computed {len(feature_df)} feature rows after warmup drop")
        
        if feature_df.empty:
            continue
            
        write_df = feature_df[["timestamp", "sma_10", "sma_20", "sma_50", "ema_12", "ema_26", "macd", "macd_signal", "rsi_14"]].copy()
        write_df = write_df.rename(columns={"timestamp": "time"})
        write_df["symbol"] = symbol
        
        cols_order = ["time", "symbol", "sma_10", "sma_20", "sma_50", "ema_12", "ema_26", "macd", "macd_signal", "rsi_14"]
        write_df = write_df[cols_order]
        
        logger.info(f"Writing {len(write_df)} rows to features_wide_bootstrap...")
        try:
            write_df.to_sql("features_wide_bootstrap", engine, if_exists="append", index=False, chunksize=5000, method='multi')
            logger.info(f"✓ Successfully wrote features for {symbol}")
        except Exception as e:
            logger.error(f"Failed to write features for {symbol}: {e}")

    logger.info("=== Feature Bootstrap Complete ===")
    
    # Verification query
    with engine.connect() as conn:
        res = conn.execute(text("SELECT symbol, count(*) FROM features_wide_bootstrap GROUP BY symbol;"))
        logger.info("Verification Counts:")
        for row in res.fetchall():
            logger.info(f"  {row[0]} -> {row[1]}")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
