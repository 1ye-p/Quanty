"""cquant.factorlab.pipeline — Feature pipeline: compute and materialize factor values."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import polars as pl

from cquant.factorlab.dag import DAGPipeline
from cquant.factorlab.factor import Factor, FactorContext, FactorRegistry

logger = logging.getLogger(__name__)


@dataclass
class PipelineSpec:
    """Configuration for a feature computation run."""

    factor_names: list[str]
    start_date: date
    end_date: date
    universe_id: str = ""
    frequency: str = "1d"
    dataset_version: str = ""


@dataclass
class FeatureSetVersion:
    """Result of a completed feature pipeline run."""

    version_id: str
    spec: PipelineSpec
    data: pl.DataFrame   # Columns: [asset_id, trade_date, {factor_name}, ...]
    factor_count: int
    row_count: int


class FeaturePipeline:
    """Executes a set of factors over a price DataFrame and returns tidy output.

    Uses DAGPipeline internally so factors that declare ``dependencies`` are
    automatically executed after their required factors are computed.
    """

    def __init__(self, registry: FactorRegistry) -> None:
        self._registry = registry

    def run(
        self,
        prices: pl.DataFrame,
        spec: PipelineSpec,
        extra: dict[str, Any] | None = None,
    ) -> FeatureSetVersion:
        """Compute all factors in *spec* over *prices* and return a FeatureSetVersion.

        Parameters
        ----------
        prices:
            Silver OHLCV DataFrame.
        spec:
            Which factors to compute and over what date range.
        extra:
            Optional dict injected into ``FactorContext.extra`` (e.g. ``{"fundamentals": df}``).
        """
        ctx = FactorContext(
            as_of_date=spec.end_date,
            frequency=spec.frequency,
            universe_id=spec.universe_id,
            extra=extra or {},
        )

        # Filter to the requested date range
        windowed = prices.filter(
            (pl.col("trade_date") >= spec.start_date)
            & (pl.col("trade_date") <= spec.end_date)
        )

        # Resolve factor instances; track any not found in registry
        factors: list[Factor] = []
        missing: list[str] = []
        for name in spec.factor_names:
            try:
                factors.append(self._registry.get(name))
            except KeyError:
                logger.warning("Factor '%s' not in registry — will produce null column", name)
                missing.append(name)

        # Execute via DAGPipeline (handles dependency ordering)
        if factors:
            dag = DAGPipeline(factors, strict=False)
            enriched = dag.run(windowed, ctx)
        else:
            enriched = windowed

        # Build result: keep id cols + requested factor columns only
        id_cols = ["asset_id", "trade_date"]
        available_factors = [n for n in spec.factor_names if n in enriched.columns]
        result = enriched.select(id_cols + available_factors)

        # Add null columns for factors missing from registry
        for name in missing:
            if name not in result.columns:
                result = result.with_columns(pl.lit(None).cast(pl.Float64).alias(name))

        version_id = str(uuid.uuid4())
        return FeatureSetVersion(
            version_id=version_id,
            spec=spec,
            data=result,
            factor_count=len(spec.factor_names),
            row_count=len(result),
        )
