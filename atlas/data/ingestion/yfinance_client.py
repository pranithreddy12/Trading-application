"""
Minimal async wrapper around `yfinance` to provide 1-minute bars as a
fallback when Polygon returns delayed/no-results. This module keeps the
interface small: `fetch_1m_bars(symbol, start_dt, end_dt)` returns a list
of dicts matching the Polygon `results` shape (keys: `t`, `o`, `h`, `l`,
`c`, `v`, `vw`).

Note: `yfinance` and `pandas` are required for this to work. Install with:
  pip install yfinance pandas
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any
import asyncio

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency
    yf = None


async def fetch_1m_bars(symbol: str, start_dt: datetime, end_dt: datetime) -> List[Dict[str, Any]]:
    """
    Fetch 1-minute bars for `symbol` between `start_dt` and `end_dt`.

    Returns a list of dicts similar to Polygon `/v2/aggs` results where
    `t` is epoch milliseconds.
    """
    if yf is None:
        raise RuntimeError("yfinance is not installed. Install with `pip install yfinance pandas`")

    # yfinance is synchronous; run in thread to avoid blocking
    def _sync_fetch():
        ticker = yf.Ticker(symbol)
        # yfinance expects timezone-aware datetimes or strings
        df = ticker.history(start=start_dt, end=end_dt, interval="1m", auto_adjust=False)
        if df is None or df.empty:
            return []
        out = []
        for idx, row in df.iterrows():
            ts = int(pd_timestamp_to_epoch_ms(idx))
            out.append({
                "t": ts,
                "o": float(row.get("Open", 0)),
                "h": float(row.get("High", 0)),
                "l": float(row.get("Low", 0)),
                "c": float(row.get("Close", 0)),
                "v": float(row.get("Volume", 0)),
                "vw": None,
            })
        return out

    # Helper to convert pandas Timestamp to epoch ms without importing pandas at module import time
    def pd_timestamp_to_epoch_ms(ts):
        try:
            # pandas Timestamp has tz_localize info; convert to UTC then to epoch
            return int(ts.tz_convert("UTC").timestamp() * 1000)
        except Exception:
            return int(ts.timestamp() * 1000)

    return await asyncio.to_thread(_sync_fetch)
