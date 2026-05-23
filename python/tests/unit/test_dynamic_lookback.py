"""Tests for dynamic lookback window in FactorMaterializer."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import polars as pl
import pytest

from cquant.factorlab.factor import Factor, FactorRegistry
from cquant.factorlab.factors.momentum import Return240d, Momentum12_1
from cquant.factorlab.factors.volatility import Vol120d, Vol20d


class TestLookbackDaysProperty:
    def test_default_lookback_is_at_least_90(self) -> None:
        f = Vol20d()
        assert hasattr(f, "lookback_days")
        assert f.lookback_days >= 90

    def test_return_240d_lookback_exceeds_370(self) -> None:
        f = Return240d()
        assert f.lookback_days > 370

    def test_momentum_12_1_lookback_exceeds_390(self) -> None:
        f = Momentum12_1()
        assert f.lookback_days > 390

    def test_vol_120d_lookback_exceeds_185(self) -> None:
        f = Vol120d()
        assert f.lookback_days > 185


class TestMaterializerDynamicLookback:
    def test_materializer_uses_max_lookback(self) -> None:
        from cquant.factorlab.materialize import FactorMaterializer, FactorMaterializationSpec

        reg = FactorRegistry()
        reg.register(Return240d())

        mock_catalog = MagicMock()
        mock_catalog.query.return_value = pl.DataFrame()

        materializer = FactorMaterializer(mock_catalog, reg)
        spec = FactorMaterializationSpec(
            dataset_version="v1",
            factor_names=["ret_240d"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )

        try:
            materializer.run(spec)
        except Exception:
            pass

        assert mock_catalog.query.called
        query_params = mock_catalog.query.call_args[0][1]
        lookback_start_str = query_params[0]
        from datetime import date as dt_date
        lookback_start = dt_date.fromisoformat(lookback_start_str)
        delta = (date(2025, 1, 1) - lookback_start).days
        assert delta > 370, f"Expected lookback > 370 days but got {delta}"
