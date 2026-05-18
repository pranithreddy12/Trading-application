import requests
import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# =========================
# CONFIG
# =========================
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
EQUITY_SYMBOLS = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT"]

CRYPTO_INTERVAL = "1h"
CRYPTO_LIMIT = 1000
BINANCE_URL = "https://api.binance.com/api/v3/klines"

BASE_DIR = Path("historical_data")
CRYPTO_DIR = BASE_DIR / "crypto"
EQUITY_DIR = BASE_DIR / "equities"

CRYPTO_DIR.mkdir(parents=True, exist_ok=True)
EQUITY_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# CRYPTO FETCHER
# =========================
def fetch_crypto_symbol(symbol):
    print(f"\n=== Fetching Crypto: {symbol} ===")

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=365)

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    all_data = []

    while start_ms < end_ms:
        params = {
            "symbol": symbol,
            "interval": CRYPTO_INTERVAL,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": CRYPTO_LIMIT
        }

        response = requests.get(BINANCE_URL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if not data:
            break

        all_data.extend(data)

        last_open_time = data[-1][0]
        start_ms = last_open_time + 1

        print(f"{symbol}: {len(all_data)} candles fetched")

        time.sleep(0.25)

    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ]

    df = pd.DataFrame(all_data, columns=columns)

    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["symbol"] = symbol
    df["asset_class"] = "crypto"
    df["source"] = "binance"

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[[
        "timestamp", "symbol", "asset_class", "source",
        "open", "high", "low", "close", "volume"
    ]]

    df = df.drop_duplicates(subset=["timestamp"]).dropna()

    filepath = CRYPTO_DIR / f"{symbol.lower()}_1h_1y.csv"
    df.to_csv(filepath, index=False)

    print(f"{symbol}: Saved {len(df)} rows -> {filepath}")

    return df


# =========================
# EQUITY FETCHER
# =========================
def fetch_equity_symbol(symbol):
    print(f"\n=== Fetching Equity: {symbol} ===")

    df = yf.download(
        symbol,
        period="1y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="column"
    )

    if df.empty:
        print(f"{symbol}: FAILED (No data)")
        return pd.DataFrame()

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    # Reset index
    df = df.reset_index()

    # Detect date column
    date_col = None
    for candidate in ["Date", "Datetime", "index"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        raise ValueError(f"{symbol}: Could not find date column. Columns: {list(df.columns)}")

    # Validate OHLCV existence
    required_source_cols = ["Open", "High", "Low", "Close", "Volume"]

    missing_source = [c for c in required_source_cols if c not in df.columns]

    if missing_source:
        raise ValueError(f"{symbol}: Missing source columns -> {missing_source}. Available: {list(df.columns)}")

    # Build normalized schema
    df["timestamp"] = pd.to_datetime(df[date_col], utc=True)
    df["symbol"] = symbol
    df["asset_class"] = "equity"
    df["source"] = "yfinance"

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })

    df = df[
        [
            "timestamp",
            "symbol",
            "asset_class",
            "source",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]
    ]

    # Numeric normalization
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Cleanup
    df = df.drop_duplicates(subset=["timestamp"]).dropna()

    filepath = EQUITY_DIR / f"{symbol.lower()}_1d_1y.csv"
    df.to_csv(filepath, index=False)

    print(f"{symbol}: Saved {len(df)} rows -> {filepath}")

    return df
# =========================
# VALIDATION
# =========================
def validate_dataset(df, symbol):
    if df.empty:
        print(f"{symbol}: EMPTY DATASET")
        return

    duplicates = df["timestamp"].duplicated().sum()
    nulls = df.isnull().sum().sum()

    print(f"\nValidation: {symbol}")
    print(f"Rows: {len(df)}")
    print(f"Duplicates: {duplicates}")
    print(f"Nulls: {nulls}")
    print(f"Start: {df['timestamp'].min()}")
    print(f"End: {df['timestamp'].max()}")


# =========================
# MAIN
# =========================
def main():
    all_crypto = []
    all_equities = []

    # Crypto
    for symbol in CRYPTO_SYMBOLS:
        try:
            df = fetch_crypto_symbol(symbol)
            validate_dataset(df, symbol)
            all_crypto.append(df)
        except Exception as e:
            print(f"{symbol}: FAILED -> {e}")

    # Equities
    for symbol in EQUITY_SYMBOLS:
        try:
            df = fetch_equity_symbol(symbol)
            validate_dataset(df, symbol)
            all_equities.append(df)
        except Exception as e:
            print(f"{symbol}: FAILED -> {e}")

    # Merge Crypto
    if all_crypto:
        crypto_master = pd.concat(all_crypto, ignore_index=True)
        crypto_master.to_csv(BASE_DIR / "all_crypto_master.csv", index=False)
        print(f"\nSaved crypto master: {len(crypto_master)} rows")

    # Merge Equities
    if all_equities:
        equity_master = pd.concat(all_equities, ignore_index=True)
        equity_master.to_csv(BASE_DIR / "all_equities_master.csv", index=False)
        print(f"Saved equity master: {len(equity_master)} rows")

    # Unified
    combined = []

    if all_crypto:
        combined.append(crypto_master)

    if all_equities:
        combined.append(equity_master)

    if combined:
        full_master = pd.concat(combined, ignore_index=True)
        full_master.to_csv(BASE_DIR / "atlas_historical_universe.csv", index=False)

        print(f"\n=== FULL ATLAS UNIVERSE COMPLETE ===")
        print(f"Total Rows: {len(full_master)}")
        print(f"Symbols: {full_master['symbol'].nunique()}")
        print(full_master.groupby(['asset_class', 'symbol']).size())


if __name__ == "__main__":
    main()