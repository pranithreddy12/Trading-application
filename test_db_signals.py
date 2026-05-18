import asyncio
from atlas.data.storage.timescale_client import TimescaleClient
from atlas.config.settings import get_settings
import pandas as pd
from sqlalchemy import text

async def main():
    settings = get_settings()
    timescale = TimescaleClient(settings.database_url)
    await timescale.connect()
    
    symbol = "NVDA"
    async with timescale.engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT time, open, high, low, close, volume
                FROM market_data_l1
                WHERE symbol = :symbol
                ORDER BY time ASC
                """
            ),
            {"symbol": symbol},
        )
        rows = result.fetchall()

    df = pd.DataFrame(
        rows,
        columns=["time", "open", "high", "low", "close", "volume"],
    )
    df["time"] = pd.to_datetime(df["time"])
    
    async with timescale.engine.connect() as conn:
        feat_result = await conn.execute(
            text(
                """
                SELECT time, feature_name, value
                FROM features
                WHERE symbol = :symbol
                ORDER BY time ASC
                """
            ),
            {"symbol": symbol},
        )
        feat_rows = feat_result.fetchall()

    if feat_rows:
        feat_df = pd.DataFrame(
            feat_rows,
            columns=["time", "feature_name", "value"],
        )
        feat_df["time"] = pd.to_datetime(feat_df["time"])
        feat_pivot = feat_df.pivot_table(
            index="time",
            columns="feature_name",
            values="value",
            aggfunc="first",
        ).reset_index()
        feat_pivot.columns.name = None
        feat_pivot.columns = [str(c) for c in feat_pivot.columns]

        df = df.merge(feat_pivot, on="time", how="left")
        df = df.sort_values("time")
        df = df.ffill().bfill()
        
        print("Available columns:", df.columns.tolist())
        
        if 'rsi_14' in df.columns:
            entry = df['rsi_14'] < 40
            exit_ = df['rsi_14'] > 60
            
            signals = pd.Series(0, index=df.index)
            signals.loc[entry.fillna(False)] = 1
            signals.loc[exit_.fillna(False)] = -1
            
            overlap = entry & exit_
            signals.loc[overlap.fillna(False)] = 0
            
            entry_count = (signals == 1).sum()
            exit_count = (signals == -1).sum()
            print(f"Total Rows: {len(df)}")
            print(f"Entry Count: {entry_count}")
            print(f"Exit Count: {exit_count}")
        else:
            print("rsi_14 not found in columns")

if __name__ == '__main__':
    asyncio.run(main())
