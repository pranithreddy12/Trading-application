import pandas as pd
from loguru import logger
import os

def validate_results(csv_path: str):
    logger.info(f"Loading benchmark results from {csv_path}")
    if not os.path.exists(csv_path):
        logger.error(f"{csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    # Validation Rules
    # 1. Total trades < 10 -> 'repair_candidate' (Insufficient sample)
    # 2. Net Return < 0 -> 'repair_candidate' (Bleeding edge)
    # 3. Net Return > 0 AND Win Rate > 50 AND Trades > 100 -> 'validated'
    # 4. Otherwise -> 'research_candidate' (Edge exists, but weak/unstable)
    
    tier_results = []
    
    for _, row in df.iterrows():
        tier = "unknown"
        reason = ""
        
        if row['total_trades'] < 10:
            tier = "repair_candidate"
            reason = "False-fail suppression: Insufficient trade sample size (<10)."
        elif row['net_return'] < 0:
            tier = "repair_candidate"
            reason = "Negative net return (Cost burden or bad logic)."
        elif row['net_return'] > 0 and row['win_rate'] >= 50 and row['total_trades'] > 100:
            tier = "validated"
            reason = "Strong positive expectancy with adequate sample and win rate."
        else:
            tier = "research_candidate"
            reason = "Positive edge but sub-50% win rate or marginal net return."
            
        tier_results.append({
            'symbol': row['symbol'],
            'strategy': row['strategy'],
            'tier': tier,
            'reason': reason
        })
        
    res_df = pd.DataFrame(tier_results)
    print("\n================ VALIDATOR TIERING ===================")
    print(res_df.to_string(index=False))
    print("======================================================\n")

if __name__ == "__main__":
    validate_results("historical_data/benchmark_results.csv")
