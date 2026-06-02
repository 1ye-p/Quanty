"""Tests for cquant.market_calendar.limit_detector."""

import pytest

from cquant.core.enums import LimitStatus
from cquant.market_calendar.limit_detector import detect_limit


def _bar(open_: float, high: float, low: float, close: float, volume: int = 1000) -> dict:
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


class TestDetectLimit:
    def test_no_limit(self):
        bar = _bar(10.0, 10.5, 9.5, 10.2)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.NONE

    def test_limit_up(self):
        bar = _bar(10.5, 11.0, 10.5, 11.0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.UP

    def test_limit_down(self):
        bar = _bar(9.5, 9.5, 9.0, 9.0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.DOWN

    def test_yizi_limit_up(self):
        bar = _bar(11.0, 11.0, 11.0, 11.0, volume=0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.YIZI_UP

    def test_yizi_limit_down(self):
        bar = _bar(9.0, 9.0, 9.0, 9.0, volume=0)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.YIZI_DOWN

    def test_st_limit_up(self):
        bar = _bar(10.5, 10.5, 10.5, 10.5)
        assert detect_limit(bar, 10.0, 0.05) == LimitStatus.YIZI_UP

    def test_normal_price_not_limit(self):
        bar = _bar(10.0, 10.3, 9.8, 10.1)
        assert detect_limit(bar, 10.0, 0.10) == LimitStatus.NONE

    def test_zero_prev_close_returns_none(self):
        bar = _bar(10.0, 10.0, 10.0, 10.0)
        assert detect_limit(bar, 0.0, 0.10) == LimitStatus.NONE

    def test_zero_limit_pct_returns_none(self):
        bar = _bar(10.0, 10.0, 10.0, 10.0)
        assert detect_limit(bar, 10.0, 0.0) == LimitStatus.NONE

    def test_tolerance_applied(self):
        # 9.9% change with 10% limit, tolerance=0.99 → threshold=9.9% → hits
        bar = _bar(10.99, 10.99, 10.99, 10.99)
        assert detect_limit(bar, 10.0, 0.10, tolerance=0.99) == LimitStatus.YIZI_UP
