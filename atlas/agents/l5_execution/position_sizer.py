"""
position_sizer.py — Risk-Normalized Position Sizing

Every trade risks the same dollar amount regardless of asset price.
This ensures BTC and SOL positions are equally sized by *risk*, not notional.

Formula: qty = risk_usd / (price × stop_pct)
  BTC at $60,000, stop=5%: qty = 100 / (60000 × 0.05) = 0.033
  SOL at $60,    stop=5%: qty = 100 / (60   × 0.05) = 33.3
  NVDA at $900,  stop=5%: qty = 100 / (900  × 0.05) = 2.2 → 2 shares
"""

from loguru import logger


class PositionSizer:
    """
    Risk-normalized position sizing.

    Every trade risks the same dollar amount regardless of asset price.
    Prevents situations where one large-notional trade (e.g. 5 BTC)
    overwhelms hundreds of small-notional trades (e.g. SOL).
    """

    # Risk limits — tune these for the portfolio
    PORTFOLIO_VALUE: float = 100_000.0  # $100k paper portfolio
    RISK_PER_TRADE_USD: float = 100.0  # Risk $100 per trade
    MAX_NOTIONAL_PER_POS: float = 5_000.0  # Never exceed $5k notional per position
    MAX_NOTIONAL_PER_SYM: float = 10_000.0  # Never exceed $10k total per symbol
    STOP_LOSS_PCT: float = 0.05  # 5% stop loss (aligned with MTM engine exit threshold)

    # Precision by asset type
    CRYPTO_PRECISION: int = 3  # e.g. 0.083 BTC
    EQUITY_PRECISION: int = 0  # whole shares only

    # Crypto quote currency suffixes
    _CRYPTO_SUFFIXES: tuple = ("USDT", "USDC", "BTC", "ETH", "BNB", "BUSD", "FDUSD")

    def _is_crypto(self, symbol: str) -> bool:
        """Return True if symbol is a crypto pair."""
        return any(symbol.upper().endswith(s) for s in self._CRYPTO_SUFFIXES)

    def calculate_qty(
        self,
        symbol: str,
        price: float,
        stop_loss_pct: float | None = None,
    ) -> float:
        """
        Calculate position size using fixed fractional risk.

        Args:
            symbol:        The ticker/pair (e.g. 'BTCUSDT', 'AAPL').
            price:         Current market price in USD.
            stop_loss_pct: Fraction of price as stop distance (default 2%).

        Returns:
            Quantity to trade, properly rounded for asset class.
        """
        if price <= 0:
            logger.warning(
                f"PositionSizer: invalid price {price} for {symbol}, returning 0"
            )
            return 0.0

        stop = stop_loss_pct if stop_loss_pct is not None else self.STOP_LOSS_PCT
        # Enforce a minimum stop to avoid astronomically large quantities
        stop = max(stop, 0.005)  # minimum 0.5%

        # Core formula: risk_usd / (price × stop_fraction)
        qty = self.RISK_PER_TRADE_USD / (price * stop)

        # Apply notional cap
        notional = qty * price
        if notional > self.MAX_NOTIONAL_PER_POS:
            qty = self.MAX_NOTIONAL_PER_POS / price

        # Apply precision and minimum size rules
        if self._is_crypto(symbol):
            qty = round(qty, self.CRYPTO_PRECISION)
            # Enforce minimum notional ($10 for crypto)
            if qty * price < 10.0:
                qty = round(10.0 / price, self.CRYPTO_PRECISION)
        else:
            # Equities: whole shares only.
            # Reject if 1 share violates the risk budget.
            if qty < 1.0:
                logger.warning(
                    f"PositionSizer: 1 share of {symbol} at ${price} with {stop:.1%} stop "
                    f"risks ${price * stop:,.2f}, exceeding ${self.RISK_PER_TRADE_USD} limit. "
                    f"Rejecting trade."
                )
                return 0.0
            qty = float(int(qty))

        logger.debug(
            f"PositionSizer: {symbol} price=${price:,.2f} stop={stop:.1%} "
            f"→ qty={qty} notional=${qty * price:,.0f}"
        )
        return float(qty)

    def validate_notional(
        self,
        symbol: str,
        qty: float,
        price: float,
        existing_notional: float = 0.0,
    ) -> tuple[bool, str]:
        """
        Check if adding this position would breach symbol exposure limits.

        Args:
            symbol:             The ticker/pair.
            qty:                Quantity to add.
            price:              Current market price.
            existing_notional:  Current dollar exposure already held for this symbol.

        Returns:
            (approved: bool, reason: str)
        """
        new_notional = qty * price
        total_notional = existing_notional + new_notional

        if new_notional > self.MAX_NOTIONAL_PER_POS:
            reason = (
                f"Position notional ${new_notional:,.0f} "
                f"exceeds MAX_NOTIONAL_PER_POS "
                f"${self.MAX_NOTIONAL_PER_POS:,.0f}"
            )
            logger.warning(
                f"PositionSizer.validate_notional rejected {symbol}: {reason}"
            )
            return False, reason

        if total_notional > self.MAX_NOTIONAL_PER_SYM:
            reason = (
                f"Symbol {symbol} total exposure ${total_notional:,.0f} "
                f"would exceed MAX_NOTIONAL_PER_SYM "
                f"${self.MAX_NOTIONAL_PER_SYM:,.0f}"
            )
            logger.warning(
                f"PositionSizer.validate_notional rejected {symbol}: {reason}"
            )
            return False, reason

        return True, "approved"
