"""Integration tests for strategy + factor enhancement + GlobalStopPolicy.

Verifies end-to-end behaviour of:
1. MultiFactorStrategy missing_factor_strategy (fill_0 / fill_median / exclude)
2. GlobalStopPolicy in a backtest-like context
3. Factor templates loading and integration with MultiFactorStrategy
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.backtest_vector.strategies.multi_factor import MultiFactorStrategy
from cquant.backtest_vector.strategy import StrategyContext
from cquant.factorlab.factor_templates import get_template, list_templates
from cquant.riskguard.policies.global_stop import GlobalStopPolicy


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_features(
    trade_date: date,
    data: dict[str, list[float | None]],
    asset_ids: list[str] | None = None,
) -> pl.DataFrame:
    """Build a wide-format features DataFrame, supporting None values."""
    n = len(next(iter(data.values())))
    if asset_ids is None:
        asset_ids = [f"SSE:{i:06d}" for i in range(n)]
    rows: dict = {"asset_id": asset_ids, "trade_date": [trade_date] * n}
    rows.update(data)
    return pl.DataFrame(rows)


def _positions(*asset_ids: str) -> dict:
    """Return a minimal positions dict."""
    return {aid: {"quantity": 100} for aid in asset_ids}


# ── MultiFactorStrategy: missing_factor_strategy integration ──────────────────


class TestFillZeroIntegration:
    """fill_0 strategy in an integration-style scenario."""

    def test_fill_0_preserves_all_assets(self):
        """With fill_0, null factor values are replaced by 0 and all assets survive."""
        strat = MultiFactorStrategy(
            "int_fill0",
            factor_weights={"ret_20d": 1.0},
            top_n=10,
            missing_factor_strategy="fill_0",
        )
        d = date(2025, 6, 1)
        features = _make_features(
            d,
            {"ret_20d": [0.05, None, 0.03, None, 0.01]},
            asset_ids=[f"SSE:{i:06d}" for i in range(5)],
        )
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        # All 5 assets should appear — nulls filled with 0
        assert len(signals) == 5
        selected = set(signals["asset_id"].to_list())
        assert selected == {f"SSE:{i:06d}" for i in range(5)}

    def test_fill_0_with_entirely_missing_column(self):
        """fill_0 should add a missing factor column with zeros."""
        strat = MultiFactorStrategy(
            "int_fill0_col",
            factor_weights={"ret_20d": 1.0, "vol_20d": 0.5},
            top_n=5,
            missing_factor_strategy="fill_0",
        )
        d = date(2025, 6, 1)
        # vol_20d column is entirely absent
        features = _make_features(
            d,
            {"ret_20d": [0.01, 0.02, 0.03, 0.04, 0.05]},
        )
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        assert len(signals) == 5
        # Scores should vary because ret_20d contributes
        strengths = signals.sort("strength")["strength"].to_list()
        assert strengths[-1] > strengths[0]


class TestFillMedianIntegration:
    """fill_median strategy in an integration-style scenario."""

    def test_fill_median_preserves_all_assets(self):
        """With fill_median, nulls are replaced by the column median."""
        strat = MultiFactorStrategy(
            "int_fillmedian",
            factor_weights={"ret_20d": 1.0},
            top_n=10,
            missing_factor_strategy="fill_median",
        )
        d = date(2025, 6, 1)
        # Median of [0.01, 0.03, 0.05] = 0.03
        features = _make_features(
            d,
            {"ret_20d": [0.01, None, 0.03, None, 0.05]},
            asset_ids=[f"SSE:{i:06d}" for i in range(5)],
        )
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        # All 5 assets should appear
        assert len(signals) == 5

    def test_fill_median_ranking_reflects_filled_values(self):
        """Assets with null values filled by median should rank accordingly."""
        strat = MultiFactorStrategy(
            "int_fillmedian_rank",
            factor_weights={"ret_20d": 1.0},
            top_n=5,
            missing_factor_strategy="fill_median",
        )
        d = date(2025, 6, 1)
        # Median of [0.01, 0.05] = 0.03; nulls become 0.03
        features = _make_features(
            d,
            {"ret_20d": [0.01, None, 0.05, None, 0.01]},
            asset_ids=["A", "B", "C", "D", "E"],
        )
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        # C (0.05) should have highest strength, then B/D (0.03 median), then A/E (0.01)
        strengths = dict(zip(signals["asset_id"].to_list(), signals["strength"].to_list()))
        assert strengths["C"] > strengths["B"]
        assert strengths["C"] > strengths["D"]
        assert strengths["B"] == pytest.approx(strengths["D"])


class TestExcludeIntegration:
    """exclude strategy in an integration-style scenario."""

    def test_exclude_drops_null_assets(self):
        """With exclude, assets having null factor values are dropped."""
        strat = MultiFactorStrategy(
            "int_exclude",
            factor_weights={"ret_20d": 1.0},
            top_n=10,
            missing_factor_strategy="exclude",
        )
        d = date(2025, 6, 1)
        features = _make_features(
            d,
            {"ret_20d": [0.01, None, 0.03, None, 0.05]},
            asset_ids=[f"SSE:{i:06d}" for i in range(5)],
        )
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        # Only 3 non-null assets survive
        assert len(signals) == 3
        selected = set(signals["asset_id"].to_list())
        assert selected == {"SSE:000000", "SSE:000002", "SSE:000004"}

    def test_exclude_all_null_returns_empty(self):
        """If all factor values are null, exclude yields empty signals."""
        strat = MultiFactorStrategy(
            "int_exclude_all",
            factor_weights={"ret_20d": 1.0},
            top_n=10,
            missing_factor_strategy="exclude",
        )
        d = date(2025, 6, 1)
        features = _make_features(
            d,
            {"ret_20d": [None, None, None]},
            asset_ids=["A", "B", "C"],
        )
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        assert len(signals) == 0


# ── GlobalStopPolicy: backtest-context integration ────────────────────────────


class TestGlobalStopPolicyIntegration:
    """GlobalStopPolicy used in a backtest-like scenario."""

    def test_stop_loss_triggers_in_portfolio_context(self):
        """Stop-loss triggers for a losing position in a multi-asset portfolio."""
        policy = GlobalStopPolicy(stop_loss_pct=-0.05)
        exits = policy.check_exits(
            positions=_positions("SH600000", "SZ000001", "SH601318"),
            current_prices={"SH600000": 9.0, "SZ000001": 10.5, "SH601318": 10.2},
            entry_prices={"SH600000": 10.0, "SZ000001": 10.0, "SH601318": 10.0},
        )
        assert len(exits) == 1
        assert exits[0].asset_id == "SH600000"
        assert "global_stop_loss" in exits[0].reason
        assert exits[0].urgency == "high"

    def test_take_profit_triggers_in_portfolio_context(self):
        """Take-profit triggers for a winning position."""
        policy = GlobalStopPolicy(take_profit_pct=0.20)
        exits = policy.check_exits(
            positions=_positions("SH600000", "SZ000001"),
            current_prices={"SH600000": 12.5, "SZ000001": 10.5},
            entry_prices={"SH600000": 10.0, "SZ000001": 10.0},
        )
        assert len(exits) == 1
        assert exits[0].asset_id == "SH600000"
        assert "global_take_profit" in exits[0].reason

    def test_combined_policy_mixed_positions(self):
        """Both legs active: one stop-loss, one take-profit, one neutral."""
        policy = GlobalStopPolicy(stop_loss_pct=-0.05, take_profit_pct=0.20)
        exits = policy.check_exits(
            positions=_positions("SH600000", "SZ000001", "SH601318"),
            current_prices={
                "SH600000": 9.0,   # -10% -> stop loss
                "SZ000001": 10.5,  # +5%  -> neither
                "SH601318": 13.0,  # +30% -> take profit
            },
            entry_prices={
                "SH600000": 10.0,
                "SZ000001": 10.0,
                "SH601318": 10.0,
            },
        )
        assert len(exits) == 2
        reasons = {e.asset_id: e.reason for e in exits}
        assert "SH600000" in reasons
        assert "SH601318" in reasons
        assert "global_stop_loss" in reasons["SH600000"]
        assert "global_take_profit" in reasons["SH601318"]

    def test_no_positions_returns_empty(self):
        """Empty positions dict yields no exits."""
        policy = GlobalStopPolicy(stop_loss_pct=-0.05, take_profit_pct=0.20)
        exits = policy.check_exits(
            positions={},
            current_prices={"SH600000": 9.0},
            entry_prices={"SH600000": 10.0},
        )
        assert len(exits) == 0


# ── Factor templates integration ──────────────────────────────────────────────


class TestFactorTemplateIntegration:
    """Factor templates loaded and used with MultiFactorStrategy."""

    def test_all_templates_load(self):
        """list_templates returns all 4 presets."""
        templates = list_templates()
        assert len(templates) == 4
        ids = {t["template_id"] for t in templates}
        assert ids == {"value", "growth", "momentum", "low_vol"}

    def test_template_to_strategy(self):
        """A template's factor_weights can drive MultiFactorStrategy."""
        tpl = get_template("value")
        assert tpl is not None

        strat = MultiFactorStrategy(
            "from_template",
            factor_weights=tpl["factor_weights"],
            top_n=tpl["top_n"],
        )
        d = date(2025, 6, 1)
        # Build features with all factors the value template needs
        n = 20
        features = pl.DataFrame({
            "asset_id": [f"SSE:{i:06d}" for i in range(n)],
            "trade_date": [d] * n,
            "pe_ttm": [10.0 + i for i in range(n)],
            "pb": [1.0 + i * 0.1 for i in range(n)],
            "roe_ttm": [0.15 + i * 0.005 for i in range(n)],
            "div_yield": [0.02 + i * 0.001 for i in range(n)],
        })
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        assert len(signals) == tpl["top_n"]
        for col in ("asset_id", "signal_date", "direction", "strength", "confidence"):
            assert col in signals.columns

    def test_template_with_fill_0_for_missing_factors(self):
        """Template strategy works even when some factors are absent (filled with 0)."""
        tpl = get_template("momentum")
        assert tpl is not None

        strat = MultiFactorStrategy(
            "tpl_momentum",
            factor_weights=tpl["factor_weights"],
            top_n=tpl["top_n"],
            missing_factor_strategy="fill_0",
        )
        d = date(2025, 6, 1)
        # Only provide ret_60d and ret_20d; vol_20d and turnover_20d are missing
        n = 15
        features = pl.DataFrame({
            "asset_id": [f"SSE:{i:06d}" for i in range(n)],
            "trade_date": [d] * n,
            "ret_60d": [0.05 + i * 0.01 for i in range(n)],
            "ret_20d": [0.02 + i * 0.005 for i in range(n)],
        })
        ctx = StrategyContext(as_of_date=d, universe_id="cn_all", features=features)
        signals = strat.generate_signals(ctx)

        # Should still produce signals (missing factors filled with 0)
        assert len(signals) == tpl["top_n"]

    def test_get_template_none_for_invalid(self):
        """get_template returns None for unknown ids."""
        assert get_template("invalid_id") is None
        assert get_template("") is None
