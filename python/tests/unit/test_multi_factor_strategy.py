"""Tests for MultiFactorStrategy."""

from datetime import date

import polars as pl
import pytest

from cquant.backtest_vector.strategies.multi_factor import MultiFactorStrategy
from cquant.backtest_vector.strategy import StrategyContext


def _make_features(trade_date: date, data: dict[str, list[float]], asset_ids: list[str] | None = None) -> pl.DataFrame:
    """Build a wide-format features DataFrame."""
    n = len(next(iter(data.values())))
    if asset_ids is None:
        asset_ids = [f"SSE:{i:06d}" for i in range(n)]
    rows = {"asset_id": asset_ids, "trade_date": [trade_date] * n}
    rows.update(data)
    return pl.DataFrame(rows)


class TestMultiFactorStrategy:
    def test_returns_signal_frame(self):
        """Signal frame has the expected columns."""
        strat = MultiFactorStrategy("mf_test", factor_weights={"ret_20d": 1.0}, top_n=3)
        d = date(2025, 6, 1)
        features = _make_features(d, {"ret_20d": [0.01, 0.02, 0.03, 0.04, 0.05]})
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        assert isinstance(signals, pl.DataFrame)
        for col in ("asset_id", "signal_date", "direction", "strength", "confidence"):
            assert col in signals.columns, f"Missing column: {col}"

    def test_top_n_limits_output(self):
        """20 assets with top_n=5 yields exactly 5 signals."""
        strat = MultiFactorStrategy("mf_top5", factor_weights={"ret_20d": 1.0}, top_n=5)
        d = date(2025, 6, 1)
        features = _make_features(d, {"ret_20d": list(range(20))})
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        assert len(signals) == 5

    def test_empty_features_returns_empty(self):
        """None features produces an empty signal frame."""
        strat = MultiFactorStrategy("mf_empty", factor_weights={"ret_20d": 1.0}, top_n=10)
        d = date(2025, 6, 1)
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=None)
        signals = strat.generate_signals(ctx)

        assert len(signals) == 0

    def test_missing_factor_handled(self):
        """A weight referencing a nonexistent factor is silently ignored."""
        strat = MultiFactorStrategy(
            "mf_missing",
            factor_weights={"ret_20d": 1.0, "nonexistent": 0.5},
            top_n=3,
        )
        d = date(2025, 6, 1)
        features = _make_features(d, {"ret_20d": [1.0, 2.0, 3.0, 4.0, 5.0]})
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        assert len(signals) == 3  # still works with the available factor

    def test_negative_weight_inverts_ranking(self):
        """Negative weight on ret_20d selects the lowest-return assets."""
        strat = MultiFactorStrategy("mf_neg", factor_weights={"ret_20d": -1.0}, top_n=2)
        d = date(2025, 6, 1)
        features = _make_features(
            d,
            {"ret_20d": [0.01, 0.05, 0.03, 0.02, 0.04]},
            asset_ids=["SSE:00000", "SSE:00001", "SSE:00002", "SSE:00003", "SSE:00004"],
        )
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        selected_ids = signals["asset_id"].to_list()
        # Lowest return is 0.01 (SSE:00000) and 0.02 (SSE:00003)
        assert "SSE:00000" in selected_ids
        assert "SSE:00003" in selected_ids
