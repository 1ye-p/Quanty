"""Base types and utilities for the indicator module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import polars as pl


@dataclass(frozen=True)
class IndicatorSpec:
    """Specification for a registered technical indicator."""

    name: str
    category: str
    description: str
    params: list[tuple[str, type, Any]]  # (param_name, param_type, default_value)
    fn: Callable[..., pl.Series]

    def default_params(self) -> dict[str, Any]:
        """Return a dict of default parameter values."""
        return {name: default for name, _, default in self.params}


# Standard OHLCV column names expected by indicators
OHLCV_COLUMNS: set[str] = {"open", "high", "low", "close", "volume", "amount"}


def validate_ohlcv(df: pl.DataFrame, required: set[str] | None = None) -> None:
    """Validate that a DataFrame contains required OHLCV columns.

    Args:
        df: Input DataFrame.
        required: Column names that must be present. Defaults to OHLCV_COLUMNS.

    Raises:
        ValueError: If any required column is missing.
    """
    cols = required or OHLCV_COLUMNS
    missing = cols - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")
