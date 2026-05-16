import pandas as pd
import numpy as np
from typing import Dict, Optional
import ta


def compute_technical_features(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """
    Compute technical features from an OHLCV DataFrame using the 'ta' library.
    Requires columns: open, high, low, close, volume.
    Returns a dictionary of features for the latest bar. Returns None for features
    if minimum bars are not available, never raises.
    """
    features = {}

    if df is None or len(df) == 0:
        return features

    # Helper function to get the last valid value safely
    def get_last(series) -> Optional[float]:
        try:
            val = series.iloc[-1]
            if pd.isna(val) or np.isinf(val):
                return None
            return round(float(val), 6)
        except Exception:
            return None

    try:
        # RSI
        features["rsi_7"] = get_last(ta.momentum.rsi(df["close"], window=7))
        features["rsi_14"] = get_last(ta.momentum.rsi(df["close"], window=14))
        features["rsi_21"] = get_last(ta.momentum.rsi(df["close"], window=21))

        # MACD
        macd = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        features["macd_line"] = get_last(macd.macd())
        features["macd_signal"] = get_last(macd.macd_signal())
        features["macd_hist"] = get_last(macd.macd_diff())

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        features["bb_upper"] = get_last(bb.bollinger_hband())
        features["bb_lower"] = get_last(bb.bollinger_lband())
        features["bb_mid"] = get_last(bb.bollinger_mavg())
        features["bb_pb"] = get_last(bb.bollinger_pband())
        features["bb_bandwidth"] = get_last(bb.bollinger_wband())

        # ATR
        features["atr_7"] = get_last(
            ta.volatility.average_true_range(
                df["high"], df["low"], df["close"], window=7
            )
        )
        features["atr_14"] = get_last(
            ta.volatility.average_true_range(
                df["high"], df["low"], df["close"], window=14
            )
        )

        # VWAP
        vwap = ta.volume.VolumeWeightedAveragePrice(
            df["high"], df["low"], df["close"], df["volume"]
        )
        features["vwap"] = get_last(vwap.vwap)
        # Calculate VWAP deviation (price vs vwap)
        last_close = get_last(df["close"])
        if (
            features["vwap"] is not None
            and last_close is not None
            and features["vwap"] != 0
        ):
            features["vwap_deviation"] = (last_close - features["vwap"]) / features[
                "vwap"
            ]
        else:
            features["vwap_deviation"] = None

        # EMA
        features["ema_9"] = get_last(ta.trend.ema_indicator(df["close"], window=9))
        features["ema_21"] = get_last(ta.trend.ema_indicator(df["close"], window=21))
        features["ema_50"] = get_last(ta.trend.ema_indicator(df["close"], window=50))
        features["ema_200"] = get_last(ta.trend.ema_indicator(df["close"], window=200))

        # SMA
        features["sma_20"] = get_last(ta.trend.sma_indicator(df["close"], window=20))
        features["sma_50"] = get_last(ta.trend.sma_indicator(df["close"], window=50))

        # Stochastic
        stoch = ta.momentum.StochasticOscillator(
            df["high"], df["low"], df["close"], window=14, smooth_window=3
        )
        features["stoch_k"] = get_last(stoch.stoch())
        features["stoch_d"] = get_last(stoch.stoch_signal())

        # Williams %R
        features["williams_r"] = get_last(
            ta.momentum.williams_r(df["high"], df["low"], df["close"], lbp=14)
        )

        # CCI
        features["cci_20"] = get_last(
            ta.trend.cci(df["high"], df["low"], df["close"], window=20)
        )

        # ADX
        adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
        features["adx_14"] = get_last(adx.adx())
        features["plus_di"] = get_last(adx.adx_pos())
        features["minus_di"] = get_last(adx.adx_neg())

        # OBV
        obv = ta.volume.OnBalanceVolumeIndicator(
            df["close"], df["volume"]
        ).on_balance_volume()
        features["obv"] = get_last(obv)
        # OBV 10-bar slope (simple change or regression)
        try:
            if len(obv) >= 10:
                features["obv_10_slope"] = get_last(obv) - float(obv.iloc[-10])
            else:
                features["obv_10_slope"] = None
        except Exception:
            features["obv_10_slope"] = None

        # Volume ratio (current vs 20-bar avg)
        try:
            vol_avg_20 = df["volume"].rolling(window=20).mean()
            features["volume_ratio_20"] = get_last(df["volume"] / vol_avg_20)
        except Exception:
            features["volume_ratio_20"] = None

        # ROC
        features["roc_10"] = get_last(ta.momentum.roc(df["close"], window=10))
        features["roc_20"] = get_last(ta.momentum.roc(df["close"], window=20))

        # Keltner Channel
        kc = ta.volatility.KeltnerChannel(
            df["high"], df["low"], df["close"], window=20, window_atr=20
        )
        features["kc_upper"] = get_last(kc.keltner_channel_hband())
        features["kc_lower"] = get_last(kc.keltner_channel_lband())
        features["kc_mid"] = get_last(kc.keltner_channel_mband())

        # Donchian Channel
        dc = ta.volatility.DonchianChannel(
            df["high"], df["low"], df["close"], window=20
        )
        features["dc_upper"] = get_last(dc.donchian_channel_hband())
        features["dc_lower"] = get_last(dc.donchian_channel_lband())
        features["dc_mid"] = get_last(dc.donchian_channel_mband())

        # Parabolic SAR
        psar = ta.trend.PSARIndicator(df["high"], df["low"], df["close"])
        features["psar"] = get_last(psar.psar())

    except Exception:
        # Failsafe in case the dataframe is too small to calculate indicators
        # Or missing columns, we return what we have (with None values)
        pass

    # =========================================================
    # STRATEGY-COMPATIBLE ALIASES
    # Feature names expected by strategy_normalizer / ideator
    # The ta library uses different internal names — fix that here.
    # =========================================================
    try:
        # ema_12 / ema_26 / sma_5 — required by EMA crossover strategies
        features["ema_12"] = get_last(ta.trend.ema_indicator(df["close"], window=12))
        features["ema_26"] = get_last(ta.trend.ema_indicator(df["close"], window=26))
        features["sma_5"] = get_last(ta.trend.sma_indicator(df["close"], window=5))

        # bollinger_upper/lower — aliases for bb_upper/bb_lower
        features["bollinger_upper"] = features.get("bb_upper")
        features["bollinger_lower"] = features.get("bb_lower")

        # macd — alias for macd_line
        features["macd"] = features.get("macd_line")

        # returns / log_returns
        if len(df) >= 2:
            ret = df["close"].pct_change().fillna(0)
            features["returns"] = get_last(ret)
            with np.errstate(divide="ignore", invalid="ignore"):
                log_ret = np.where(
                    df["close"].shift(1) > 0,
                    np.log(df["close"] / df["close"].shift(1)),
                    0.0,
                )
            features["log_returns"] = round(float(log_ret[-1]), 8)
        else:
            features["returns"] = None
            features["log_returns"] = None

        # rolling_volatility — 20-bar std of returns
        features["rolling_volatility"] = get_last(
            df["close"].pct_change().rolling(window=20).std()
        )

    except Exception as e:
        pass  # keep what we have

    # =========================================================
    # NEW NORMALIZED CROSS-ASSET FEATURES
    # These are scale-free and work for both equity + crypto
    # =========================================================
    try:
        lc = get_last(df["close"])

        # 1. price_vs_vwap_pct: % deviation of price from VWAP
        _vwap = features.get("vwap")
        if _vwap and _vwap != 0 and lc is not None:
            features["price_vs_vwap_pct"] = round((lc - _vwap) / _vwap, 8)
        else:
            features["price_vs_vwap_pct"] = None

        # 2. ema_spread_pct: EMA12 vs EMA26 divergence as % of EMA26
        _e12 = features.get("ema_12")
        _e26 = features.get("ema_26")
        if _e12 is not None and _e26 is not None and _e26 != 0:
            features["ema_spread_pct"] = round((_e12 - _e26) / _e26, 8)
        else:
            features["ema_spread_pct"] = None

        # 3. relative_volume: current bar volume vs 20-bar mean
        try:
            _vol_mean = df["volume"].rolling(window=20).mean().iloc[-1]
            _vol_last = float(df["volume"].iloc[-1])
            if _vol_mean and _vol_mean > 0 and not np.isnan(_vol_mean):
                features["relative_volume"] = round(_vol_last / float(_vol_mean), 6)
            else:
                features["relative_volume"] = None
        except Exception:
            features["relative_volume"] = None

        # 4. bollinger_band_position: where is close inside the band (0=lower, 1=upper)
        _bu = features.get("bollinger_upper")
        _bl = features.get("bollinger_lower")
        if _bu is not None and _bl is not None and (_bu - _bl) != 0 and lc is not None:
            features["bollinger_band_position"] = round((lc - _bl) / (_bu - _bl), 6)
        else:
            features["bollinger_band_position"] = None

        # 5. volatility_regime: rolling_volatility vs its 20-bar mean (>1 = expanding)
        try:
            _rv = df["close"].pct_change().rolling(window=20).std()
            _rv_mean = _rv.rolling(window=20).mean()
            _rv_last = _rv.iloc[-1]
            _rv_mean_last = _rv_mean.iloc[-1]
            if (
                _rv_mean_last
                and _rv_mean_last > 0
                and not np.isnan(_rv_last)
                and not np.isnan(_rv_mean_last)
            ):
                features["volatility_regime"] = round(
                    float(_rv_last) / float(_rv_mean_last), 6
                )
            else:
                features["volatility_regime"] = None
        except Exception:
            features["volatility_regime"] = None

        # 6. trend_strength: normalised EMA divergence relative to price
        if _e12 is not None and _e26 is not None and lc is not None and lc != 0:
            features["trend_strength"] = round(abs(_e12 - _e26) / lc, 8)
        else:
            features["trend_strength"] = None

    except Exception:
        pass  # keep existing features intact

    # Ensure all defined features are in the dictionary, set to None if missing
    expected_features = [
        "rsi_7", "rsi_14", "rsi_21",
        "macd_line", "macd_signal", "macd_hist", "macd",
        "bb_upper", "bb_lower", "bb_mid", "bb_pb", "bb_bandwidth",
        "bollinger_upper", "bollinger_lower",
        "atr_7", "atr_14",
        "vwap", "vwap_deviation",
        "ema_9", "ema_12", "ema_21", "ema_26", "ema_50", "ema_200",
        "sma_5", "sma_20", "sma_50",
        "stoch_k", "stoch_d",
        "williams_r", "cci_20",
        "adx_14", "plus_di", "minus_di",
        "obv", "obv_10_slope",
        "volume_ratio_20",
        "roc_10", "roc_20",
        "kc_upper", "kc_lower", "kc_mid",
        "dc_upper", "dc_lower", "dc_mid",
        "psar",
        "returns", "log_returns", "rolling_volatility",
        # New normalized features
        "price_vs_vwap_pct", "ema_spread_pct", "relative_volume",
        "bollinger_band_position", "volatility_regime", "trend_strength",
    ]
    for feat in expected_features:
        if feat not in features:
            features[feat] = None

    return features

