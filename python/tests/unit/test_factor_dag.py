"""Tests for DAG-based factor execution."""
from datetime import date

import polars as pl
import pytest

from cquant.factorlab.dag import DAGPipeline
from cquant.factorlab.factor import Factor, FactorContext


class PriceRatio(Factor):
    """Composite factor: close / open ratio."""

    @property
    def name(self) -> str:
        return "price_ratio"

    @property
    def dependencies(self) -> list[str]:
        return []

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (frame["close"] / frame["open"].clip(lower_bound=1e-9)).alias(self.name)


class PriceRatioZscore(Factor):
    """Depends on price_ratio."""

    @property
    def name(self) -> str:
        return "price_ratio_zscore"

    @property
    def dependencies(self) -> list[str]:
        return ["price_ratio"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        pr = frame["price_ratio"]
        return ((pr - pr.mean()) / pr.std().clip(lower_bound=1e-9)).alias(self.name)


class CyclicA(Factor):
    """For testing cycle detection."""

    @property
    def name(self) -> str:
        return "cyclic_a"

    @property
    def dependencies(self) -> list[str]:
        return ["cyclic_b"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return pl.lit(1.0).alias(self.name)


class CyclicB(Factor):
    @property
    def name(self) -> str:
        return "cyclic_b"

    @property
    def dependencies(self) -> list[str]:
        return ["cyclic_a"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return pl.lit(1.0).alias(self.name)


def _make_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "asset_id": ["A", "B", "C"],
            "trade_date": [date(2025, 6, 1)] * 3,
            "open": [10.0, 20.0, 30.0],
            "close": [11.0, 19.0, 33.0],
        }
    )


class TestDAGPipeline:
    def test_topological_order(self):
        pipeline = DAGPipeline([PriceRatioZscore(), PriceRatio()])
        order = pipeline.execution_order()
        # price_ratio must come before price_ratio_zscore
        assert order.index("price_ratio") < order.index("price_ratio_zscore")

    def test_cycle_detection(self):
        with pytest.raises(ValueError, match="cycle"):
            DAGPipeline([CyclicA(), CyclicB()])

    def test_execution(self):
        pipeline = DAGPipeline([PriceRatioZscore(), PriceRatio()])
        frame = _make_frame()
        ctx = FactorContext(as_of_date=date(2025, 6, 1))
        result = pipeline.run(frame, ctx)
        assert "price_ratio" in result.columns
        assert "price_ratio_zscore" in result.columns
        assert len(result) == 3

    def test_missing_dependency_skipped(self):
        """Factor with missing dependency should be skipped with a warning."""

        class DependsOnMissing(Factor):
            @property
            def name(self) -> str:
                return "orphan"

            @property
            def dependencies(self) -> list[str]:
                return ["nonexistent"]

            def compute(self, frame, ctx):
                return pl.lit(1.0).alias(self.name)

        pipeline = DAGPipeline([DependsOnMissing()])
        frame = _make_frame()
        ctx = FactorContext(as_of_date=date(2025, 6, 1))
        result = pipeline.run(frame, ctx)
        # orphan should be skipped since nonexistent is not available
        assert "orphan" not in result.columns or result["orphan"].null_count() == len(result)
