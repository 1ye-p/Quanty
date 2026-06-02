"""Tests for CNTradingRules extended market rules."""

from datetime import date

from cquant.core.enums import AssetStatus, LimitStatus, TradabilityReason
from cquant.market_calendar.rules.base import TradabilityResult
from cquant.market_calendar.rules.cn_rules import CNTradingRules


def _bar(open_: float = 10.0, high: float = 10.5, low: float = 9.5, close: float = 10.2, volume: int = 1000) -> dict:
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


class TestCNTradingRulesExtended:
    def setup_method(self):
        self.rules = CNTradingRules()

    def test_detect_limit_normal(self):
        bar = _bar(10.0, 10.3, 9.8, 10.1)
        result = self.rules.detect_limit(bar, 10.0, 0.10)
        assert result == LimitStatus.NONE

    def test_detect_limit_up(self):
        bar = _bar(10.5, 11.0, 10.5, 11.0)
        result = self.rules.detect_limit(bar, 10.0, 0.10)
        assert result == LimitStatus.UP

    def test_detect_yizi_up(self):
        bar = _bar(11.0, 11.0, 11.0, 11.0, volume=0)
        result = self.rules.detect_limit(bar, 10.0, 0.10)
        assert result == LimitStatus.YIZI_UP

    def test_check_tradable_active(self):
        bar = _bar()
        result = self.rules.check_tradable("SH600000", date(2026, 1, 2), bar)
        assert result.tradable is True
        assert result.reason == TradabilityReason.TRADABLE

    def test_check_tradable_yizi_up(self):
        bar = _bar(11.0, 11.0, 11.0, 11.0, volume=0)
        bar["pre_close"] = 10.0
        result = self.rules.check_tradable("SH600000", date(2026, 1, 2), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.YIZI_LIMIT

    def test_check_tradable_yizi_down(self):
        bar = _bar(9.0, 9.0, 9.0, 9.0, volume=0)
        bar["pre_close"] = 10.0
        result = self.rules.check_tradable("SH600000", date(2026, 1, 2), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.YIZI_LIMIT

    def test_check_tradable_delisted(self):
        from cquant.market_calendar.status_tracker import StatusTracker
        tracker = StatusTracker()
        tracker.set_status("SH600000", date(2026, 6, 1), AssetStatus.DELISTED.value)
        self.rules.set_status_tracker(tracker)
        bar = _bar()
        result = self.rules.check_tradable("SH600000", date(2026, 6, 1), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.DELISTED

    def test_get_asset_status_default(self):
        result = self.rules.get_asset_status("SH600000", date(2026, 1, 2))
        assert result == AssetStatus.ACTIVE.value

    def test_get_asset_status_with_tracker(self):
        from cquant.market_calendar.status_tracker import StatusTracker
        tracker = StatusTracker()
        tracker.set_status("SH600000", date(2026, 1, 2), AssetStatus.ST.value)
        self.rules.set_status_tracker(tracker)
        result = self.rules.get_asset_status("SH600000", date(2026, 1, 2))
        assert result == "st"

    def test_get_delist_date_default(self):
        result = self.rules.get_delist_date("SH600000")
        assert result is None

    def test_handle_delist(self):
        trades = self.rules.handle_delist({"SH600000": 1000}, "SH600000", date(2026, 1, 2), 5.0)
        assert len(trades) == 1
        assert trades[0].side == "sell"
        assert trades[0].qty == 1000

    def test_handle_delist_no_position(self):
        trades = self.rules.handle_delist({}, "SH600000", date(2026, 1, 2), 5.0)
        assert len(trades) == 0

    def test_get_board_main(self):
        assert self.rules._get_board("SH600000") == "main_board"

    def test_get_board_chinext(self):
        assert self.rules._get_board("SZSE:300001") == "chinext"

    def test_get_board_star(self):
        assert self.rules._get_board("SSE:688001") == "star"

    def test_get_limit_pct_main(self):
        assert self.rules._get_limit_pct("SH600000") == 0.10

    def test_get_limit_pct_st(self):
        assert self.rules._get_limit_pct("SH600000", is_st=True) == 0.05

    def test_get_limit_pct_chinext(self):
        assert self.rules._get_limit_pct("SZSE:300001") == 0.20

    def test_st_limit_5pct_yizi(self):
        from cquant.market_calendar.status_tracker import StatusTracker
        tracker = StatusTracker()
        tracker.set_status("SZ000001", date(2026, 1, 2), AssetStatus.ST.value)
        self.rules.set_status_tracker(tracker)
        bar = _bar(10.5, 10.5, 10.5, 10.5, volume=0)
        bar["pre_close"] = 10.0
        result = self.rules.check_tradable("SZ000001", date(2026, 1, 2), bar)
        assert result.tradable is False
        assert result.reason == TradabilityReason.YIZI_LIMIT
