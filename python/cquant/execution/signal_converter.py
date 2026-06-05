"""cquant.execution.signal_converter — Convert strategy signals to Order objects.

Transforms a SignalFrame (from Strategy.generate_signals) into broker-ready
Order objects, applying position sizing and risk constraints.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import polars as pl

from cquant.core.types import SignalFrame
from cquant.execution.broker import Order

logger = logging.getLogger(__name__)

# Minimum lot size for CN market (100 shares per lot)
_CN_LOT_SIZE = 100


class SignalConverter:
    """Converts strategy signals into Order objects.

    Handles:
    - Signal filtering (strength > threshold)
    - Position sizing (equal weight, risk parity, etc.)
    - Lot size rounding (CN: 100-share lots)
    - Buy/sell determination based on current positions

    Usage::

        converter = SignalConverter(lot_size=100)
        orders = converter.convert(signals, current_positions, nav, prices)
    """

    def __init__(
        self,
        lot_size: int = _CN_LOT_SIZE,
        min_strength: float = 0.01,
        max_position_pct: float = 0.10,
    ) -> None:
        self._lot_size = lot_size
        self._min_strength = min_strength
        self._max_position_pct = max_position_pct

    def convert(
        self,
        signals: SignalFrame,
        current_positions: dict[str, int],
        nav: float,
        prices: dict[str, float],
    ) -> list[Order]:
        """Convert signals to Order list.

        Parameters
        ----------
        signals:
            SignalFrame with columns: asset_id, signal_date, direction, strength, confidence.
        current_positions:
            Current holdings {asset_id: qty}.
        nav:
            Current portfolio NAV.
        prices:
            Current prices {asset_id: price}.

        Returns
        -------
        List of Order objects (buy orders for new positions, sell orders for exits).
        """
        if signals.is_empty():
            return []

        orders: list[Order] = []

        # Filter signals by minimum strength
        active_signals = signals.filter(pl.col("strength").abs() >= self._min_strength)

        if active_signals.is_empty():
            return []

        # Calculate target positions
        target_positions = self._compute_target_positions(active_signals, nav, prices)

        # Diff with current positions
        all_assets = set(target_positions.keys()) | set(current_positions.keys())

        for asset_id in all_assets:
            target_qty = target_positions.get(asset_id, 0)
            current_qty = current_positions.get(asset_id, 0)
            delta = target_qty - current_qty

            if abs(delta) < self._lot_size:
                continue  # Skip tiny deltas

            price = prices.get(asset_id, 0.0)
            if price <= 0:
                logger.warning("No price for %s, skipping order", asset_id)
                continue

            if delta > 0:
                # Buy
                buy_qty = self._round_to_lot(delta)
                if buy_qty > 0:
                    orders.append(self._make_order(asset_id, "buy", buy_qty))
            elif delta < 0:
                # Sell
                sell_qty = self._round_to_lot(abs(delta))
                if sell_qty > 0:
                    orders.append(self._make_order(asset_id, "sell", sell_qty))

        logger.info("Converted %d signals to %d orders", len(active_signals), len(orders))
        return orders

    def _compute_target_positions(
        self,
        signals: SignalFrame,
        nav: float,
        prices: dict[str, float],
    ) -> dict[str, int]:
        """Compute target share quantities from signals.

        Uses equal-weight sizing per signal, capped at max_position_pct.
        """
        target: dict[str, int] = {}

        # Only take long signals (direction == "buy" or strength > 0)
        long_signals = signals.filter(pl.col("strength") > 0)

        if long_signals.is_empty():
            return target

        n_signals = len(long_signals)
        if n_signals == 0:
            return target

        # Equal weight allocation
        weight_per_signal = min(1.0 / n_signals, self._max_position_pct)

        for row in long_signals.to_dicts():
            asset_id = row["asset_id"]
            price = prices.get(asset_id, 0.0)
            if price <= 0:
                continue

            allocation = nav * weight_per_signal
            raw_qty = allocation / price
            qty = self._round_to_lot(int(raw_qty))

            if qty >= self._lot_size:
                target[asset_id] = qty

        return target

    def _round_to_lot(self, qty: int) -> int:
        """Round quantity down to nearest lot size."""
        return (qty // self._lot_size) * self._lot_size

    @staticmethod
    def _make_order(asset_id: str, side: str, qty: int) -> Order:
        """Create an Order object."""
        return Order(
            order_id=str(uuid.uuid4())[:8],
            asset_id=asset_id,
            side=side,
            qty=qty,
            order_type="market",
            strategy_id="live_executor",
        )
