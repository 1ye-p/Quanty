"""Delist position handler — forced liquidation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class ForcedLiquidationTrade:
    """A forced liquidation trade due to delisting."""

    asset_id: str
    trade_date: date
    side: str  # always "sell"
    qty: int
    price: float
    reason: str = "delist_forced_liquidation"


class DelistHandler:
    """Handles forced liquidation when a stock is delisted."""

    def handle_delist(
        self,
        positions: dict[str, int],
        asset_id: str,
        trade_date: date,
        price: float,
    ) -> list[ForcedLiquidationTrade]:
        """Generate forced sell trade for delisted stock.

        Args:
            positions: current portfolio positions {asset_id: quantity}
            asset_id: the delisted stock
            trade_date: date of delisting
            price: last available price for liquidation

        Returns:
            List of forced liquidation trades (empty if no position)
        """
        qty = positions.get(asset_id, 0)
        if qty <= 0:
            return []
        return [ForcedLiquidationTrade(
            asset_id=asset_id,
            trade_date=trade_date,
            side="sell",
            qty=qty,
            price=price,
            reason="delist_forced_liquidation",
        )]
