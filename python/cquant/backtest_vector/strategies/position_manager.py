"""PositionManager — lightweight position management for signal-based strategies.

Provides equal-weight sizing, max-positions limiting, and basic stop-loss /
take-profit logic that can be layered on top of raw signals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import polars as pl

from cquant.core.types import SignalFrame

logger = logging.getLogger(__name__)


@dataclass
class PositionManagerConfig:
    """Configuration for position management.

    Attributes
    ----------
    max_positions:
        Maximum number of simultaneous positions.
    sizing:
        Position sizing method.  ``"equal_weight"`` splits capital equally
        across all positions.
    stop_loss_pct:
        Stop-loss threshold as a negative fraction (e.g. -0.05 for 5%).
        Set to ``None`` to disable.
    take_profit_pct:
        Take-profit threshold as a positive fraction (e.g. 0.10 for 10%).
        Set to ``None`` to disable.
    """

    max_positions: int = 10
    sizing: str = "equal_weight"
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


class PositionManager:
    """Apply position sizing and stop-loss / take-profit to signals.

    Usage::

        pm = PositionManager(PositionManagerConfig(max_positions=5))
        sized_signals = pm.apply(raw_signals, current_positions, prices, as_of_date)
    """

    def __init__(self, config: PositionManagerConfig | None = None) -> None:
        self.config = config or PositionManagerConfig()

    def apply(
        self,
        signals: SignalFrame,
        current_positions: dict[str, float] | None = None,
        prices: pl.DataFrame | None = None,
        as_of_date=None,
    ) -> SignalFrame:
        """Apply position management rules to raw signals.

        Parameters
        ----------
        signals:
            Raw signals from a strategy (SignalFrame).
        current_positions:
            Currently held asset weights ``{asset_id: weight}``.
        prices:
            Price DataFrame with ``[asset_id, trade_date, close]`` columns.
        as_of_date:
            Current evaluation date for stop-loss/take-profit checks.

        Returns
        -------
        Adjusted SignalFrame with sizing and exit signals applied.
        """
        if signals.is_empty():
            return signals

        current_positions = current_positions or {}

        # 1. Separate buy / sell / hold signals
        buy_signals = signals.filter(pl.col("direction") == "long")
        sell_signals = signals.filter(pl.col("direction") == "sell")

        # 2. Check stop-loss / take-profit on current positions
        if (
            (self.config.stop_loss_pct is not None or self.config.take_profit_pct is not None)
            and current_positions
            and prices is not None
            and as_of_date is not None
        ):
            forced_exits = self._check_risk_exits(
                current_positions, prices, as_of_date,
            )
            if not forced_exits.is_empty():
                sell_signals = pl.concat([sell_signals, forced_exits])

        # 3. Remove assets with sell signals from buy candidates
        if not sell_signals.is_empty() and not buy_signals.is_empty():
            sell_assets = set(sell_signals["asset_id"].to_list())
            buy_signals = buy_signals.filter(
                ~pl.col("asset_id").is_in(list(sell_assets))
            )

        # 4. Limit to max_positions
        max_pos = self.config.max_positions
        # Count current positions that are NOT being sold
        sell_set = set(sell_signals["asset_id"].to_list()) if not sell_signals.is_empty() else set()
        held_count = sum(1 for aid in current_positions if aid not in sell_set)
        available_slots = max(0, max_pos - held_count)

        if not buy_signals.is_empty() and len(buy_signals) > available_slots:
            buy_signals = (
                buy_signals
                .sort("strength", descending=True)
                .head(available_slots)
            )

        # 5. Apply equal-weight sizing to buy signals
        if not buy_signals.is_empty() and self.config.sizing == "equal_weight":
            n = len(buy_signals)
            buy_signals = buy_signals.with_columns(
                pl.lit(1.0 / n).alias("strength")
            )

        # 6. Combine and return
        frames = [f for f in [buy_signals, sell_signals] if not f.is_empty()]
        if not frames:
            return _empty_frame()
        return pl.concat(frames)

    def _check_risk_exits(
        self,
        current_positions: dict[str, float],
        prices: pl.DataFrame,
        as_of_date,
    ) -> SignalFrame:
        """Check current positions for stop-loss / take-profit triggers."""
        exits = []

        for asset_id, entry_weight in current_positions.items():
            if entry_weight <= 0:
                continue

            # Get current and entry prices
            day_price = prices.filter(
                (pl.col("asset_id") == asset_id)
                & (pl.col("trade_date") == as_of_date)
            )
            if day_price.is_empty():
                continue
            current_price = float(day_price["close"].item())

            # For a proper implementation, entry price should be tracked
            # externally.  Here we use the earliest available price as a proxy.
            asset_hist = prices.filter(
                (pl.col("asset_id") == asset_id)
                & (pl.col("trade_date") <= as_of_date)
            ).sort("trade_date")

            if asset_hist.is_empty():
                continue

            entry_price = float(asset_hist["close"].head(1).item())
            if entry_price <= 0:
                continue

            pnl_pct = (current_price - entry_price) / entry_price

            should_exit = False
            reason = ""

            if self.config.stop_loss_pct is not None and pnl_pct <= self.config.stop_loss_pct:
                should_exit = True
                reason = f"stop_loss ({pnl_pct:.2%})"
            elif self.config.take_profit_pct is not None and pnl_pct >= self.config.take_profit_pct:
                should_exit = True
                reason = f"take_profit ({pnl_pct:.2%})"

            if should_exit:
                logger.debug(
                    "PositionManager: forcing exit for %s — %s",
                    asset_id, reason,
                )
                exits.append({
                    "asset_id": asset_id,
                    "signal_date": as_of_date,
                    "direction": "sell",
                    "strength": 1.0,
                    "confidence": 1.0,
                })

        if not exits:
            return _empty_frame()
        return pl.DataFrame(exits)


def _empty_frame() -> SignalFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "signal_date": pl.Date,
            "direction": pl.Utf8,
            "strength": pl.Float64,
            "confidence": pl.Float64,
        }
    )
