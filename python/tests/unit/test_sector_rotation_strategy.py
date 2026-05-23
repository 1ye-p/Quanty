"""Tests for SectorRotationStrategy."""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.backtest_vector.strategies.sector_rotation import SectorRotationStrategy
from cquant.backtest_vector.strategy import StrategyContext


def _features(assets_by_sector: dict[str, list[str]], factor_values: dict[str, float]) -> pl.DataFrame:
    rows = []
    for sector, assets in assets_by_sector.items():
        for asset in assets:
            rows.append({
                "asset_id": asset,
                "trade_date": date(2025, 6, 1),
                "ret_20d": factor_values.get(asset, 0.0),
            })
    return pl.DataFrame(rows)


def _ctx(features: pl.DataFrame, sector_map: dict | None = None) -> StrategyContext:
    return StrategyContext(
        as_of_date=date(2025, 6, 1),
        universe_id="test",
        features=features,
        extra={"sector_map": sector_map} if sector_map else {},
    )


class TestSectorRotationStrategy:
    def test_strategy_id(self) -> None:
        strat = SectorRotationStrategy("sr_test")
        assert strat.strategy_id == "sr_test"

    def test_selects_from_top_sectors_only(self) -> None:
        sector_map = {
            "A1": "Tech", "A2": "Tech",
            "B1": "Finance", "B2": "Finance",
        }
        features = _features(
            {"Tech": ["A1", "A2"], "Finance": ["B1", "B2"]},
            {"A1": 0.10, "A2": 0.09, "B1": 0.02, "B2": 0.01},
        )
        strat = SectorRotationStrategy(
            "sr_test",
            factor_col="ret_20d",
            sector_map=sector_map,
            top_sectors=1,
            top_n_per_sector=2,
        )
        signals = strat.generate_signals(_ctx(features))
        asset_ids = set(signals["asset_id"].to_list())
        assert "A1" in asset_ids or "A2" in asset_ids
        assert "B1" not in asset_ids
        assert "B2" not in asset_ids

    def test_respects_top_n_per_sector(self) -> None:
        sector_map = {"A1": "Tech", "A2": "Tech", "A3": "Tech"}
        features = _features(
            {"Tech": ["A1", "A2", "A3"]},
            {"A1": 0.10, "A2": 0.09, "A3": 0.01},
        )
        strat = SectorRotationStrategy(
            "sr_test",
            factor_col="ret_20d",
            sector_map=sector_map,
            top_sectors=1,
            top_n_per_sector=2,
        )
        signals = strat.generate_signals(_ctx(features))
        assert len(signals) == 2
        assert "A1" in signals["asset_id"].to_list()
        assert "A2" in signals["asset_id"].to_list()

    def test_returns_empty_without_features(self) -> None:
        strat = SectorRotationStrategy("sr_test")
        ctx = StrategyContext(as_of_date=date(2025, 6, 1), universe_id="test")
        signals = strat.generate_signals(ctx)
        assert signals.is_empty()

    def test_signals_have_correct_schema(self) -> None:
        sector_map = {"A1": "Tech"}
        features = _features({"Tech": ["A1"]}, {"A1": 0.10})
        strat = SectorRotationStrategy("sr_test", sector_map=sector_map)
        signals = strat.generate_signals(_ctx(features, sector_map))
        assert "asset_id" in signals.columns
        assert "signal_date" in signals.columns
        assert "direction" in signals.columns
        assert "strength" in signals.columns
        assert "confidence" in signals.columns
