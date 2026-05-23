"""Tests for Winsorize return clipping in silver layer and return computations."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest


class TestForwardReturnLabelsClip:
    """forward_return_labels() clips extreme forward returns to [-0.5, 0.5]."""

    def _make_prices(self, closes: list[float]) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": ["A"] * len(closes),
            "trade_date": [date(2026, 1, i + 1) for i in range(len(closes))],
            "close": closes,
        })

    def test_normal_returns_unchanged(self) -> None:
        from cquant.ml_lab.labels import forward_return_labels
        prices = self._make_prices([100.0, 105.0, 110.25])
        result = forward_return_labels(prices, periods=1)
        ret = result["ret_1d"].drop_nulls().to_list()
        assert abs(ret[0] - 0.05) < 1e-6

    def test_extreme_positive_return_clipped_to_50pct(self) -> None:
        from cquant.ml_lab.labels import forward_return_labels
        prices = self._make_prices([100.0, 300.0, 100.0])
        result = forward_return_labels(prices, periods=1)
        ret = result["ret_1d"].drop_nulls().to_list()
        assert ret[0] == pytest.approx(0.5, abs=1e-6), f"Expected 0.5, got {ret[0]}"

    def test_extreme_negative_return_clipped_to_minus_50pct(self) -> None:
        from cquant.ml_lab.labels import forward_return_labels
        prices = self._make_prices([100.0, 20.0, 100.0])
        result = forward_return_labels(prices, periods=1)
        ret = result["ret_1d"].drop_nulls().to_list()
        assert ret[0] == pytest.approx(-0.5, abs=1e-6), f"Expected -0.5, got {ret[0]}"

    def test_null_labels_not_affected(self) -> None:
        from cquant.ml_lab.labels import forward_return_labels
        prices = self._make_prices([100.0, 105.0, 110.0])
        result = forward_return_labels(prices, periods=1)
        assert result["ret_1d"][-1] is None


class TestMomentumFactorClip:
    """_ReturnNd.compute() clips extreme momentum returns."""

    def _make_frame(self, closes: list[float]) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": ["A"] * len(closes),
            "trade_date": [date(2026, 1, i + 1) for i in range(len(closes))],
            "close": closes,
        })

    def test_normal_1d_return_unchanged(self) -> None:
        from cquant.factorlab.factors.momentum import Return1d
        from cquant.factorlab.factor import FactorContext
        frame = self._make_frame([100.0, 105.0])
        ctx = FactorContext(as_of_date=date(2026, 1, 2))
        result = Return1d().compute(frame, ctx)
        non_null = result.drop_nulls()
        assert abs(float(non_null[0]) - 0.05) < 1e-6

    def test_extreme_1d_return_clipped(self) -> None:
        from cquant.factorlab.factors.momentum import Return1d
        from cquant.factorlab.factor import FactorContext
        frame = self._make_frame([100.0, 300.0])
        ctx = FactorContext(as_of_date=date(2026, 1, 2))
        result = Return1d().compute(frame, ctx)
        non_null = result.drop_nulls()
        assert float(non_null[0]) == pytest.approx(0.5, abs=1e-6)

    def test_extreme_negative_return_clipped(self) -> None:
        from cquant.factorlab.factors.momentum import Return1d
        from cquant.factorlab.factor import FactorContext
        frame = self._make_frame([100.0, 10.0])
        ctx = FactorContext(as_of_date=date(2026, 1, 2))
        result = Return1d().compute(frame, ctx)
        non_null = result.drop_nulls()
        assert float(non_null[0]) == pytest.approx(-0.5, abs=1e-6)


class TestSilverLayerWinsorize:
    """SilverNormalizer._clean_data_quality() removes rows with >±50% daily adj_close change."""

    def _make_silver_df(self, adj_closes: list[float]) -> pl.DataFrame:
        n = len(adj_closes)
        return pl.DataFrame({
            "asset_id": ["SSE:600036"] * n,
            "trade_date": [date(2026, 1, i + 1) for i in range(n)],
            "close": adj_closes,
            "adj_close": adj_closes,
            "open": adj_closes,
            "high": adj_closes,
            "low": adj_closes,
            "volume": [1_000_000] * n,
        })

    def test_normal_prices_unchanged(self) -> None:
        from cquant.datahub.pipelines.silver import SilverNormalizer
        normalizer = SilverNormalizer()
        df = self._make_silver_df([100.0, 102.0, 104.0, 106.0])
        result = normalizer._clean_data_quality(df)
        assert len(result) == len(df)

    def test_extreme_daily_jump_removed(self) -> None:
        from cquant.datahub.pipelines.silver import SilverNormalizer
        normalizer = SilverNormalizer()
        df = self._make_silver_df([100.0, 102.0, 306.0, 103.0])
        result = normalizer._clean_data_quality(df)
        assert 306.0 not in result["adj_close"].to_list()

    def test_first_row_per_asset_not_removed(self) -> None:
        from cquant.datahub.pipelines.silver import SilverNormalizer
        normalizer = SilverNormalizer()
        df = self._make_silver_df([500.0, 102.0, 103.0])
        result = normalizer._clean_data_quality(df)
        assert 500.0 in result["adj_close"].to_list()
