"""cquant.riskguard.portfolio_ledger — Realistic portfolio state tracking.

Tracks cash, positions, orders, fills, and NAV with proper accounting.
Unlike the weight-based approximation, this provides a true ledger that
can be audited and reconciled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """A single asset position."""
    asset_id: str
    qty: int
    avg_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class PortfolioState:
    """Point-in-time portfolio state."""
    trade_date: date
    cash: float
    positions: dict[str, Position]
    nav: float
    gross_exposure: float
    net_exposure: float
    realized_pnl: float
    unrealized_pnl: float


class PortfolioLedger:
    """Realistic portfolio ledger with proper accounting.

    Usage::

        ledger = PortfolioLedger(initial_cash=1_000_000)
        ledger.apply_fill(fill)
        state = ledger.mark_to_market(prices, trade_date)
    """

    def __init__(self, initial_cash: float) -> None:
        self._cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._realized_pnl = 0.0
        self._trade_date: date | None = None

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        return self._positions.copy()

    def apply_fill(self, fill: dict) -> None:
        """Apply a fill to the ledger.

        Args:
            fill: dict with keys: trade_date, asset_id, side, qty, price, notional, total_cost
        """
        asset_id = fill["asset_id"]
        side = fill["side"]
        qty = fill["qty"]
        price = fill["price"]
        notional = fill["notional"]
        total_cost = fill["total_cost"]

        if side == "buy":
            self._apply_buy(asset_id, qty, price, notional, total_cost)
        elif side == "sell":
            self._apply_sell(asset_id, qty, price, notional, total_cost)
        else:
            logger.warning("Unknown fill side: %s", side)

        self._trade_date = fill.get("trade_date", self._trade_date)

    def _apply_buy(
        self, asset_id: str, qty: int, price: float, notional: float, total_cost: float
    ) -> None:
        """Apply a buy fill."""
        # Check cash
        required = notional + total_cost
        if required > self._cash:
            logger.warning(
                "Insufficient cash for buy: need %.2f, have %.2f",
                required, self._cash,
            )
            # Adjust qty to available cash
            max_notional = self._cash - total_cost
            if max_notional <= 0:
                return
            qty = int(max_notional / price)
            if qty <= 0:
                return
            notional = qty * price
            required = notional + total_cost

        # Update cash
        self._cash -= required

        # Update position
        if asset_id in self._positions:
            pos = self._positions[asset_id]
            # Update average cost
            total_cost_basis = pos.avg_cost * pos.qty + price * qty
            pos.qty += qty
            pos.avg_cost = total_cost_basis / pos.qty if pos.qty > 0 else 0
        else:
            self._positions[asset_id] = Position(
                asset_id=asset_id,
                qty=qty,
                avg_cost=price,
            )

    def _apply_sell(
        self, asset_id: str, qty: int, price: float, notional: float, total_cost: float
    ) -> None:
        """Apply a sell fill."""
        if asset_id not in self._positions:
            logger.warning("Cannot sell %s: no position", asset_id)
            return

        pos = self._positions[asset_id]
        if qty > pos.qty:
            logger.warning(
                "Cannot sell %d shares of %s: only have %d",
                qty, asset_id, pos.qty,
            )
            qty = pos.qty
            notional = qty * price

        # Calculate realized PnL
        realized = (price - pos.avg_cost) * qty
        self._realized_pnl += realized

        # Update cash
        self._cash += notional - total_cost

        # Update position
        pos.qty -= qty
        if pos.qty <= 0:
            del self._positions[asset_id]

    def mark_to_market(self, prices: dict[str, float], trade_date: date) -> PortfolioState:
        """Mark positions to market and return current state.

        Args:
            prices: dict of asset_id -> current price
            trade_date: current trade date

        Returns:
            PortfolioState with current NAV and exposures
        """
        self._trade_date = trade_date

        gross_exposure = 0.0
        unrealized_pnl = 0.0

        for asset_id, pos in self._positions.items():
            price = prices.get(asset_id, pos.avg_cost)
            pos.market_value = pos.qty * price
            pos.unrealized_pnl = (price - pos.avg_cost) * pos.qty
            gross_exposure += abs(pos.market_value)
            unrealized_pnl += pos.unrealized_pnl

        nav = self._cash + sum(pos.market_value for pos in self._positions.values())
        net_exposure = sum(pos.market_value for pos in self._positions.values())

        return PortfolioState(
            trade_date=trade_date,
            cash=self._cash,
            positions=self._positions.copy(),
            nav=nav,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            realized_pnl=self._realized_pnl,
            unrealized_pnl=unrealized_pnl,
        )

    def get_nav(self, prices: dict[str, float]) -> float:
        """Get current NAV."""
        market_value = sum(
            qty * prices.get(asset_id, pos.avg_cost)
            for asset_id, pos in self._positions.items()
        )
        return self._cash + market_value

    def get_drawdown(self, peak_nav: float, current_nav: float) -> float:
        """Calculate drawdown from peak."""
        if peak_nav <= 0:
            return 0.0
        return (current_nav - peak_nav) / peak_nav

    def to_snapshot_dict(self, trade_date: date, prices: dict[str, float]) -> dict:
        """Convert current state to a snapshot dict for persistence."""
        state = self.mark_to_market(prices, trade_date)
        return {
            "trade_date": trade_date,
            "cash": state.cash,
            "nav": state.nav,
            "positions_count": len(state.positions),
            "gross_exposure": state.gross_exposure,
            "net_exposure": state.net_exposure,
            "realized_pnl": state.realized_pnl,
            "unrealized_pnl": state.unrealized_pnl,
        }
