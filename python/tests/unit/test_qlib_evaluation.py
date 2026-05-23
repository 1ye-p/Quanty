"""测试 FactorEvaluator.qlib_risk_analysis() 方法。"""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from cquant.factorlab.evaluation import FactorEvaluator


class TestQlibRiskAnalysis:
    def test_returns_dict_with_required_keys(self) -> None:
        rng = np.random.default_rng(42)
        returns = pl.Series("r", rng.normal(0.001, 0.01, 252))
        ev = FactorEvaluator(factor_col="f", return_col="r")
        result = ev.qlib_risk_analysis(returns)
        assert isinstance(result, dict)
        assert "annualized_return" in result
        assert "information_ratio" in result
        assert "max_drawdown" in result

    def test_positive_drift_has_positive_ir(self) -> None:
        returns = pl.Series("r", [0.002] * 252)
        ev = FactorEvaluator(factor_col="f", return_col="r")
        result = ev.qlib_risk_analysis(returns)
        assert result is not None
        assert result["information_ratio"] > 0

    def test_empty_returns_returns_none(self) -> None:
        ev = FactorEvaluator(factor_col="f", return_col="r")
        result = ev.qlib_risk_analysis(pl.Series("r", []))
        assert result is None

    def test_max_drawdown_is_non_positive(self) -> None:
        rng = np.random.default_rng(42)
        returns = pl.Series("r", rng.normal(0.0, 0.01, 252))
        ev = FactorEvaluator(factor_col="f", return_col="r")
        result = ev.qlib_risk_analysis(returns)
        if result is not None:
            assert result["max_drawdown"] <= 0
