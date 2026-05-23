"""测试 QlibEvaluator（IC/risk_analysis 封装）。"""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from cquant.qlib_bridge.evaluator import QlibEvaluator


class TestQlibEvaluatorRiskAnalysis:
    def test_returns_dict_with_required_keys(self) -> None:
        rng = np.random.default_rng(42)
        returns = pl.Series("r", rng.normal(0.001, 0.01, 252))
        ev = QlibEvaluator()
        result = ev.risk_analysis(returns)
        assert isinstance(result, dict)
        for key in ["annualized_return", "information_ratio", "max_drawdown", "mean", "std"]:
            assert key in result, f"缺少键 '{key}'"

    def test_positive_drift_has_positive_ir(self) -> None:
        returns = pl.Series("r", [0.002] * 252)
        ev = QlibEvaluator()
        result = ev.risk_analysis(returns)
        assert result["information_ratio"] > 0

    def test_max_drawdown_is_non_positive(self) -> None:
        rng = np.random.default_rng(42)
        returns = pl.Series("r", rng.normal(0.0, 0.01, 252))
        ev = QlibEvaluator()
        result = ev.risk_analysis(returns)
        assert result["max_drawdown"] <= 0

    def test_empty_returns_returns_empty_dict(self) -> None:
        ev = QlibEvaluator()
        result = ev.risk_analysis(pl.Series("r", []))
        assert result == {}


class TestQlibEvaluatorICAnalysis:
    def test_ic_analysis_returns_dict(self) -> None:
        rng = np.random.default_rng(42)
        factor = pl.Series("f", rng.normal(0, 1, 100))
        returns = factor * 0.1 + pl.Series("r", rng.normal(0, 0.05, 100))
        ev = QlibEvaluator()
        result = ev.ic_analysis(factor, returns)
        assert "ic" in result
        assert "p_value" in result

    def test_perfect_correlation_gives_ic_one(self) -> None:
        factor = pl.Series("f", [float(i) for i in range(50)])
        returns = pl.Series("r", [float(i) * 2 for i in range(50)])
        ev = QlibEvaluator()
        result = ev.ic_analysis(factor, returns)
        assert result["ic"] == pytest.approx(1.0, abs=0.01)
