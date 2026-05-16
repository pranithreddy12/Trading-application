"""
atlas/scripts/seed_equity_data.py
──────────────────────────────────────────────────────────────────────────────
Seed historical 1-minute OHLCV bars for equity symbols into market_data_l1.

Strategy
────────
1.  yfinance  (primary)  — free, no auth, last 7 days of 1m data.
2.  Polygon REST aggs    (fallback) — uses POLYGON_API_KEY; free tier rate-
    limited to 5 calls/min, so we sleep 13 s between symbols.
3.  Polygon /prev close  (last-resort) — single daily bar if aggs 403.

Run
────
    python atlas/scripts/seed_equity_data.py

NOTE: yfinance path takes ~30 s for 10 symbols.
      Polygon fallback path takes ~2 min due to rate limits.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp
import yfinance as yf
from loguru import logger
from sqlalchemy import text

from atlas.config.settings import settings
from atlas.data.storage.timescale_client import TimescaleClient, _r4

# ── Symbols ─────────────────────────────────────────────────────────────────
SYMBOLS = [
    "SPY",
    "QQQ",
    "AAPL",
    "TSLA",
    "NVDA",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
    "AMD",
]

# ── yfinance helpers ─────────────────────────────────────────────────────────


def fetch_yfinance_bars(symbol: str, days_back: int = 7) -> list[dict]:
    """
    Pull 1-minute bars from yfinance (last 7 days, no auth required).
    Returns a list of Polygon-compatible bar dicts:
        {t, o, h, l, c, v}
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{days_back}d", interval="1m")
        if df is None or df.empty:
            logger.warning(f"{symbol}: yfinance returned empty DataFrame")
            return []

        bars: list[dict] = []
        for ts, row in df.iterrows():
            # yfinance timestamps are tz-aware; convert to UTC ms
            try:
                ts_utc = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
                bars.append(
                    {
                        "t": int(ts_utc.timestamp() * 1000),
                        "o": float(row["Open"]),
                        "h": float(row["High"]),
                        "l": float(row["Low"]),
                        "c": float(row["Close"]),
                        "v": float(row["Volume"]),
                    }
                )
            except Exception as row_err:
                logger.debug(f"{symbol}: skipping malformed yfinance row — {row_err}")
                continue

        logger.info(f"{symbol}: yfinance returned {len(bars)} bars (last {days_back}d)")
        return bars

    except Exception as e:
        logger.error(f"{symbol}: yfinance fetch failed — {e}")
        return []


# ── Polygon helpers ──────────────────────────────────────────────────────────


async def fetch_polygon_aggs(
    session: aiohttp.ClientSession,
    symbol: str,
    days_back: int = 5,
) -> list[dict]:
    """
    Fetch 1-minute bars from Polygon REST /v2/aggs (requires API key).
    Free tier allows up to 2 years history but rate-limits at 5 req/min.
    Returns list of raw Polygon result dicts.
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)
    from_str = start_date.strftime("%Y-%m-%d")
    to_str = end_date.strftime("%Y-%m-%d")

    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute"
        f"/{from_str}/{to_str}"
        f"?adjusted=true&sort=asc&limit=5000"
        f"&apiKey={settings.polygon_api_key}"
    )

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("results", [])
                logger.info(
                    f"{symbol}: Polygon aggs returned {len(results)} bars "
                    f"({from_str} → {to_str})"
                )
                return results

            elif resp.status == 403:
                logger.warning(
                    f"{symbol}: Polygon 403 — free-tier aggs restricted. "
                    f"Falling back to /prev endpoint."
                )
                return await fetch_polygon_prev(session, symbol)

            else:
                body = await resp.text()
                logger.error(f"{symbol}: Polygon {resp.status} — {body[:200]}")
                return []

    except Exception as e:
        logger.error(f"{symbol}: Polygon request error — {e}")
        return []


async def fetch_polygon_prev(
    session: aiohttp.ClientSession,
    symbol: str,
) -> list[dict]:
    """Last-resort: Polygon /v2/aggs/ticker/{symbol}/prev (single daily bar)."""
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev"
        f"?adjusted=true&apiKey={settings.polygon_api_key}"
    )
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("results", [])
    except Exception as e:
        logger.error(f"{symbol}: Polygon /prev error — {e}")
    return []


# ── DB insert ────────────────────────────────────────────────────────────────


async def insert_equity_bars(
    db: TimescaleClient,
    symbol: str,
    bars: list[dict],
    source: str = "yfinance",
) -> int:
    """
    Bulk-insert Polygon-format bars {t, o, h, l, c, v} into market_data_l1.
    Uses ON CONFLICT (time, symbol) DO NOTHING to be idempotent.
    """
    if not bars:
        return 0

    rows: list[dict] = []
    for bar in bars:
        try:
            rows.append(
                {
                    "time": datetime.fromtimestamp(
                        bar["t"] / 1000, tz=timezone.utc
                    ).isoformat(),
                    "symbol": symbol,
                    "open": _r4(bar.get("o", 0)),
                    "high": _r4(bar.get("h", 0)),
                    "low": _r4(bar.get("l", 0)),
                    "close": _r4(bar.get("c", 0)),
                    "volume": _r4(bar.get("v", 0)),
                    "source": source,
                    "interval": "1m",
                    "asset_class": "equity",
                }
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"{symbol}: skipping malformed bar — {e}")
            continue

    if not rows:
        return 0

    async with db.engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO market_data_l1
                    (time, symbol, open, high, low,
                     close, volume, source, interval, asset_class)
                SELECT
                    d.time::timestamptz,
                    d.symbol,
                    d.open::float8,
                    d.high::float8,
                    d.low::float8,
                    d.close::float8,
                    d.volume::float8,
                    d.source,
                    d.interval,
                    d.asset_class
                FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS d(
                    time text,   symbol text,
                    open float8, high float8, low float8,
                    close float8, volume float8,
                    source text, interval text, asset_class text
                )
                ON CONFLICT (time, symbol) DO NOTHING
            """),
            {"rows": json.dumps(rows)},
        )

    return len(rows)


# ── Main ─────────────────────────────────────────────────────────────────────


async def main() -> None:
    # ── Connect to DB ────────────────────────────────────────────────────────
    db = TimescaleClient(settings.database_url)
    await db.connect()
    logger.info("✅  TimescaleDB connected")

    # ── BEFORE state ─────────────────────────────────────────────────────────
    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT symbol, COUNT(*) AS bars
                FROM   market_data_l1
                WHERE  asset_class = 'equity'
                   OR  symbol NOT LIKE '%USDT'
                GROUP  BY symbol
                ORDER  BY bars DESC
            """)
        )
        before = result.fetchall()

    logger.info("─" * 60)
    logger.info("BEFORE — equity-related bars in market_data_l1:")
    if before:
        for r in before:
            logger.info(f"  {r.symbol:10s}: {r.bars:>6} bars")
    else:
        logger.info("  (none)")
    logger.info("─" * 60)

    # ── Fetch + insert ───────────────────────────────────────────────────────
    total_inserted = 0
    polygon_needed: list[str] = []  # symbols where yfinance returned 0

    # Pass 1: yfinance (sync — runs in thread to avoid blocking event loop)
    logger.info("📥  Pass 1 — yfinance (primary, free, last 7 days)")
    loop = asyncio.get_event_loop()

    for symbol in SYMBOLS:
        bars = await loop.run_in_executor(None, fetch_yfinance_bars, symbol)
        if bars:
            inserted = await insert_equity_bars(db, symbol, bars, source="yfinance")
            total_inserted += inserted
            logger.success(f"  ✓ {symbol}: inserted {inserted} bars  [yfinance]")
        else:
            logger.warning(
                f"  ✗ {symbol}: yfinance returned 0 bars — queued for Polygon"
            )
            polygon_needed.append(symbol)

    # Pass 2: Polygon REST for symbols that yfinance missed
    if polygon_needed:
        logger.info(
            f"📥  Pass 2 — Polygon REST fallback for {len(polygon_needed)} symbols"
        )

        resolver = aiohttp.AsyncResolver(nameservers=["8.8.8.8", "1.1.1.1"])
        connector = aiohttp.TCPConnector(resolver=resolver)

        async with aiohttp.ClientSession(connector=connector) as session:
            for symbol in polygon_needed:
                bars = await fetch_polygon_aggs(session, symbol, days_back=5)
                if bars:
                    inserted = await insert_equity_bars(
                        db, symbol, bars, source="polygon"
                    )
                    total_inserted += inserted
                    logger.success(f"  ✓ {symbol}: inserted {inserted} bars  [polygon]")
                else:
                    logger.error(f"  ✗ {symbol}: 0 bars from both yfinance and Polygon")

                # Respect Polygon free-tier: 5 req/min → 13 s between calls
                if symbol != polygon_needed[-1]:
                    logger.info("    ⏳  sleeping 13 s (Polygon rate limit)…")
                    await asyncio.sleep(13)
    else:
        logger.info(
            "✅  All symbols fetched via yfinance — Polygon fallback not needed"
        )

    # ── AFTER state ──────────────────────────────────────────────────────────
    async with db.engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT symbol,
                       COUNT(*)   AS bars,
                       MIN(time)  AS oldest,
                       MAX(time)  AS newest
                FROM   market_data_l1
                GROUP  BY symbol
                ORDER  BY bars DESC
            """)
        )
        after = result.fetchall()

    logger.info("=" * 60)
    logger.info(f"AFTER — all bars in market_data_l1  (total new: {total_inserted}):")
    for r in after:
        try:
            oldest = r.oldest.strftime("%Y-%m-%d %H:%M")
            newest = r.newest.strftime("%Y-%m-%d %H:%M")
        except Exception:
            oldest = newest = "N/A"
        logger.info(f"  {r.symbol:10s}: {r.bars:>6} bars | {oldest} → {newest}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
