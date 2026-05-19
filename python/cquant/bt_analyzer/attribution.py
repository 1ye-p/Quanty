"""cquant.bt_analyzer.attribution — Performance attribution analysis.

Provides:
- Brinson Attribution: asset allocation + stock selection contribution
- Factor Attribution: factor exposure + factor return decomposition
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BrinsonResult:
    """Result of Brinson attribution analysis."""
    total_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    sector_details: dict[str, dict[str, float]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorAttributionResult:
    """Result of factor attribution analysis."""
    total_return: float
    factor_returns: dict[str, float]  # factor_name -> contribution
    specific_return: float
    factor_exposures: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class BrinsonAttribution:
    """Brinson-Fachler attribution model.

    Decomposes active return into:
    - Allocation effect: sector weight differences * benchmark sector returns
    - Selection effect: portfolio stock returns * benchmark sector weights
    - Interaction effect: weight differences * return differences

    Usage::

        analyzer = BrinsonAttribution()
        result = analyzer.analyze(
            portfolio_weights={"SSE:600036": 0.5, "SZSE:000858": 0.5},
            benchmark_weights={"SSE:600036": 0.3, "SZSE:000858": 0.7},
            portfolio_returns={"SSE:600036": 0.10, "SZSE:000858": 0.15},
            benchmark_returns={"SSE:600036": 0.08, "SZSE:000858": 0.12},
            sector_map={"SSE:600036": "Finance", "SZSE:000858": "Consumer"},
        )
    """

    def analyze(
        self,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
        sector_map: dict[str, str] | None = None,
    ) -> BrinsonResult:
        """Perform Brinson attribution analysis.

        Args:
            portfolio_weights: Portfolio weights by asset
            benchmark_weights: Benchmark weights by asset
            portfolio_returns: Portfolio returns by asset
            benchmark_returns: Benchmark returns by asset
            sector_map: Optional mapping of asset_id -> sector

        Returns:
            BrinsonResult with allocation, selection, and interaction effects
        """
        # If no sector map, treat each asset as its own sector
        if sector_map is None:
            sector_map = {aid: aid for aid in portfolio_weights}

        # Group by sector
        sectors = set(sector_map.values())

        # Calculate sector-level aggregates
        sector_data = {}
        for sector in sectors:
            assets_in_sector = [a for a, s in sector_map.items() if s == sector]

            port_weight = sum(portfolio_weights.get(a, 0) for a in assets_in_sector)
            bench_weight = sum(benchmark_weights.get(a, 0) for a in assets_in_sector)

            # Weighted average returns
            port_return = sum(
                portfolio_weights.get(a, 0) * portfolio_returns.get(a, 0)
                for a in assets_in_sector
            )
            bench_return = sum(
                benchmark_weights.get(a, 0) * benchmark_returns.get(a, 0)
                for a in assets_in_sector
            )

            # Normalize by weights
            if port_weight > 0:
                port_return /= port_weight
            if bench_weight > 0:
                bench_return /= bench_weight

            sector_data[sector] = {
                "port_weight": port_weight,
                "bench_weight": bench_weight,
                "port_return": port_return,
                "bench_return": bench_return,
            }

        # Benchmark total return
        bench_total = sum(
            benchmark_weights.get(a, 0) * benchmark_returns.get(a, 0)
            for a in benchmark_weights
        )

        # Calculate effects
        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0

        for sector, data in sector_data.items():
            wp = data["port_weight"]
            wb = data["bench_weight"]
            rp = data["port_return"]
            rb = data["bench_return"]

            # Allocation: (wp - wb) * (rb - Rb)
            allocation_effect += (wp - wb) * (rb - bench_total)

            # Selection: wb * (rp - rb)
            selection_effect += wb * (rp - rb)

            # Interaction: (wp - wb) * (rp - rb)
            interaction_effect += (wp - wb) * (rp - rb)

        # Portfolio total return
        port_total = sum(
            portfolio_weights.get(a, 0) * portfolio_returns.get(a, 0)
            for a in portfolio_weights
        )

        return BrinsonResult(
            total_return=port_total,
            allocation_effect=allocation_effect,
            selection_effect=selection_effect,
            interaction_effect=interaction_effect,
            sector_details=sector_data,
            metadata={
                "benchmark_return": bench_total,
                "active_return": port_total - bench_total,
            },
        )


class FactorAttribution:
    """Factor-based return attribution.

    Decomposes portfolio return into:
    - Factor returns: exposure to each factor * factor return
    - Specific return: unexplained return (alpha)

    Usage::

        analyzer = FactorAttribution()
        result = analyzer.analyze(
            portfolio_return=0.10,
            factor_exposures={"momentum": 0.5, "value": -0.2},
            factor_returns={"momentum": 0.08, "value": 0.05},
        )
    """

    def analyze(
        self,
        portfolio_return: float,
        factor_exposures: dict[str, float],
        factor_returns: dict[str, float],
    ) -> FactorAttributionResult:
        """Perform factor attribution analysis.

        Args:
            portfolio_return: Total portfolio return
            factor_exposures: Portfolio exposure to each factor
            factor_returns: Return of each factor

        Returns:
            FactorAttributionResult with factor contributions
        """
        # Calculate factor contributions
        factor_contributions = {}
        total_factor_return = 0.0

        for factor in factor_exposures:
            exposure = factor_exposures.get(factor, 0.0)
            ret = factor_returns.get(factor, 0.0)
            contribution = exposure * ret
            factor_contributions[factor] = contribution
            total_factor_return += contribution

        # Specific return (alpha)
        specific_return = portfolio_return - total_factor_return

        return FactorAttributionResult(
            total_return=portfolio_return,
            factor_returns=factor_contributions,
            specific_return=specific_return,
            factor_exposures=factor_exposures,
            metadata={
                "total_factor_return": total_factor_return,
            },
        )
