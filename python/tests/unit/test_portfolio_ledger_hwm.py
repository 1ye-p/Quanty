"""Tests for high watermark auto-tracking in PortfolioLedger."""
from __future__ import annotations

from datetime import date

import pytest

from cquant.riskguard.portfolio_ledger import PortfolioLedger


def _make_ledger(initial_cash: float = 1_000_000) -> PortfolioLedger:
    return PortfolioLedger(initial_cash=initial_cash)


class TestPeakNavProperty:
    def test_initial_peak_nav_equals_initial_cash(self) -> None:
        ledger = _make_ledger(1_000_000)
        assert ledger.peak_nav == 1_000_000

    def test_peak_nav_updates_after_mark_to_market(self) -> None:
        ledger = _make_ledger(1_000_000)
        fill = {
            "trade_date": date(2025, 1, 2),
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": 1000,
            "price": 50.0,
            "notional": 50_000.0,
            "total_cost": 50_100.0,
        }
        ledger.apply_fill(fill)
        state = ledger.mark_to_market({"SSE:600036": 60.0}, date(2025, 1, 3))
        assert ledger.peak_nav >= state.nav

    def test_peak_nav_never_decreases(self) -> None:
        ledger = _make_ledger(1_000_000)
        fill = {
            "trade_date": date(2025, 1, 2),
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": 1000,
            "price": 50.0,
            "notional": 50_000.0,
            "total_cost": 50_100.0,
        }
        ledger.apply_fill(fill)
        state1 = ledger.mark_to_market({"SSE:600036": 60.0}, date(2025, 1, 3))
        peak_after_rise = ledger.peak_nav
        state2 = ledger.mark_to_market({"SSE:600036": 40.0}, date(2025, 1, 6))
        assert ledger.peak_nav == peak_after_rise
        assert state2.nav < peak_after_rise

    def test_current_drawdown_is_zero_at_peak(self) -> None:
        ledger = _make_ledger(1_000_000)
        state = ledger.mark_to_market({}, date(2025, 1, 2))
        dd = ledger.current_drawdown(state.nav)
        assert dd == pytest.approx(0.0, abs=1e-6)

    def test_current_drawdown_is_negative_below_peak(self) -> None:
        ledger = _make_ledger(1_000_000)
        fill = {
            "trade_date": date(2025, 1, 2),
            "asset_id": "SSE:600036",
            "side": "buy",
            "qty": 1000,
            "price": 50.0,
            "notional": 50_000.0,
            "total_cost": 50_100.0,
        }
        ledger.apply_fill(fill)
        state = ledger.mark_to_market({"SSE:600036": 45.0}, date(2025, 1, 3))
        dd = ledger.current_drawdown(state.nav)
        assert dd < 0

    def test_get_drawdown_backward_compat(self) -> None:
        ledger = _make_ledger(1_000_000)
        dd = ledger.get_drawdown(1_000_000, 900_000)
        assert dd == pytest.approx(-0.10, rel=1e-6)
