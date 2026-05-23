"""Tests for VolParitySizer short support fix."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.vol_parity import VolParitySizer


def _signals(longs: list[str], shorts: list[str]) -> pl.DataFrame:
    rows = []
    for a in longs:
        rows.append({"asset_id": a, "signal_date": date(2025, 6, 1), "direction": "long", "strength": 1.0, "confidence": 1.0})
    for a in shorts:
        rows.append({"asset_id": a, "signal_date": date(2025, 6, 1), "direction": "short", "strength": 1.0, "confidence": 1.0})
    return pl.DataFrame(rows)


def _ctx(vol_map: dict[str, float]) -> SizingContext:
    vol_df = pl.DataFrame({"asset_id": list(vol_map.keys()), "volatility": list(vol_map.values())})
    return SizingContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal("1000000"),
        universe_ids=list(vol_map.keys()),
        volatility=vol_df,
    )


class TestVolParityLongOnly:
    def test_long_only_weights_sum_to_one(self) -> None:
        sizer = VolParitySizer(allow_short=False)
        signals = _signals(["A", "B", "C"], [])
        ctx = _ctx({"A": 0.20, "B": 0.30, "C": 0.25})
        result = sizer.target_weights(signals, ctx)
        assert sum(result.weights.values()) == pytest.approx(1.0, abs=1e-6)

    def test_long_only_all_weights_positive(self) -> None:
        sizer = VolParitySizer(allow_short=False)
        signals = _signals(["A", "B"], [])
        ctx = _ctx({"A": 0.20, "B": 0.30})
        result = sizer.target_weights(signals, ctx)
        for w in result.weights.values():
            assert w > 0


class TestVolParityWithShorts:
    def test_shorts_included_when_allow_short_true(self) -> None:
        sizer = VolParitySizer(allow_short=True)
        signals = _signals(["A", "B"], ["C", "D"])
        ctx = _ctx({"A": 0.20, "B": 0.30, "C": 0.25, "D": 0.15})
        result = sizer.target_weights(signals, ctx)
        assert set(result.weights.keys()) == {"A", "B", "C", "D"}

    def test_short_weights_are_negative(self) -> None:
        sizer = VolParitySizer(allow_short=True)
        signals = _signals(["A"], ["B"])
        ctx = _ctx({"A": 0.20, "B": 0.30})
        result = sizer.target_weights(signals, ctx)
        assert result.weights["A"] > 0
        assert result.weights["B"] < 0

    def test_long_and_short_exposure_balanced(self) -> None:
        sizer = VolParitySizer(allow_short=True)
        signals = _signals(["A", "B"], ["C", "D"])
        ctx = _ctx({"A": 0.20, "B": 0.30, "C": 0.25, "D": 0.15})
        result = sizer.target_weights(signals, ctx)
        long_total = sum(w for w in result.weights.values() if w > 0)
        short_total = sum(w for w in result.weights.values() if w < 0)
        assert long_total == pytest.approx(0.5, abs=0.01)
        assert short_total == pytest.approx(-0.5, abs=0.01)

    def test_shorts_ignored_when_allow_short_false(self) -> None:
        sizer = VolParitySizer(allow_short=False)
        signals = _signals(["A"], ["B"])
        ctx = _ctx({"A": 0.20, "B": 0.30})
        result = sizer.target_weights(signals, ctx)
        assert "B" not in result.weights
        assert "A" in result.weights
