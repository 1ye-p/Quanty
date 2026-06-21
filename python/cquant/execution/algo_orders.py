"""cquant.execution.algo_orders — Algorithmic order execution engines.

Provides TWAP and VWAP algorithmic order types for execution:
- TWAP (Time-Weighted Average Price): splits order into equal time intervals
- VWAP (Volume-Weighted Average Price): splits order based on historical volume profile

Usage::

    # TWAP example
    params = AlgoOrderParams(
        algo_type=AlgoType.TWAP,
        asset_id="SSE:600036",
        side="buy",
        total_qty=10000,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=2),
        num_slices=10,
    )
    engine = TWAPEngine()
    slices = engine.create_slices(params)

    # VWAP example
    engine = VWAPEngine(catalog)
    slices = engine.create_slices(params)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


class AlgoType(str, Enum):
    """Algorithm order type."""
    TWAP = "twap"
    VWAP = "vwap"


@dataclass
class AlgoOrderParams:
    """Parameters for an algorithmic order."""
    algo_type: AlgoType
    asset_id: str
    side: str  # "buy" | "sell"
    total_qty: int
    start_time: datetime
    end_time: datetime
    num_slices: int = 10  # TWAP: number of equal slices
    lookback_days: int = 20  # VWAP: days to compute volume profile
    broker: str = "paper"
    strategy_id: str = ""


@dataclass
class AlgoSlice:
    """A single slice of an algo order."""
    slice_id: int
    scheduled_time: datetime
    qty: int
    status: str = "pending"  # pending | filled | failed | cancelled
    filled_price: float | None = None
    filled_qty: int | None = None
    filled_at: datetime | None = None
    order_id: str | None = None  # Broker order ID after submission


@dataclass
class AlgoOrder:
    """An algorithmic order with multiple slices."""
    order_id: str
    params: AlgoOrderParams
    slices: list[AlgoSlice] = field(default_factory=list)
    status: str = "active"  # active | completed | cancelled
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def filled_slices(self) -> list[AlgoSlice]:
        """Get slices that have been filled."""
        return [s for s in self.slices if s.status == "filled"]

    @property
    def pending_slices(self) -> list[AlgoSlice]:
        """Get slices that are pending execution."""
        return [s for s in self.slices if s.status == "pending"]

    @property
    def cumulative_filled_qty(self) -> int:
        """Get total filled quantity across all slices."""
        return sum(s.filled_qty or 0 for s in self.filled_slices)

    @property
    def cumulative_avg_price(self) -> float | None:
        """Get volume-weighted average fill price."""
        filled = self.filled_slices
        if not filled:
            return None
        total_notional = sum((s.filled_price or 0) * (s.filled_qty or 0) for s in filled)
        total_qty = sum(s.filled_qty or 0 for s in filled)
        if total_qty <= 0:
            return None
        return total_notional / total_qty

    @property
    def progress_pct(self) -> float:
        """Get execution progress as percentage."""
        if self.params.total_qty <= 0:
            return 0.0
        return (self.cumulative_filled_qty / self.params.total_qty) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "order_id": self.order_id,
            "order_type": self.params.algo_type.value,
            "algo_type": self.params.algo_type.value,  # backward compat
            "asset_id": self.params.asset_id,
            "side": self.params.side,
            "total_qty": self.params.total_qty,
            "status": self.status,
            "progress_pct": round(self.progress_pct, 2),
            "filled_qty": self.cumulative_filled_qty,
            "avg_price": self.cumulative_avg_price,
            "slippage": 0.0,  # TODO: compute actual slippage vs arrival price
            "updated_at": self.completed_at.isoformat() if self.completed_at else self.created_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "params": {
                "num_slices": self.params.num_slices,
                "lookback_days": self.params.lookback_days,
                "start_time": self.params.start_time.isoformat(),
                "end_time": self.params.end_time.isoformat(),
                "broker": self.params.broker,
                "strategy_id": self.params.strategy_id,
            },
            "slices": [
                {
                    "slice_id": str(s.slice_id),
                    "scheduled_time": s.scheduled_time.isoformat(),
                    "qty": s.qty,
                    "status": s.status,
                    "filled_price": s.filled_price,
                    "filled_qty": s.filled_qty,
                    "filled_at": s.filled_at.isoformat() if s.filled_at else None,
                    "order_id": s.order_id,
                }
                for s in self.slices
            ],
        }


class TWAPEngine:
    """Time-Weighted Average Price algorithm.

    Splits an order into equal time intervals with equal quantities.
    This ensures the execution is spread evenly over the specified time window.

    Usage::

        engine = TWAPEngine()
        slices = engine.create_slices(params)
    """

    def create_slices(self, params: AlgoOrderParams) -> list[AlgoSlice]:
        """Split order into equal time intervals.

        Parameters
        ----------
        params:
            AlgoOrderParams with start_time, end_time, num_slices, and total_qty.

        Returns
        -------
        List of AlgoSlice objects with scheduled times and quantities.

        Raises
        ------
        ValueError:
            If params are invalid (end_time <= start_time, num_slices <= 0, etc.)
        """
        # Validate params
        if params.end_time <= params.start_time:
            raise ValueError("end_time must be after start_time")
        if params.num_slices <= 0:
            raise ValueError("num_slices must be > 0")
        if params.total_qty <= 0:
            raise ValueError("total_qty must be > 0")

        total_seconds = (params.end_time - params.start_time).total_seconds()
        interval = total_seconds / params.num_slices
        qty_per_slice = params.total_qty // params.num_slices
        remainder = params.total_qty % params.num_slices

        slices: list[AlgoSlice] = []
        for i in range(params.num_slices):
            scheduled = params.start_time + timedelta(seconds=i * interval)
            # Distribute remainder to first slices (1 extra share each)
            qty = qty_per_slice + (1 if i < remainder else 0)
            slices.append(AlgoSlice(slice_id=i, scheduled_time=scheduled, qty=qty))

        logger.info(
            "TWAP: Created %d slices for %s %s x%d over %s to %s",
            len(slices),
            params.side,
            params.asset_id,
            params.total_qty,
            params.start_time.isoformat(),
            params.end_time.isoformat(),
        )
        return slices


class VWAPEngine:
    """Volume-Weighted Average Price algorithm.

    Splits an order based on historical intraday volume profile.
    Allocates more quantity to high-volume periods to minimize market impact.

    Usage::

        engine = VWAPEngine(catalog)
        slices = engine.create_slices(params)
    """

    def __init__(self, catalog: Catalog | None = None) -> None:
        self._catalog = catalog

    def get_volume_profile(
        self,
        asset_id: str,
        lookback_days: int = 20,
    ) -> dict[int, float]:
        """Get historical intraday volume distribution by hour.

        Queries the catalog for historical volume data and computes the
        fraction of daily volume for each trading hour.

        Parameters
        ----------
        asset_id:
            Asset identifier (e.g., "SSE:600036").
        lookback_days:
            Number of historical days to look back for volume profile.

        Returns
        -------
        Dict mapping hour_of_day (9-15) to fraction_of_daily_volume.
        Returns uniform distribution if no data available.
        """
        # Default trading hours for CN market: 9:30-11:30, 13:00-15:00
        # Map to hours: 9, 10, 11, 13, 14
        default_hours = {9: 0.2, 10: 0.2, 11: 0.2, 13: 0.2, 14: 0.2}

        if self._catalog is None:
            logger.warning("No catalog provided, using uniform volume profile")
            return default_hours

        try:
            # Extract symbol from asset_id
            symbol = asset_id.split(":")[-1] if ":" in asset_id else asset_id

            # TODO: Implement intraday volume profile when data is available
            # Current silver_prices_1d only has daily aggregates, not hourly
            logger.info(
                "VWAP: Using default volume profile for %s (intraday data not available)",
                asset_id,
            )
            return default_hours

        except Exception as exc:
            logger.warning(
                "VWAP: Failed to get volume profile for %s: %s. Using uniform.",
                asset_id,
                exc,
            )
            return default_hours

    def create_slices(self, params: AlgoOrderParams) -> list[AlgoSlice]:
        """Split order based on historical volume profile.

        Parameters
        ----------
        params:
            AlgoOrderParams with start_time, end_time, lookback_days, and total_qty.

        Returns
        -------
        List of AlgoSlice objects with scheduled times and quantities
        proportional to historical volume.

        Raises
        ------
        ValueError:
            If params are invalid.
        """
        # Validate params
        if params.end_time <= params.start_time:
            raise ValueError("end_time must be after start_time")
        if params.total_qty <= 0:
            raise ValueError("total_qty must be > 0")

        # Get volume profile
        profile = self.get_volume_profile(params.asset_id, params.lookback_days)

        # Determine trading hours in the execution window
        start_hour = params.start_time.hour
        end_hour = params.end_time.hour

        # Filter profile to execution window
        active_hours = {
            h: frac for h, frac in profile.items()
            if start_hour <= h <= end_hour
        }

        if not active_hours:
            # Fallback: create uniform slices if no volume data in window
            logger.warning(
                "VWAP: No volume data in execution window %d-%d, using TWAP fallback",
                start_hour,
                end_hour,
            )
            twap = TWAPEngine()
            return twap.create_slices(params)

        # Normalize fractions to sum to 1
        total_frac = sum(active_hours.values())
        normalized = {h: frac / total_frac for h, frac in active_hours.items()}

        # Create slices for each trading hour
        slices: list[AlgoSlice] = []
        allocated_qty = 0
        hours_sorted = sorted(normalized.keys())

        for i, hour in enumerate(hours_sorted):
            frac = normalized[hour]

            if i < len(hours_sorted) - 1:
                # Proportional allocation with rounding
                qty = int(params.total_qty * frac)
                # Round to lot size (100 shares)
                qty = (qty // 100) * 100
                if qty < 100:
                    qty = 100
            else:
                # Last slice gets remainder
                qty = params.total_qty - allocated_qty

            if qty <= 0:
                continue

            # Schedule at the start of each hour
            scheduled = params.start_time.replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            # If scheduled is before start_time, use start_time
            if scheduled < params.start_time:
                scheduled = params.start_time

            slices.append(AlgoSlice(slice_id=i, scheduled_time=scheduled, qty=qty))
            allocated_qty += qty

        # Adjust if we over-allocated due to rounding
        if allocated_qty > params.total_qty and slices:
            excess = allocated_qty - params.total_qty
            # Reduce from largest slice
            largest = max(slices, key=lambda s: s.qty)
            largest.qty = max(100, largest.qty - excess)

        logger.info(
            "VWAP: Created %d slices for %s %s x%d based on volume profile",
            len(slices),
            params.side,
            params.asset_id,
            params.total_qty,
        )
        return slices


class AlgoOrderManager:
    """Manages algorithmic order lifecycle.

    Creates, tracks, and executes algo orders using the specified broker.

    Usage::

        manager = AlgoOrderManager(broker)
        order = manager.create_order(params)
        # Execute slices as they become due
        manager.execute_due_slices(order.order_id)
    """

    def __init__(self, broker: Any) -> None:
        self._broker = broker
        self._orders: dict[str, AlgoOrder] = {}
        self._twap_engine = TWAPEngine()
        self._vwap_engine = VWAPEngine()

    def create_order(self, params: AlgoOrderParams) -> AlgoOrder:
        """Create a new algorithmic order.

        Parameters
        ----------
        params:
            AlgoOrderParams defining the order.

        Returns
        -------
            AlgoOrder with slices created.
        """
        order_id = f"algo-{str(uuid.uuid4())[:8]}"

        # Create slices based on algo type
        if params.algo_type == AlgoType.TWAP:
            slices = self._twap_engine.create_slices(params)
        elif params.algo_type == AlgoType.VWAP:
            slices = self._vwap_engine.create_slices(params)
        else:
            raise ValueError(f"Unknown algo type: {params.algo_type}")

        order = AlgoOrder(
            order_id=order_id,
            params=params,
            slices=slices,
        )

        self._orders[order_id] = order
        logger.info(
            "Created algo order %s: %s %s %s x%d (%d slices)",
            order_id,
            params.algo_type.value,
            params.side,
            params.asset_id,
            params.total_qty,
            len(slices),
        )
        return order

    def get_order(self, order_id: str) -> AlgoOrder | None:
        """Get algo order by ID."""
        return self._orders.get(order_id)

    def get_orders(self, status: str | None = None) -> list[AlgoOrder]:
        """Get all algo orders, optionally filtered by status."""
        orders = list(self._orders.values())
        if status:
            orders = [o for o in orders if o.status == status]
        return orders

    def cancel_order(self, order_id: str) -> AlgoOrder:
        """Cancel an algo order and all pending slices.

        Parameters
        ----------
        order_id:
            ID of the algo order to cancel.

        Returns
        -------
            Updated AlgoOrder.

        Raises
        ------
        ValueError:
            If order not found.
        """
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"Algo order not found: {order_id}")

        # Cancel all pending slices
        for slice in order.pending_slices:
            slice.status = "cancelled"
            # Cancel broker order if submitted
            if slice.order_id:
                try:
                    self._broker.cancel_order(slice.order_id)
                except Exception as exc:
                    logger.warning(
                        "Failed to cancel broker order %s: %s",
                        slice.order_id,
                        exc,
                    )

        order.status = "cancelled"
        order.completed_at = datetime.now()
        logger.info("Cancelled algo order %s", order_id)
        return order

    def execute_due_slices(self, order_id: str) -> list[AlgoSlice]:
        """Execute slices that are due (scheduled_time <= now).

        Parameters
        ----------
        order_id:
            ID of the algo order.

        Returns
        -------
            List of slices that were executed.

        Raises
        ------
        ValueError:
            If order not found.
        """
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"Algo order not found: {order_id}")

        if order.status != "active":
            return []

        from cquant.execution.broker import Order as BrokerOrder

        now = datetime.now()
        executed: list[AlgoSlice] = []

        for slice in order.pending_slices:
            if slice.scheduled_time <= now:
                try:
                    # Create broker order

                    broker_order = BrokerOrder(
                        order_id=f"{order_id}-s{slice.slice_id}",
                        asset_id=order.params.asset_id,
                        side=order.params.side,
                        qty=slice.qty,
                        order_type="market",
                        strategy_id=order.params.strategy_id or "algo_order",
                    )

                    # Submit to broker
                    result = self._broker.submit_order(broker_order)

                    # Update slice status
                    slice.order_id = result.order_id
                    if result.status.value == "filled":
                        slice.status = "filled"
                        slice.filled_price = result.filled_price
                        slice.filled_qty = result.filled_qty
                        slice.filled_at = result.filled_at
                    else:
                        slice.status = "failed"
                        logger.warning(
                            "Slice %d of order %s failed: %s",
                            slice.slice_id,
                            order_id,
                            result.reject_reason,
                        )

                    executed.append(slice)

                except Exception as exc:
                    slice.status = "failed"
                    logger.error(
                        "Error executing slice %d of order %s: %s",
                        slice.slice_id,
                        order_id,
                        exc,
                    )
                    executed.append(slice)

        # Check if order is complete
        if not order.pending_slices:
            order.status = "completed"
            order.completed_at = datetime.now()
            logger.info("Algo order %s completed", order_id)

        return executed

    def execute_all_pending(self) -> dict[str, list[AlgoSlice]]:
        """Execute all due slices across all active orders.

        Returns
        -------
            Dict mapping order_id to list of executed slices.
        """
        results: dict[str, list[AlgoSlice]] = {}

        for order_id, order in self._orders.items():
            if order.status == "active":
                executed = self.execute_due_slices(order_id)
                if executed:
                    results[order_id] = executed

        return results
