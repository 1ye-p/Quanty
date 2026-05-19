"""cquant.factorlab.pipeline — Feature pipeline: compute and materialize factor values."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date

import polars as pl

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

    Usage::

        registry = FactorRegistry()
        for f in BUILTIN_FACTORS:
            registry.register(f)

        pipeline = FeaturePipeline(registry)
        spec = PipelineSpec(
            factor_names=["ret_20d", "vol_20d", "zscore_close_60d"],
            start_date=date(2023, 1, 1),
            end_date=date(2026, 1, 1),
        )
        result = pipeline.run(prices_df, spec)
    """

    def __init__(self, registry: FactorRegistry) -> None:
        self._registry = registry

    def run(self, prices: pl.DataFrame, spec: PipelineSpec) -> FeatureSetVersion:
        """Compute all factors in *spec* over *prices* and return a FeatureSetVersion."""
        ctx = FactorContext(
            as_of_date=spec.end_date,
            frequency=spec.frequency,
            universe_id=spec.universe_id,
        )

        # Filter to the requested date range
        windowed = prices.filter(
            (pl.col("trade_date") >= spec.start_date)
            & (pl.col("trade_date") <= spec.end_date)
        )

        result = windowed.select(["asset_id", "trade_date"])
        failed: list[str] = []

        for factor_name in spec.factor_names:
            try:
                factor = self._registry.get(factor_name)
                series = factor.safe_compute(windowed, ctx)
                result = result.with_columns(series.alias(factor_name))
            except Exception as exc:
                logger.error("Factor %s failed: %s", factor_name, exc)
                failed.append(factor_name)
                result = result.with_columns(
                    pl.lit(None).cast(pl.Float64).alias(factor_name)
                )

        if failed:
            logger.warning("Factors with errors: %s", failed)

        version_id = str(uuid.uuid4())
        return FeatureSetVersion(
            version_id=version_id,
            spec=spec,
            data=result,
            factor_count=len(spec.factor_names),
            row_count=len(result),
        )
