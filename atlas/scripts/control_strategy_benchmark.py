import asyncio
import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import create_engine, text
from atlas.config.settings import get_settings
import uuid
import json
from datetime import datetime

class SimpleBacktester:
    def __init__(self, df: pd.DataFrame, initial_capital=10000.0, fee_pct=0.001):
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.fee_pct = fee_pct

    def run(self, strategy_name: str, signals: pd.Series) -> dict:
        """
        signals: 1 for long entry, -1 for short entry, 0 for neutral
        We assume we hold position until signal changes.
        """
        df = self.df
        df['signal'] = signals
        df['position'] = df['signal'].replace(0, np.nan).ffill().fillna(0)
        
        # Calculate returns
        df['next_open'] = df['open'].shift(-1)
        
        # Find trades
        df['trade'] = df['position'].diff()
        
        trades = []
        in_pos = False
        entry_price = 0
        entry_time = None
        pos_type = 0
        
        for idx, row in df.iterrows():
            if row['trade'] != 0 and not pd.isna(row['trade']):
                # Exit previous position
                if in_pos:
                    exit_price = row['open'] # Assume execute at open of candle following signal
                    exit_time = row['time']
                    pnl_pct = (exit_price - entry_price) / entry_price if pos_type == 1 else (entry_price - exit_price) / entry_price
                    pnl_pct -= (self.fee_pct * 2) # entry and exit fee
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': exit_time,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'side': 'long' if pos_type == 1 else 'short',
                        'pnl_pct': pnl_pct
                    })
                    in_pos = False
                
                # Enter new position
                if row['position'] != 0:
                    in_pos = True
                    entry_price = row['open']
                    entry_time = row['time']
                    pos_type = row['position']
                    
        # Calculate metrics
        total_trades = len(trades)
        if total_trades > 0:
            pnl_pcts = [t['pnl_pct'] for t in trades]
            win_rate = len([p for p in pnl_pcts if p > 0]) / total_trades
            gross_edge = sum([p + (self.fee_pct * 2) for p in pnl_pcts])
            cost_burden = total_trades * self.fee_pct * 2
            net_return = sum(pnl_pcts)
        else:
            win_rate = 0.0
            gross_edge = 0.0
            cost_burden = 0.0
            net_return = 0.0
            
        return {
            'strategy': strategy_name,
            'total_trades': total_trades,
            'win_rate': round(win_rate * 100, 2),
            'gross_edge': round(gross_edge * 100, 2),
            'cost_burden': round(cost_burden * 100, 2),
            'net_return': round(net_return * 100, 2)
        }

async def main():
    settings = get_settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(db_url)
    
    symbols = ["BTCUSDT", "ETHUSDT"]
    results = []

    for symbol in symbols:
        logger.info(f"--- Running Benchmarks for {symbol} ---")
        query = f"""
            SELECT m.time, m.open, m.high, m.low, m.close, m.volume,
                   f.sma_10, f.sma_20, f.sma_50, f.ema_12, f.ema_26, f.macd, f.macd_signal, f.rsi_14
            FROM market_data_l1_bootstrap m
            JOIN features_wide_bootstrap f ON m.time = f.time AND m.symbol = f.symbol
            WHERE m.symbol = '{symbol}'
            ORDER BY m.time ASC
        """
        df = pd.read_sql(query, engine)
        
        # We missed SMA 30 in DB, calculate it locally for the SMA 10/30 benchmark
        df['sma_30'] = df['close'].rolling(30).mean()
        
        backtester = SimpleBacktester(df)
        
        # 1. Buy and Hold
        sig_bh = pd.Series(0, index=df.index)
        sig_bh.iloc[0] = 1 # Buy at start
        res = backtester.run("Buy-and-Hold", sig_bh)
        res['symbol'] = symbol
        results.append(res)
        
        # 2. SMA 20/50 Crossover
        buy = (df['sma_20'] > df['sma_50']) & (df['sma_20'].shift(1) <= df['sma_50'].shift(1))
        sell = (df['sma_20'] < df['sma_50']) & (df['sma_20'].shift(1) >= df['sma_50'].shift(1))
        sig = pd.Series(0, index=df.index)
        sig[buy] = 1
        sig[sell] = -1
        res = backtester.run("SMA 20/50", sig)
        res['symbol'] = symbol
        results.append(res)

        # 3. SMA 10/30 Crossover
        buy = (df['sma_10'] > df['sma_30']) & (df['sma_10'].shift(1) <= df['sma_30'].shift(1))
        sell = (df['sma_10'] < df['sma_30']) & (df['sma_10'].shift(1) >= df['sma_30'].shift(1))
        sig = pd.Series(0, index=df.index)
        sig[buy] = 1
        sig[sell] = -1
        res = backtester.run("SMA 10/30", sig)
        res['symbol'] = symbol
        results.append(res)
        
        # 4. RSI Mean Reversion (Buy < 30, Sell > 70)
        buy = (df['rsi_14'] < 30)
        sell = (df['rsi_14'] > 70)
        sig = pd.Series(0, index=df.index)
        sig[buy] = 1
        sig[sell] = -1
        res = backtester.run("RSI Mean Reversion", sig)
        res['symbol'] = symbol
        results.append(res)
        
        # 5. MACD Crossover
        buy = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        sell = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))
        sig = pd.Series(0, index=df.index)
        sig[buy] = 1
        sig[sell] = -1
        res = backtester.run("MACD Crossover", sig)
        res['symbol'] = symbol
        results.append(res)

    results_df = pd.DataFrame(results)
    print("\n================ BENCHMARK RESULTS ================")
    print(results_df.to_string(index=False))
    print("===================================================\n")
    
    # Save to CSV for the validator agent step
    results_df.to_csv("historical_data/benchmark_results.csv", index=False)
    logger.info("Saved benchmark_results.csv")

if __name__ == "__main__":
    asyncio.run(main())
