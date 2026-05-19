"""Tests for A-share limit detection rules."""
import pytest
from cquant.backtest_vector.limit_rules import (
    BoardType, detect_board, get_limit_pct, is_at_limit_up, is_at_limit_down,
)


class TestDetectBoard:
    def test_sse_main(self):
        assert detect_board("SH600000") == BoardType.MAIN
        assert detect_board("SH601398") == BoardType.MAIN

    def test_star(self):
        assert detect_board("SH688001") == BoardType.STAR

    def test_szse_main(self):
        assert detect_board("SZ000001") == BoardType.MAIN
        assert detect_board("SZ002594") == BoardType.MAIN

    def test_chinext(self):
        assert detect_board("SZ300001") == BoardType.CHINEXT
        assert detect_board("SZ301001") == BoardType.CHINEXT

    def test_bse(self):
        assert detect_board("BJ430001") == BoardType.BSE

    def test_unknown_defaults_to_main(self):
        assert detect_board("") == BoardType.MAIN
        assert detect_board("XX123456") == BoardType.MAIN


class TestGetLimitPct:
    def test_main_board_10pct(self):
        assert get_limit_pct("SH600000") == 0.10

    def test_chinext_20pct(self):
        assert get_limit_pct("SZ300001") == 0.20

    def test_star_20pct(self):
        assert get_limit_pct("SH688001") == 0.20

    def test_bse_30pct(self):
        assert get_limit_pct("BJ430001") == 0.30

    def test_st_stock_5pct(self):
        assert get_limit_pct("SH600000", is_st=True) == 0.05


class TestIsAtLimit:
    def test_main_board_limit_up(self):
        prev = 10.0
        assert is_at_limit_up(11.0, prev, "SH600000") is True
        assert is_at_limit_up(10.5, prev, "SH600000") is False

    def test_chinext_limit_up(self):
        prev = 10.0
        assert is_at_limit_up(12.0, prev, "SZ300001") is True
        assert is_at_limit_up(11.5, prev, "SZ300001") is False

    def test_main_board_limit_down(self):
        prev = 10.0
        assert is_at_limit_down(9.0, prev, "SH600000") is True
        assert is_at_limit_down(9.5, prev, "SH600000") is False

    def test_invalid_prices(self):
        assert is_at_limit_up(0, 10.0, "SH600000") is False
        assert is_at_limit_down(10.0, 0, "SH600000") is False
