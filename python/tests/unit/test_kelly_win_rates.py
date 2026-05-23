"""Tests for KellySizer using historical win rates from ctx.extra."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.kelly import KellySizer


def _signals(assets: list[str], confidence: float = 0.55) -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": assets,
        "signal_date": [date(2025, 6, 1)] * len(assets),
        "direction": ["long"] * len(assets),
        "strength": [1.0] * len(assets),
        "confidence": [confidence] * len(assets),
    })


def _ctx(win_rates: dict[str, float] | None = None) -> SizingContext:
    return SizingContext(
        as_of_date=date(2025, 6, 1),
        portfolio_nav=Decimal("1000000"),
        universe_ids=["A", "B"],
        extra={"win_rates": win_rates} if win_rates else {},
    )


class TestKellyWithHistoricalWinRates:
    def test_uses_win_rate_from_ctx_extra(self) -> None:
        sizer = KellySizer()
        assets = ["SSE:600036"]
        # Confidence = 0.5 (neutral), but historical win rate = 0.75 (strong)
        signals = _signals(assets, confidence=0.50)
        ctx_with_rates = _ctx(win_rates={"SSE:600036": 0.75})
        ctx_without_rates = _ctx()
        result_with = sizer.target_weights(signals, ctx_with_rates)
        result_without = sizer.target_weights(signals, ctx_without_rates)
        w_with = result_with.weights.get("SSE:600036", 0.0)
        w_without = result_without.weights.get("SSE:600036", 0.0)
        assert w_with > w_without

    def test_falls_back_to_confidence_when_no_win_rates(self) -> None:
        sizer = KellySizer()
        signals = _signals(["A"], confidence=0.7)
        ctx = _ctx()
        result = sizer.target_weights(signals, ctx)
        assert "A" in result.weights
        assert result.weights["A"] > 0

    def test_partial_win_rates_fallback(self) -> None:
        sizer = KellySizer()
        signals = _signals(["A", "B"], confidence=0.5)
        ctx = _ctx(win_rates={"A": 0.80})
        result = sizer.target_weights(signals, ctx)
        assert "A" in result.weights
        assert "B" in result.weights

    def test_win_rate_is_clipped_to_valid_range(self) -> None:
        sizer = KellySizer()
        signals = _signals(["A"])
        ctx = _ctx(win_rates={"A": 1.5})  # invalid: > 1.0
        result = sizer.target_weights(signals, ctx)
        assert result.weights.get("A", 0.0) <= sizer._max_position_pct
