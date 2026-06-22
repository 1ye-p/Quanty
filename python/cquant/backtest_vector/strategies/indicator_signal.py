"""IndicatorSignalStrategy — generate signals based on indicator condition DSL.

Uses the condition DSL from :mod:`cquant.indicator.conditions` to evaluate
buy/sell conditions on computed technical indicators.  Indicators are
auto-extracted from the DSL strings and computed via the indicator registry.
"""

from __future__ import annotations

import logging
import re

import polars as pl

from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.types import SignalFrame
from cquant.indicator import registry
from cquant.indicator.conditions import evaluate_condition, parse_condition

logger = logging.getLogger(__name__)

# Pattern to extract indicator references like ``rsi(14)`` or ``sma(20)``
# from condition DSL strings.
_IND_REF_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)")


def _extract_indicator_refs(conditions: list[str]) -> list[dict[str, str | dict]]:
    """Extract indicator references from condition DSL strings.

    Parses ``rsi(14)``, ``sma(20, column=close)`` etc. into indicator specs
    compatible with :func:`cquant.indicator.registry.compute`.

    Returns a list of dicts with keys:
      - ``name``: indicator name (e.g. ``"rsi"``)
      - ``params``: parameter dict (e.g. ``{"period": 14}``)
      - ``col_name``: the full DSL column name (e.g. ``"rsi(14)"``)
    """
    seen: set[str] = set()
    refs: list[dict[str, str | dict]] = []

    for cond_str in conditions:
        for match in _IND_REF_RE.finditer(cond_str):
            name = match.group(1)
            args_str = match.group(2)
            col_name = f"{name}({args_str})"

            if col_name in seen:
                continue
            seen.add(col_name)

            # Parse arguments: positional (int/float) or keyword (key=value)
            params: dict = {}
            if args_str.strip():
                for arg in args_str.split(","):
                    arg = arg.strip()
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        params[k.strip()] = _parse_value(v.strip())
                    else:
                        # Positional argument — use the first param name from registry
                        spec = registry.get_indicator(name)
                        if spec and spec.params:
                            first_param_name = spec.params[0][0]
                            params[first_param_name] = _parse_value(arg)
                        else:
                            # Fallback: try 'period' as common default
                            params["period"] = _parse_value(arg)

            refs.append({"name": name, "params": params, "col_name": col_name})

    return refs


def _parse_value(raw: str) -> int | float | str:
    """Parse a string value to int, float, or leave as string."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _compute_indicators(
    df: pl.DataFrame,
    indicator_refs: list[dict],
) -> pl.DataFrame:
    """Compute indicators and rename columns to DSL-compatible names.

    The registry computes columns named after the indicator (e.g. ``rsi``),
    but the condition DSL expects parameterized names (e.g. ``rsi(14)``).
    This function renames accordingly.
    """
    result = df.clone()

    for ref in indicator_refs:
        name: str = ref["name"]  # type: ignore[assignment]
        params: dict = ref["params"]  # type: ignore[assignment]
        col_name: str = ref["col_name"]  # type: ignore[assignment]

        spec = registry.get_indicator(name)
        if spec is None:
            logger.warning("Unknown indicator %r — skipping", name)
            continue

        # Merge default params with user-specified ones
        merged = spec.default_params()
        merged.update(params)

        series = spec.fn(df, **merged)
        # Rename to DSL-compatible column name
        result = result.with_columns(series.alias(col_name))

    return result


def _build_signal_frame(
    asset_id: str,
    dates: list,
    direction: str,
    strength: float = 1.0,
    confidence: float = 1.0,
) -> SignalFrame:
    """Build a SignalFrame for one asset + direction from a list of dates."""
    if not dates:
        return pl.DataFrame(
            schema={
                "asset_id": pl.Utf8,
                "signal_date": pl.Date,
                "direction": pl.Utf8,
                "strength": pl.Float64,
                "confidence": pl.Float64,
            }
        )
    n = len(dates)
    return pl.DataFrame({
        "asset_id": [asset_id] * n,
        "signal_date": dates,
        "direction": [direction] * n,
        "strength": [strength] * n,
        "confidence": [confidence] * n,
    })


class IndicatorSignalStrategy(Strategy):
    """Strategy that generates signals based on indicator condition DSL.

    Evaluates entry and exit conditions (written in the indicator condition DSL)
    on computed technical indicators to produce buy/sell signals per asset.

    Parameters
    ----------
    strategy_id:
        Unique identifier for this strategy.
    entry_conditions:
        List of condition DSL strings for entry signals (buy).
        Example: ``["rsi(14) < 30 AND close > sma(20)"]``
    exit_conditions:
        List of condition DSL strings for exit signals (sell).
        Example: ``["rsi(14) > 70"]``
    indicators:
        Explicit indicator specs to compute.  If empty, indicators are
        auto-extracted from the condition DSL strings.
        Example: ``[{"name": "rsi", "params": {"period": 14}}]``
    max_positions:
        Maximum number of simultaneous long positions.  Only the top
        ``max_positions`` assets (by signal strength) are kept.
    """

    def __init__(
        self,
        strategy_id: str,
        entry_conditions: list[str] | None = None,
        exit_conditions: list[str] | None = None,
        indicators: list[dict] | None = None,
        max_positions: int = 10,
    ) -> None:
        self._strategy_id = strategy_id
        self._entry_conditions = entry_conditions or []
        self._exit_conditions = exit_conditions or []
        self._indicators = indicators or []
        self._max_positions = max_positions

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def generate_signals(self, ctx: StrategyContext) -> SignalFrame:
        """Generate buy/sell signals for the given context.

        For each asset in the universe, computes indicators on historical
        prices, evaluates entry/exit conditions, and emits signals for the
        current ``as_of_date``.
        """
        empty = _empty_frame()

        if ctx.prices is None or ctx.prices.is_empty():
            return empty

        # Get assets with data on this date
        asset_ids = (
            ctx.prices
            .filter(pl.col("trade_date") == ctx.as_of_date)
            ["asset_id"]
            .unique()
            .to_list()
        )
        if not asset_ids:
            return empty

        # Collect all condition DSL strings for indicator extraction
        all_conditions = self._entry_conditions + self._exit_conditions

        # Build indicator specs: explicit config takes priority, then auto-extract
        indicator_refs: list[dict] = []
        if self._indicators:
            for ind in self._indicators:
                name = ind["name"]
                params = ind.get("params", {})
                # Build col_name from name + first positional param
                if params:
                    first_val = next(iter(params.values()))
                    col_name = f"{name}({first_val})"
                else:
                    col_name = name
                indicator_refs.append({
                    "name": name,
                    "params": params,
                    "col_name": col_name,
                })

        # Auto-extract from DSL strings (only adds what's not already explicit)
        auto_refs = _extract_indicator_refs(all_conditions)
        existing_cols = {r["col_name"] for r in indicator_refs}
        for ref in auto_refs:
            if ref["col_name"] not in existing_cols:
                indicator_refs.append(ref)

        if not indicator_refs:
            logger.debug(
                "IndicatorSignalStrategy '%s': no indicators to compute — returning empty",
                self._strategy_id,
            )
            return empty

        # Process each asset
        all_buy_frames: list[SignalFrame] = []
        all_sell_frames: list[SignalFrame] = []

        for asset_id in asset_ids:
            # Get historical prices for this asset (up to as_of_date)
            asset_prices = ctx.prices.filter(
                (pl.col("asset_id") == asset_id)
                & (pl.col("trade_date") <= ctx.as_of_date)
            ).sort("trade_date")

            if asset_prices.is_empty():
                continue

            # Compute indicators
            try:
                indicator_df = _compute_indicators(asset_prices, indicator_refs)
            except Exception as exc:
                logger.warning(
                    "IndicatorSignalStrategy '%s': indicator compute failed for %s: %s",
                    self._strategy_id, asset_id, exc,
                )
                continue

            # Evaluate entry conditions
            for cond_dsl in self._entry_conditions:
                try:
                    result = evaluate_condition(indicator_df, cond_dsl)
                    # Only emit signals for the current as_of_date
                    dates = [
                        d for d in result["signal_dates"]
                        if d == ctx.as_of_date
                    ]
                    if dates:
                        all_buy_frames.append(
                            _build_signal_frame(asset_id, dates, "long")
                        )
                except Exception as exc:
                    logger.warning(
                        "IndicatorSignalStrategy '%s': entry condition %r failed for %s: %s",
                        self._strategy_id, cond_dsl, asset_id, exc,
                    )

            # Evaluate exit conditions
            for cond_dsl in self._exit_conditions:
                try:
                    result = evaluate_condition(indicator_df, cond_dsl)
                    dates = [
                        d for d in result["signal_dates"]
                        if d == ctx.as_of_date
                    ]
                    if dates:
                        all_sell_frames.append(
                            _build_signal_frame(asset_id, dates, "sell")
                        )
                except Exception as exc:
                    logger.warning(
                        "IndicatorSignalStrategy '%s': exit condition %r failed for %s: %s",
                        self._strategy_id, cond_dsl, asset_id, exc,
                    )

        # Combine signals — buy signals take priority over sell for same asset
        buy_df = _concat_frames(all_buy_frames)
        sell_df = _concat_frames(all_sell_frames)

        if buy_df.is_empty() and sell_df.is_empty():
            return empty

        # If an asset has both buy and sell on the same day, keep only buy
        if not buy_df.is_empty() and not sell_df.is_empty():
            buy_assets = set(buy_df["asset_id"].to_list())
            sell_df = sell_df.filter(~pl.col("asset_id").is_in(list(buy_assets)))

        # Apply max_positions limit to buy signals (keep top by strength)
        if not buy_df.is_empty() and len(buy_df) > self._max_positions:
            buy_df = buy_df.sort("strength", descending=True).head(self._max_positions)

        # Combine
        frames = [f for f in [buy_df, sell_df] if not f.is_empty()]
        if not frames:
            return empty
        return pl.concat(frames)


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


def _concat_frames(frames: list[SignalFrame]) -> SignalFrame:
    """Concat non-empty frames, returning empty frame if none."""
    non_empty = [f for f in frames if not f.is_empty()]
    if not non_empty:
        return _empty_frame()
    return pl.concat(non_empty)
