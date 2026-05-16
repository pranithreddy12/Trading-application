import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from atlas.data.features.technical import compute_technical_features
from atlas.data.features.microstructure import compute_microstructure_features
from atlas.data.features.regime import compute_regime_features

@pytest.fixture
def sample_df_200():
    np.random.seed(42)
    dates = pd.date_range("2026-05-01", periods=200, freq="1min")
    df = pd.DataFrame({
        "time": dates,
        "open": np.random.uniform(100, 110, 200),
        "high": np.random.uniform(105, 115, 200),
        "low": np.random.uniform(95, 105, 200),
        "close": np.random.uniform(100, 110, 200),
        "volume": np.random.uniform(1000, 5000, 200)
    })
    return df

@pytest.fixture
def sample_df_5():
    np.random.seed(42)
    dates = pd.date_range("2026-05-01", periods=5, freq="1min")
    df = pd.DataFrame({
        "time": dates,
        "open": np.random.uniform(100, 110, 5),
        "high": np.random.uniform(105, 115, 5),
        "low": np.random.uniform(95, 105, 5),
        "close": np.random.uniform(100, 110, 5),
        "volume": np.random.uniform(1000, 5000, 5)
    })
    return df

def test_technical_features_200_rows(sample_df_200):
    features = compute_technical_features(sample_df_200)
    assert isinstance(features, dict)
    
    # Check that at least some are float (not None) since we have 200 rows
    assert features["rsi_14"] is not None
    assert isinstance(features["rsi_14"], float)
    
    # Check no feature raises exception
    for k, v in features.items():
        assert v is None or isinstance(v, float)

def test_technical_features_5_rows(sample_df_5):
    features = compute_technical_features(sample_df_5)
    assert isinstance(features, dict)
    
    # RSI 14 should be None because we only have 5 rows
    assert features["rsi_14"] is None
    
    # Should not crash, and return mostly None
    for k, v in features.items():
        assert v is None or isinstance(v, float)

def test_regime_detection_trending():
    tech_features = {
        "adx_14": 30.0, # > 25 means trending
        "atr_14": 1.5,
        "volume_ratio_20": 1.5
    }
    regimes = compute_regime_features(tech_features, current_time=datetime(2026, 5, 12, 14, 30))
    
    assert regimes["trend_regime"] == "trending"
    assert regimes["volume_regime"] == "high"
    assert regimes["market_session"] == "regular" # 10:30 AM EDT is regular

def test_microstructure_features():
    bids = [[100.0, 10], [99.9, 15], [99.8, 20]]
    asks = [[100.1, 5], [100.2, 10], [100.3, 15]]
    
    recent_trades = pd.DataFrame([
        {"timestamp": 1, "price": 100.0, "size": 5, "side": "buy"},
        {"timestamp": 2, "price": 100.1, "size": 10, "side": "buy"},
        {"timestamp": 3, "price": 100.0, "size": 5, "side": "sell"}
    ])
    
    features = compute_microstructure_features(bids, asks, recent_trades)
    
    assert features["bid_ask_spread_abs"] == pytest.approx(0.1)
    assert features["bid_ask_spread_rel"] > 0
    assert features["order_book_imbalance"] > 0 # (45 - 30) / 75
    assert features["trade_flow_imbalance"] == pytest.approx((15 - 5) / 20) # 10 / 20 = 0.5
