"""Tests that FeaturePipeline uses DAGPipeline for topological factor execution."""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.factorlab.factor import Factor, FactorContext, FactorRegistry
from cquant.factorlab.pipeline import FeaturePipeline, PipelineSpec


class _CloseRatio(Factor):
    """close / open ratio — no dependencies."""
    @property
    def name(self) -> str:
        return "close_ratio"

    @property
    def dependencies(self) -> list[str]:
        return []

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (frame["close"] / frame["open"].clip(lower_bound=1e-9)).alias(self.name)


class _CloseRatioZscore(Factor):
    """Zscore of close_ratio — depends on close_ratio column in the frame."""
    @property
    def name(self) -> str:
        return "close_ratio_zscore"

    @property
    def dependencies(self) -> list[str]:
        return ["close_ratio"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        cr = frame["close_ratio"]
        std = cr.std() or 1.0
        return ((cr - cr.mean()) / std).alias(self.name)


def _make_prices() -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": ["A", "B", "C"] * 5,
        "trade_date": [date(2025, 1, i + 1) for i in range(5)] * 3,
        "open": [10.0, 20.0, 30.0] * 5,
        "close": [11.0, 18.0, 33.0] * 5,
    }).sort(["asset_id", "trade_date"])


def _make_registry(*factors: Factor) -> FactorRegistry:
    reg = FactorRegistry()
    for f in factors:
        reg.register(f)
    return reg


class TestPipelineDAGIntegration:
    def test_pipeline_computes_independent_factor(self) -> None:
        reg = _make_registry(_CloseRatio())
        pipeline = FeaturePipeline(reg)
        spec = PipelineSpec(
            factor_names=["close_ratio"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )
        result = pipeline.run(_make_prices(), spec)
        assert "close_ratio" in result.data.columns
        assert result.data["close_ratio"].drop_nulls().len() > 0

    def test_pipeline_executes_dependent_factor_in_order(self) -> None:
        """close_ratio_zscore depends on close_ratio; both requested in wrong order."""
        reg = _make_registry(_CloseRatioZscore(), _CloseRatio())
        pipeline = FeaturePipeline(reg)
        spec = PipelineSpec(
            factor_names=["close_ratio_zscore", "close_ratio"],  # zscore listed first
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )
        result = pipeline.run(_make_prices(), spec)
        assert "close_ratio" in result.data.columns
        assert "close_ratio_zscore" in result.data.columns
        assert result.data["close_ratio_zscore"].drop_nulls().len() > 0

    def test_pipeline_passes_extra_to_factor_context(self) -> None:
        """Extra data injected via run(extra=...) is available in FactorContext.extra."""
        extra_called: list[dict] = []

        class _ExtraAwareFactor(Factor):
            @property
            def name(self) -> str:
                return "extra_aware"
            def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
                extra_called.append(dict(ctx.extra))
                return pl.lit(1.0).alias(self.name)

        reg = _make_registry(_ExtraAwareFactor())
        pipeline = FeaturePipeline(reg)
        spec = PipelineSpec(
            factor_names=["extra_aware"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )
        pipeline.run(_make_prices(), spec, extra={"test_key": "test_value"})
        assert extra_called
        assert extra_called[0].get("test_key") == "test_value"

    def test_pipeline_handles_missing_factor_gracefully(self) -> None:
        """Factors not in registry produce null columns without crashing."""
        reg = _make_registry(_CloseRatio())
        pipeline = FeaturePipeline(reg)
        spec = PipelineSpec(
            factor_names=["close_ratio", "nonexistent_factor"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )
        result = pipeline.run(_make_prices(), spec)
        assert "close_ratio" in result.data.columns
        assert "nonexistent_factor" in result.data.columns
        assert result.data["nonexistent_factor"].null_count() == len(result.data)
