import pandas as pd
from typing import List, Dict, Optional

def compute_microstructure_features(bids: List[List[float]], asks: List[List[float]], recent_trades: pd.DataFrame) -> Dict[str, Optional[float]]:
    """
    Compute microstructure features from order book and trades.
    bids/asks format: [[price, quantity], ...]
    Returns a dictionary of features.
    """
    features = {
        "bid_ask_spread_abs": None,
        "bid_ask_spread_rel": None,
        "order_book_imbalance": None,
        "trade_flow_imbalance": None,
        "large_trade_flag": None,
        "tick_direction": None,
        "price_impact_estimate": None
    }
    
    try:
        best_bid = float(bids[0][0]) if bids and len(bids) > 0 else None
        best_ask = float(asks[0][0]) if asks and len(asks) > 0 else None
        
        if best_bid is not None and best_ask is not None:
            features["bid_ask_spread_abs"] = best_ask - best_bid
            mid_price = (best_bid + best_ask) / 2
            if mid_price > 0:
                features["bid_ask_spread_rel"] = features["bid_ask_spread_abs"] / mid_price
                
        # Order Book Imbalance (Top 5 levels)
        bid_qty_top5 = sum(float(b[1]) for b in bids[:5]) if bids else 0
        ask_qty_top5 = sum(float(a[1]) for a in asks[:5]) if asks else 0
        
        if bid_qty_top5 + ask_qty_top5 > 0:
            features["order_book_imbalance"] = (bid_qty_top5 - ask_qty_top5) / (bid_qty_top5 + ask_qty_top5)
            
        if features["bid_ask_spread_abs"] is not None and features["order_book_imbalance"] is not None:
            features["price_impact_estimate"] = (features["bid_ask_spread_abs"] / 2) * features["order_book_imbalance"]
            
        # Trades related features
        if recent_trades is not None and not recent_trades.empty:
            # Assuming recent_trades has columns: 'timestamp', 'price', 'size', 'side'
            
            # Trade Flow Imbalance (assuming last 1 minute is given in recent_trades)
            buy_vol = recent_trades[recent_trades['side'] == 'buy']['size'].sum() if 'side' in recent_trades.columns else 0
            sell_vol = recent_trades[recent_trades['side'] == 'sell']['size'].sum() if 'side' in recent_trades.columns else 0
            
            if buy_vol + sell_vol > 0:
                features["trade_flow_imbalance"] = (buy_vol - sell_vol) / (buy_vol + sell_vol)
            else:
                features["trade_flow_imbalance"] = 0.0
                
            # Large Trade Flag
            if len(recent_trades) >= 60:
                avg_size_60 = recent_trades['size'].tail(60).mean()
                current_trade_size = recent_trades['size'].iloc[-1]
                features["large_trade_flag"] = 1.0 if current_trade_size > 2 * avg_size_60 else 0.0
            else:
                features["large_trade_flag"] = 0.0
                
            # Tick Direction
            if len(recent_trades) >= 2:
                last_price = recent_trades['price'].iloc[-1]
                prev_price = recent_trades['price'].iloc[-2]
                if last_price > prev_price:
                    features["tick_direction"] = 1.0
                elif last_price < prev_price:
                    features["tick_direction"] = -1.0
                else:
                    features["tick_direction"] = 0.0
            else:
                features["tick_direction"] = 0.0
                
    except Exception:
        # Gracefully handle any issues
        pass
        
    return features
