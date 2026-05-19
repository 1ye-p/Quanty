"""cquant.factorlab.factor — Factor ABC, context, and registry."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import polars as pl

from cquant.core.errors import FactorComputeError

logger = logging.getLogger(__name__)


@dataclass
class FactorContext:
    """Runtime context passed to each factor during computation."""

    as_of_date: date
    frequency: str = "1d"
    universe_id: str = ""
    # Additional data frames available to factors (e.g. fundamentals, macro)
    extra: dict[str, pl.DataFrame] = field(default_factory=dict)


class Factor(ABC):
    """Abstract base for all cQuant factors.

    A factor takes a price/fundamental DataFrame and returns a Series of
    per-asset values for a given computation window.

    Subclasses should be pure functions with no side effects.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stable factor identifier, e.g. 'ret_20d'."""

    @property
    def description(self) -> str:
        return ""

    @property
    def tags(self) -> list[str]:
        """Taxonomy tags, e.g. ['momentum', 'price']."""
        return []

    @abstractmethod
    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        """Compute the factor over *frame* and return a Series named after this factor.

        *frame* must have at minimum: [asset_id (str), trade_date (date), close (f64)].
        Returns a Series with the same length and order as *frame*, named self.name.
        """

    def safe_compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        """Wrapper that logs and re-raises computation errors."""
        try:
            result = self.compute(frame, ctx)
            if result.name != self.name:
                result = result.alias(self.name)
            return result
        except Exception as exc:
            raise FactorComputeError(
                f"Factor '{self.name}' failed on {ctx.as_of_date}: {exc}"
            ) from exc


class FactorRegistry:
    """In-process registry of available factors."""

    def __init__(self) -> None:
        self._factors: dict[str, Factor] = {}

    def register(self, factor: Factor) -> None:
        if factor.name in self._factors:
            logger.warning("Overwriting existing factor: %s", factor.name)
        self._factors[factor.name] = factor

    def get(self, name: str) -> Factor:
        if name not in self._factors:
            raise KeyError(f"Factor '{name}' not found in registry")
        return self._factors[name]

    def all_names(self) -> list[str]:
        return sorted(self._factors.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._factors
