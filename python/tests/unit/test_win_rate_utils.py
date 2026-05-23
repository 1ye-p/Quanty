"""测试 compute_win_rates_from_fills() Kelly 胜率工具。"""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.ml_lab.win_rate_utils import compute_win_rates_from_fills


def _make_fills(trades: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(trades)


class TestComputeWinRates:
    def test_returns_empty_for_empty_fills(self) -> None:
        fills = pl.DataFrame()
        result = compute_win_rates_from_fills(fills)
        assert result == {}

    def test_profitable_trades_give_high_win_rate(self) -> None:
        fills = _make_fills([
            {"asset_id": "A", "side": "buy",  "qty": 100, "price": 10.0, "trade_date": date(2025, 1, 1), "total_cost": 1010.0},
            {"asset_id": "A", "side": "sell", "qty": 100, "price": 12.0, "trade_date": date(2025, 1, 5), "total_cost": 1200.0},
            {"asset_id": "A", "side": "buy",  "qty": 100, "price": 10.0, "trade_date": date(2025, 1, 6), "total_cost": 1010.0},
            {"asset_id": "A", "side": "sell", "qty": 100, "price": 11.0, "trade_date": date(2025, 1, 8), "total_cost": 1100.0},
        ])
        result = compute_win_rates_from_fills(fills, min_trades=1)
        assert "A" in result
        assert result["A"] == pytest.approx(1.0, abs=0.01)

    def test_losing_trades_give_low_win_rate(self) -> None:
        fills = _make_fills([
            {"asset_id": "A", "side": "buy",  "qty": 100, "price": 12.0, "trade_date": date(2025, 1, 1), "total_cost": 1210.0},
            {"asset_id": "A", "side": "sell", "qty": 100, "price": 10.0, "trade_date": date(2025, 1, 5), "total_cost": 1000.0},
            {"asset_id": "A", "side": "buy",  "qty": 100, "price": 11.0, "trade_date": date(2025, 1, 6), "total_cost": 1110.0},
            {"asset_id": "A", "side": "sell", "qty": 100, "price": 9.0,  "trade_date": date(2025, 1, 8), "total_cost": 900.0},
        ])
        result = compute_win_rates_from_fills(fills, min_trades=1)
        assert "A" in result
        assert result["A"] == pytest.approx(0.0, abs=0.01)

    def test_insufficient_trades_excluded(self) -> None:
        fills = _make_fills([
            {"asset_id": "A", "side": "buy",  "qty": 100, "price": 10.0, "trade_date": date(2025, 1, 1), "total_cost": 1000.0},
            {"asset_id": "A", "side": "sell", "qty": 100, "price": 12.0, "trade_date": date(2025, 1, 5), "total_cost": 1200.0},
        ])
        result = compute_win_rates_from_fills(fills, min_trades=3)
        assert "A" not in result

    def test_multiple_assets_computed_independently(self) -> None:
        fills = _make_fills([
            {"asset_id": "A", "side": "buy",  "qty": 100, "price": 10.0, "trade_date": date(2025, 1, 1), "total_cost": 1000.0},
            {"asset_id": "A", "side": "sell", "qty": 100, "price": 12.0, "trade_date": date(2025, 1, 5), "total_cost": 1200.0},
            {"asset_id": "B", "side": "buy",  "qty": 100, "price": 10.0, "trade_date": date(2025, 1, 1), "total_cost": 1000.0},
            {"asset_id": "B", "side": "sell", "qty": 100, "price": 8.0,  "trade_date": date(2025, 1, 5), "total_cost": 800.0},
        ])
        result = compute_win_rates_from_fills(fills, min_trades=1)
        assert result["A"] == pytest.approx(1.0, abs=0.01)
        assert result["B"] == pytest.approx(0.0, abs=0.01)
