"""Tests for cquant.market_calendar.delist_handler."""

from datetime import date

from cquant.market_calendar.delist_handler import DelistHandler


class TestDelistHandler:
    def test_handle_delist_with_position(self):
        handler = DelistHandler()
        trades = handler.handle_delist(
            positions={"SH600000": 1000},
            asset_id="SH600000",
            trade_date=date(2026, 6, 1),
            price=5.0,
        )
        assert len(trades) == 1
        assert trades[0].side == "sell"
        assert trades[0].qty == 1000
        assert trades[0].price == 5.0
        assert trades[0].reason == "delist_forced_liquidation"

    def test_handle_delist_no_position(self):
        handler = DelistHandler()
        trades = handler.handle_delist(
            positions={},
            asset_id="SH600000",
            trade_date=date(2026, 6, 1),
            price=5.0,
        )
        assert len(trades) == 0

    def test_handle_delist_zero_quantity(self):
        handler = DelistHandler()
        trades = handler.handle_delist(
            positions={"SH600000": 0},
            asset_id="SH600000",
            trade_date=date(2026, 6, 1),
            price=5.0,
        )
        assert len(trades) == 0
