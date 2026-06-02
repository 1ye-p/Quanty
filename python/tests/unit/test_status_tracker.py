"""Tests for cquant.market_calendar.status_tracker."""

from datetime import date

from cquant.core.enums import AssetStatus
from cquant.market_calendar.status_tracker import StatusTracker


class TestStatusTracker:
    def setup_method(self):
        self.tracker = StatusTracker()

    def test_derive_st_from_name(self):
        assert StatusTracker.derive_st_from_name("ST 万科A") == AssetStatus.ST

    def test_derive_star_st_from_name(self):
        assert StatusTracker.derive_st_from_name("*ST 新海") == AssetStatus.STAR_ST

    def test_derive_active_from_name(self):
        assert StatusTracker.derive_st_from_name("贵州茅台") == AssetStatus.ACTIVE

    def test_cache_hit(self):
        self.tracker.set_status("SH600000", date(2026, 1, 1), AssetStatus.ST.value)
        result = self.tracker.get_status("SH600000", date(2026, 1, 1))
        assert result == "st"

    def test_cache_miss_returns_none(self):
        result = self.tracker.get_status("SH600000", date(2026, 1, 1))
        assert result is None

    def test_get_delist_date_no_cache(self):
        result = self.tracker.get_delist_date("SH600000")
        assert result is None

    def test_get_delist_date_cached(self):
        self.tracker._cache[("SH600000", "delist_date")] = "2026-06-01"
        result = self.tracker.get_delist_date("SH600000")
        assert result == date(2026, 6, 1)

    def test_get_delist_date_cached_none(self):
        self.tracker._cache[("SH600000", "delist_date")] = "none"
        result = self.tracker.get_delist_date("SH600000")
        assert result is None
