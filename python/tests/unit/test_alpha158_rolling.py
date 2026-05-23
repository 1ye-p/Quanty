"""测试 Alpha158 Rolling 因子（16个）。"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.factorlab.factor import FactorContext
from cquant.factorlab.factors.alpha158_rolling import (
    ROC5, ROC10, ROC20, ROC30,
    MA5, MA10, MA20, MA30,
    STD5, STD10, STD20, STD30,
    MAX5, MAX20, MIN5, MIN20,
    ALPHA158_ROLLING_FACTORS,
)


def _make_frame(n: int = 40) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    p = 100.0
    rows = []
    for d in dates:
        p *= 1 + rng.normal(0.001, 0.01)
        rows.append({
            "asset_id": "A", "trade_date": d,
            "open": p * 0.99, "high": p * 1.02, "low": p * 0.97,
            "close": p, "volume": 1e6,
        })
    return pl.DataFrame(rows)


def _ctx() -> FactorContext:
    return FactorContext(as_of_date=date(2025, 2, 10))


class TestAlpha158RollingFactors:
    def test_roc5_returns_series(self) -> None:
        result = ROC5().compute(_make_frame(), _ctx())
        assert len(result) > 0

    def test_ma5_non_null_after_warmup(self) -> None:
        result = MA5().compute(_make_frame(40), _ctx())
        assert result.drop_nulls().len() > 0

    def test_std20_non_negative(self) -> None:
        result = STD20().compute(_make_frame(40), _ctx())
        non_null = result.drop_nulls().to_numpy()
        assert all(v >= 0 for v in non_null)

    def test_max20_ge_min20(self) -> None:
        frame = _make_frame(40)
        max_r = MAX20().compute(frame, _ctx())
        min_r = MIN20().compute(frame, _ctx())
        combined = pl.DataFrame({"max": max_r, "min": min_r}).drop_nulls()
        assert all(m >= n for m, n in zip(combined["max"].to_list(), combined["min"].to_list()))

    def test_all_factor_names_correct(self) -> None:
        expected = [
            "ROC5", "ROC10", "ROC20", "ROC30",
            "MA5", "MA10", "MA20", "MA30",
            "STD5", "STD10", "STD20", "STD30",
            "MAX5", "MAX20", "MIN5", "MIN20",
        ]
        factor_map = {f.name: f for f in ALPHA158_ROLLING_FACTORS}
        for name in expected:
            assert name in factor_map, f"缺少因子 {name}"

    def test_all_rolling_factors_have_alpha158_tag(self) -> None:
        for factor in ALPHA158_ROLLING_FACTORS:
            assert "alpha158" in factor.tags
