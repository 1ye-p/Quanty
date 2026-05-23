"""Integration tests for Vibe-Trading qlib158 alpha factors.

Skips all tests if VIBE_AVAILABLE is False.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from cquant.vibe_bridge._compat import VIBE_AVAILABLE

pytestmark = pytest.mark.skipif(not VIBE_AVAILABLE, reason="Vibe-Trading not installed")


def _make_price_frame(n_days: int = 60) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n_days)]
    assets = ["SSE:000001", "SSE:600036", "SSE:600519"]
    rows = []
    for d in dates:
        for a in assets:
            p = 50.0 + float(rng.normal(0, 1))
            rows.append({
                "asset_id": a, "trade_date": d,
                "open": p, "high": p + 0.5, "low": p - 0.5, "close": p,
                "volume": float(rng.integers(500_000, 2_000_000)),
                "amount": p * float(rng.integers(500_000, 2_000_000)),
            })
    return pl.DataFrame(rows)


@pytest.fixture(scope="module")
def price_frame():
    return _make_price_frame(60)


@pytest.fixture(scope="module")
def ctx():
    from cquant.factorlab.factor import FactorContext
    return FactorContext(as_of_date=date(2024, 2, 29))


@pytest.fixture(scope="module")
def qlib158_sample():
    from cquant.vibe_bridge.alpha_zoo import load_zoo
    return load_zoo("qlib158")[:10]


class TestQlib158Sample:
    def test_load_returns_factors(self, qlib158_sample) -> None:
        assert len(qlib158_sample) > 0

    def test_all_have_qlib158_tag(self, qlib158_sample) -> None:
        for f in qlib158_sample:
            assert "qlib158" in f.tags

    def test_factor_names_unique(self, qlib158_sample) -> None:
        names = [f.name for f in qlib158_sample]
        assert len(names) == len(set(names))

    def test_total_qlib158_count_is_154(self) -> None:
        from cquant.vibe_bridge.alpha_zoo import load_zoo
        factors = load_zoo("qlib158")
        assert len(factors) == 154, f"Expected 154, got {len(factors)}"

    @pytest.mark.parametrize("idx", range(5))
    def test_factor_compute_returns_series(self, qlib158_sample, price_frame, ctx, idx) -> None:
        if idx >= len(qlib158_sample):
            pytest.skip("Not enough factors")
        factor = qlib158_sample[idx]
        result = factor.compute(price_frame, ctx)
        assert isinstance(result, pl.Series)
        assert len(result) == len(price_frame)

    def test_first_factor_has_some_non_null_values(self, qlib158_sample, price_frame, ctx) -> None:
        result = qlib158_sample[0].compute(price_frame, ctx)
        assert result.drop_nulls().len() > 0

    def test_qlib158_registered_in_builtin_factors(self) -> None:
        from cquant.factorlab.factors import BUILTIN_FACTORS
        qlib158 = [f for f in BUILTIN_FACTORS if "qlib158" in getattr(f, "tags", [])]
        assert len(qlib158) == 154, f"Expected 154 in BUILTIN_FACTORS, got {len(qlib158)}"
