"""Indicator registry — register, lookup, list, and compute indicators."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from cquant.indicator.base import IndicatorSpec

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, IndicatorSpec] = {}


def register(
    name: str,
    category: str,
    description: str,
    params: list[tuple[str, type, Any]],
    fn: Any,
) -> None:
    """Register an indicator in the global registry.

    Args:
        name: Unique indicator name (e.g. 'sma', 'rsi').
        category: Category grouping (e.g. 'moving_average', 'oscillator').
        description: Human-readable description.
        params: List of (param_name, param_type, default_value) tuples.
        fn: Callable that takes (pl.DataFrame, **params) -> pl.Series.
    """
    if name in _REGISTRY:
        logger.warning("Overwriting existing indicator: %s", name)
    _REGISTRY[name] = IndicatorSpec(
        name=name,
        category=category,
        description=description,
        params=params,
        fn=fn,
    )


def get_indicator(name: str) -> IndicatorSpec | None:
    """Retrieve an indicator specification by name."""
    return _REGISTRY.get(name)


def list_indicators(category: str | None = None) -> list[IndicatorSpec]:
    """List all registered indicators, optionally filtered by category.

    Args:
        category: If provided, only return indicators in this category.

    Returns:
        Sorted list of IndicatorSpec.
    """
    specs = list(_REGISTRY.values())
    if category:
        specs = [s for s in specs if s.category == category]
    return sorted(specs, key=lambda s: (s.category, s.name))


def compute(
    data: pl.DataFrame,
    indicators: list[dict[str, Any]],
) -> pl.DataFrame:
    """Compute multiple indicators on a DataFrame.

    Args:
        data: Input OHLCV DataFrame.
        indicators: List of dicts with keys 'name' (str) and optional 'params' (dict).

    Returns:
        New DataFrame with indicator columns appended.

    Raises:
        KeyError: If an indicator name is not registered.
    """
    result = data.clone()
    for ind in indicators:
        name = ind["name"]
        spec = _REGISTRY.get(name)
        if spec is None:
            raise KeyError(f"Unknown indicator: {name!r}")
        params = ind.get("params", {})
        series = spec.fn(data, **params)
        result = result.with_columns(series.alias(name))
    return result
