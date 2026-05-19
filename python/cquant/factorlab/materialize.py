"""cquant.factorlab.materialize — Persist factor values to DuckDB gold layer.

Reads from silver_prices_1d, runs FeaturePipeline, writes to gold_factor_values.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import polars as pl

from cquant.core.errors import FactorComputeError
from cquant.datahub.catalog import Catalog
from cquant.factorlab.factor import FactorRegistry
from cquant.factorlab.pipeline import FeaturePipeline, PipelineSpec

logger = logging.getLogger(__name__)


@dataclass
class FactorMaterializationSpec:
    """Configuration for a factor materialization run."""

    dataset_version: str
    factor_names: list[str]
    start_date: date
    end_date: date
    universe_id: str = ""


class FactorMaterializer:
    """Compute factors and persist results to gold_factor_values.

    Usage::

        materializer = FactorMaterializer(catalog, registry)
        fsv = materializer.run(FactorMaterializationSpec(
            dataset_version="...",
            factor_names=["ret_20d", "vol_20d"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ))
    """

    def __init__(self, catalog: Catalog, registry: FactorRegistry) -> None:
        self._catalog = catalog
        self._registry = registry
        self._pipeline = FeaturePipeline(registry)

    def run(self, spec: FactorMaterializationSpec) -> str:
        """Compute factors and write to gold_factor_values. Returns feature_set_version."""
        self._catalog.initialize()

        prices = self._load_prices(spec)
        if prices.is_empty():
            raise FactorComputeError(
                f"No price data in silver_prices_1d for date range "
                f"{spec.start_date} to {spec.end_date}"
            )

        pipeline_spec = PipelineSpec(
            factor_names=spec.factor_names,
            start_date=spec.start_date,
            end_date=spec.end_date,
            universe_id=spec.universe_id,
            dataset_version=spec.dataset_version,
        )
        feature_set = self._pipeline.run(prices, pipeline_spec)

        if feature_set.data.is_empty():
            raise FactorComputeError("Feature pipeline returned empty result")

        self._write_factor_values(feature_set)
        logger.info(
            "Materialized %d factors, %d rows → feature_set_version=%s",
            feature_set.factor_count, feature_set.row_count, feature_set.version_id,
        )
        return feature_set.version_id

    def _load_prices(self, spec: FactorMaterializationSpec) -> pl.DataFrame:
        """Load price data from silver_prices_1d."""
        # Load extra days before start_date for factor lookback windows
        from datetime import timedelta

        lookback_start = spec.start_date - timedelta(days=90)

        df = self._catalog.query(
            """
            SELECT asset_id, trade_date, open, high, low, close, volume, amount,
                   adj_factor, adj_close, is_suspended
            FROM silver_prices_1d
            WHERE trade_date >= ? AND trade_date <= ?
            ORDER BY asset_id, trade_date
            """,
            [lookback_start.isoformat(), spec.end_date.isoformat()],
        )
        if df.is_empty():
            return df

        # Cast trade_date to date type if needed
        if df["trade_date"].dtype == pl.Utf8:
            df = df.with_columns(pl.col("trade_date").str.to_date())
        elif df["trade_date"].dtype != pl.Date:
            df = df.with_columns(pl.col("trade_date").cast(pl.Date))

        return df

    def _write_factor_values(self, feature_set) -> None:
        """Unpivot feature_set.data and write to gold_factor_values."""
        id_cols = ["asset_id", "trade_date"]
        factor_names = [c for c in feature_set.data.columns if c not in id_cols]

        if not factor_names:
            raise FactorComputeError("No factor columns in feature set data")

        long_df = feature_set.data.unpivot(
            index=id_cols,
            on=factor_names,
            variable_name="factor_name",
            value_name="value",
        ).drop_nulls(["value"])

        if long_df.is_empty():
            logger.warning("All factor values are null after unpivot")
            return

        # Add metadata columns
        write_frame = long_df.with_columns(
            pl.lit(feature_set.version_id).alias("feature_set_version"),
        ).select(["feature_set_version", "factor_name", "trade_date", "asset_id", "value"])

        conn = self._catalog._get_conn()
        stage = "_factor_values_stage"
        conn.register(stage, write_frame.to_arrow())
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO gold_factor_values
                    (feature_set_version, factor_name, trade_date, asset_id, value)
                SELECT feature_set_version, factor_name, trade_date, asset_id, value
                FROM _factor_values_stage
                """
            )
        except Exception as exc:
            raise FactorComputeError(f"Failed to write gold_factor_values: {exc}") from exc
        finally:
            try:
                conn.unregister(stage)
            except Exception:
                pass
