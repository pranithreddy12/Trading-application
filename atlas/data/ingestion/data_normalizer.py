from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class MarketDataL1(BaseModel):
    symbol: str
    source: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    asset_class: str = "crypto"


class MarketDataL2(BaseModel):
    symbol: str
    source: str
    timestamp: int
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float


class OrderFlow(BaseModel):
    symbol: str
    source: str
    timestamp: int
    price: float
    size: float
    conditions: Optional[list] = None


def _infer_asset_class(source: str, symbol: str) -> str:
    """Infer asset class from source and symbol."""
    if source == "binance":
        return "crypto"
    if source == "polygon":
        crypto_indicators = ["/USD", "/USDT", "USD/"]
        if any(ind in symbol.upper() for ind in crypto_indicators):
            return "crypto"
        return "equity"
    return "crypto"


def _round_ohlcv(
    open_: float, high: float, low: float, close: float, volume: float, asset_class: str
) -> tuple:
    return (
        round(float(open_), 4),
        round(float(high), 4),
        round(float(low), 4),
        round(float(close), 4),
        round(float(volume), 6 if asset_class == "crypto" else 4),
    )


def _round_orderbook(
    bid_price: float, ask_price: float, bid_size: float, ask_size: float
) -> tuple:
    return (
        round(float(bid_price), 6),
        round(float(ask_price), 6),
        round(float(bid_size), 4),
        round(float(ask_size), 4),
    )


def _round_trade(price: float, size: float) -> tuple:
    return (
        round(float(price), 6),
        round(float(size), 4),
    )


def normalize_bar(raw: Dict[str, Any], source: str) -> MarketDataL1:
    if source == "polygon":
        symbol = raw.get("sym", raw.get("symbol", ""))
        asset_class = _infer_asset_class(source, symbol)
        o, h, l, c, v = _round_ohlcv(
            raw.get("o", raw.get("open", 0)),
            raw.get("h", raw.get("high", 0)),
            raw.get("l", raw.get("low", 0)),
            raw.get("c", raw.get("close", 0)),
            raw.get("v", raw.get("volume", 0)),
            asset_class,
        )
        return MarketDataL1(
            symbol=symbol,
            source=source,
            timestamp=raw.get("e", raw.get("end_timestamp", 0)),
            open=o,
            high=h,
            low=l,
            close=c,
            volume=v,
            asset_class=asset_class,
        )
    elif source == "binance":
        k = raw.get("k", {})
        o, h, l, c, v = _round_ohlcv(
            k.get("o", 0),
            k.get("h", 0),
            k.get("l", 0),
            k.get("c", 0),
            k.get("v", 0),
            "crypto",
        )
        return MarketDataL1(
            symbol=raw.get("s", ""),
            source=source,
            timestamp=k.get("t", 0),
            open=o,
            high=h,
            low=l,
            close=c,
            volume=v,
            asset_class="crypto",
        )
    raise ValueError(f"Unknown source: {source}")


def normalize_orderbook(raw: Dict[str, Any], source: str) -> MarketDataL2:
    if source == "polygon":
        bp, ap, bs, ask_sz = _round_orderbook(
            raw.get("bp", raw.get("bid_price", 0)),
            raw.get("ap", raw.get("ask_price", 0)),
            raw.get("bs", raw.get("bid_size", 0)),
            raw.get("as", raw.get("ask_size", 0)),
        )
        return MarketDataL2(
            symbol=raw.get("sym", raw.get("symbol", "")),
            source=source,
            timestamp=raw.get("t", raw.get("timestamp", 0)),
            bid_price=bp,
            bid_size=bs,
            ask_price=ap,
            ask_size=ask_sz,
        )
    elif source == "binance":
        bids = raw.get("b", [["0", "0"]])
        asks = raw.get("a", [["0", "0"]])
        best_bid = bids[0] if bids else ["0", "0"]
        best_ask = asks[0] if asks else ["0", "0"]
        bp, ap, bs, ask_sz = _round_orderbook(
            float(best_bid[0]),
            float(best_ask[0]),
            float(best_bid[1]),
            float(best_ask[1]),
        )
        return MarketDataL2(
            symbol=raw.get("s", ""),
            source=source,
            timestamp=raw.get("E", 0),
            bid_price=bp,
            bid_size=bs,
            ask_price=ap,
            ask_size=ask_sz,
        )
    raise ValueError(f"Unknown source: {source}")


def normalize_trade(raw: Dict[str, Any], source: str) -> OrderFlow:
    if source == "polygon":
        price, size = _round_trade(
            raw.get("p", raw.get("price", 0)),
            raw.get("s", raw.get("size", 0)),
        )
        return OrderFlow(
            symbol=raw.get("sym", raw.get("symbol", "")),
            source=source,
            timestamp=raw.get("t", raw.get("timestamp", 0)),
            price=price,
            size=size,
            conditions=raw.get("c", raw.get("conditions", [])),
        )
    elif source == "binance":
        price, size = _round_trade(
            raw.get("p", 0),
            raw.get("q", 0),
        )
        return OrderFlow(
            symbol=raw.get("s", ""),
            source=source,
            timestamp=raw.get("E", 0),
            price=price,
            size=size,
            conditions=[],
        )
    raise ValueError(f"Unknown source: {source}")
