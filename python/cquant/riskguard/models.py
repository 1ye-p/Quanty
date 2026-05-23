"""cquant.riskguard.models — Core risk data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import polars as pl

from cquant.core.types import RiskSnapshot


@dataclass(frozen=True)
class RiskLimit:
    """A single risk limit definition."""

    name: str
    limit_type: str       # 'position_pct', 'gross_leverage', 'sector_pct', 'factor_exposure'
    threshold: float
    hard: bool = True     # True = hard limit (order rejected); False = soft (warning)
    description: str = ""


@dataclass
class RiskContext:
    """Context provided to each RiskPolicy during evaluation."""

    as_of_date: date
    portfolio_nav: Decimal              # Net asset value
    current_positions: pl.DataFrame     # [asset_id, quantity, market_value, weight]
    current_snapshot: RiskSnapshot | None = None
    factor_exposure: dict[str, float] = field(default_factory=dict)
    sector_exposure: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)  # Policy-specific extra context


@dataclass(frozen=True)
class RiskBudget:
    """Per-strategy risk budget allocation."""

    strategy_id: str
    risk_budget: float       # Max allowed portfolio risk contribution (fraction of total)
    capital_budget: float    # Max capital allocation fraction
    turnover_budget: float   # Max 1-way turnover per rebalance period
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass
class SizingContext:
    """Context provided to PositionSizer during weight computation."""

    as_of_date: date
    portfolio_nav: Decimal
    universe_ids: list[str]
    expected_returns: pl.DataFrame | None = None    # [asset_id, expected_return]
    return_covariance: pl.DataFrame | None = None   # Asset covariance matrix
    volatility: pl.DataFrame | None = None          # [asset_id, volatility]
    constraints: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
