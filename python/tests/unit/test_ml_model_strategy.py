"""Tests for MLModelStrategy — reads gold_predictions and generates signals."""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.backtest_vector.strategies.ml_strategy import MLModelStrategy
from cquant.backtest_vector.strategy import StrategyContext
from cquant.datahub.catalog import Catalog

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


@pytest.fixture()
def catalog_with_predictions(tmp_path):
    db_file = tmp_path / "test.duckdb"
    cat = Catalog(db_path=db_file, repo_root=_REPO_ROOT)
    cat.initialize()

    cat._get_conn().execute("""
        INSERT INTO gold_predictions
            (model_version, trade_date, asset_id, prediction, horizon, label_name)
        VALUES
            ('lgbm_v1', '2025-06-01', 'SSE:600036', 0.035, '5d', 'ret_5d'),
            ('lgbm_v1', '2025-06-01', 'SSE:000001', 0.012, '5d', 'ret_5d'),
            ('lgbm_v1', '2025-06-01', 'SSE:600519', 0.028, '5d', 'ret_5d'),
            ('lgbm_v1', '2025-06-01', 'SSE:000858', -0.005, '5d', 'ret_5d'),
            ('lgbm_v1', '2025-06-01', 'SSE:002594', 0.019, '5d', 'ret_5d')
    """)
    return cat


def _ctx(as_of_date: date, catalog: Catalog | None = None) -> StrategyContext:
    extra = {}
    if catalog is not None:
        extra["catalog"] = catalog
    return StrategyContext(
        as_of_date=as_of_date,
        universe_id="test_universe",
        extra=extra,
    )


class TestMLModelStrategy:
    def test_strategy_id(self) -> None:
        strat = MLModelStrategy(strategy_id="ml_top3", model_version="lgbm_v1")
        assert strat.strategy_id == "ml_top3"

    def test_returns_empty_without_catalog(self) -> None:
        strat = MLModelStrategy(strategy_id="ml_top3", model_version="lgbm_v1")
        signals = strat.generate_signals(_ctx(date(2025, 6, 1)))
        assert signals.is_empty()

    def test_returns_top_n_signals(self, catalog_with_predictions: Catalog) -> None:
        strat = MLModelStrategy(
            strategy_id="ml_top3",
            model_version="lgbm_v1",
            top_n=3,
            label_name="ret_5d",
        )
        signals = strat.generate_signals(_ctx(date(2025, 6, 1), catalog_with_predictions))
        assert len(signals) == 3
        asset_ids = set(signals["asset_id"].to_list())
        assert "SSE:600036" in asset_ids
        assert "SSE:600519" in asset_ids
        assert "SSE:002594" in asset_ids
        assert "SSE:000858" not in asset_ids

    def test_signals_have_correct_schema(self, catalog_with_predictions: Catalog) -> None:
        strat = MLModelStrategy("ml_top3", "lgbm_v1", top_n=3, label_name="ret_5d")
        signals = strat.generate_signals(_ctx(date(2025, 6, 1), catalog_with_predictions))
        assert "asset_id" in signals.columns
        assert "signal_date" in signals.columns
        assert "direction" in signals.columns
        assert "strength" in signals.columns
        assert "confidence" in signals.columns
        assert all(d == "long" for d in signals["direction"].to_list())

    def test_returns_empty_when_no_predictions_for_date(
        self, catalog_with_predictions: Catalog
    ) -> None:
        strat = MLModelStrategy("ml_top3", "lgbm_v1", top_n=3, label_name="ret_5d")
        signals = strat.generate_signals(_ctx(date(2025, 7, 1), catalog_with_predictions))
        assert signals.is_empty()

    def test_excludes_negative_predictions_by_default(
        self, catalog_with_predictions: Catalog
    ) -> None:
        strat = MLModelStrategy("ml_top3", "lgbm_v1", top_n=10, label_name="ret_5d")
        signals = strat.generate_signals(_ctx(date(2025, 6, 1), catalog_with_predictions))
        asset_ids = signals["asset_id"].to_list()
        assert "SSE:000858" not in asset_ids
