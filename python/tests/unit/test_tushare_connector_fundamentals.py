"""Tests for TushareConnector: fetch_valuation_daily, fetch_fundamentals, and helpers."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import polars as pl
import pytest

from cquant.datahub.connectors.tushare_connector import (
    TushareConnector,
    _parse,
    _to_asset_id,
)


# ---------------------------------------------------------------------------
# Helper: build a TushareConnector with a mocked _pro
# ---------------------------------------------------------------------------

def _make_connector() -> tuple[TushareConnector, MagicMock]:
    """Return a TushareConnector whose _pro is a MagicMock."""
    conn = TushareConnector.__new__(TushareConnector)
    conn._token = "fake"
    pro = MagicMock()
    conn._pro = pro
    return conn, pro


# ---------------------------------------------------------------------------
# Tests for helper functions
# ---------------------------------------------------------------------------

class TestToAssetId:
    def test_sh_code(self) -> None:
        assert _to_asset_id("600036.SH") == "SSE:600036"

    def test_sz_code(self) -> None:
        assert _to_asset_id("000001.SZ") == "SZSE:000001"

    def test_no_dot_returns_unchanged(self) -> None:
        assert _to_asset_id("600036") == "600036"


class TestParse:
    def test_valid_date(self) -> None:
        assert _parse("20241231") == datetime(2024, 12, 31)

    def test_hyphenated_date(self) -> None:
        assert _parse("2024-12-31") == datetime(2024, 12, 31)

    def test_none_returns_none(self) -> None:
        assert _parse(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse("") is None

    def test_invalid_string_returns_none(self) -> None:
        assert _parse("not-a-date") is None


# ---------------------------------------------------------------------------
# Tests for fetch_valuation_daily
# ---------------------------------------------------------------------------

class TestFetchValuationDaily:
    def _mock_daily_basic(self, pro: MagicMock) -> None:
        """Set up pro.daily_basic to return a small fake DataFrame."""
        pro.daily_basic.return_value = pd.DataFrame({
            "ts_code": ["600036.SH", "600036.SH"],
            "trade_date": ["20241230", "20241231"],
            "pe_ttm": [8.5, 8.6],
            "pb": [1.2, 1.21],
            "ps_ttm": [3.1, 3.2],
            "total_mv": [900000.0, 910000.0],
            "turnover_rate": [0.5, 0.6],
            "dv_ttm": [0.035, 0.036],
        })

    def test_returns_polars_dataframe(self) -> None:
        conn, pro = _make_connector()
        self._mock_daily_basic(pro)
        df = conn.fetch_valuation_daily("600036.SH", "20241230", "20241231")
        assert isinstance(df, pl.DataFrame)

    def test_market_cap_conversion(self) -> None:
        """market_cap should equal total_mv * 1e4 (万元 → 元)."""
        conn, pro = _make_connector()
        self._mock_daily_basic(pro)
        df = conn.fetch_valuation_daily("600036.SH", "20241230", "20241231")
        assert "market_cap" in df.columns
        assert df["market_cap"].to_list() == [900000.0 * 1e4, 910000.0 * 1e4]

    def test_dividend_yield_copied(self) -> None:
        """dividend_yield should equal dv_ttm."""
        conn, pro = _make_connector()
        self._mock_daily_basic(pro)
        df = conn.fetch_valuation_daily("600036.SH", "20241230", "20241231")
        assert "dividend_yield" in df.columns
        assert df["dividend_yield"].to_list() == df["dv_ttm"].to_list()

    def test_original_columns_preserved(self) -> None:
        conn, pro = _make_connector()
        self._mock_daily_basic(pro)
        df = conn.fetch_valuation_daily("600036.SH", "20241230", "20241231")
        for col in ("ts_code", "trade_date", "pe_ttm", "pb", "ps_ttm",
                     "total_mv", "turnover_rate", "dv_ttm"):
            assert col in df.columns, f"missing original column: {col}"

    def test_calls_pro_with_correct_args(self) -> None:
        conn, pro = _make_connector()
        self._mock_daily_basic(pro)
        conn.fetch_valuation_daily("600036.SH", "20241230", "20241231")
        pro.daily_basic.assert_called_once_with(
            ts_code="600036.SH",
            start_date="20241230",
            end_date="20241231",
            fields="ts_code,trade_date,pe_ttm,pb,ps_ttm,total_mv,turnover_rate,dv_ttm",
        )


# ---------------------------------------------------------------------------
# Tests for fetch_fundamentals
# ---------------------------------------------------------------------------

class TestFetchFundamentals:
    def _mock_fina_indicator(self, pro: MagicMock, rows: list[dict]) -> None:
        """Set up pro.fina_indicator to return rows as a pandas DataFrame."""
        pro.fina_indicator.return_value = pd.DataFrame(rows)

    def test_f_ann_date_priority(self) -> None:
        """When f_ann_date is present, announce_date should use it."""
        conn, pro = _make_connector()
        self._mock_fina_indicator(pro, [{
            "ts_code": "600036.SH",
            "ann_date": "20240401",
            "f_ann_date": "20240402",
            "end_date": "20241231",
            "roe": 15.0, "roa": 10.0,
            "grossprofit_margin": 40.0, "netprofit_margin": 25.0,
            "dt_profprofit_growth_rate": 5.0, "or_yoy": 8.0, "q_profit_yoy": 6.0,
        }])
        records = conn.fetch_fundamentals("600036.SH", "20241231")
        assert len(records) == 1
        assert records[0]["announce_date"] == datetime(2024, 4, 2)

    def test_ann_date_fallback(self) -> None:
        """When f_ann_date is None/empty, announce_date should fall back to ann_date."""
        conn, pro = _make_connector()
        self._mock_fina_indicator(pro, [{
            "ts_code": "600036.SH",
            "ann_date": "20240401",
            "f_ann_date": None,
            "end_date": "20241231",
            "roe": 15.0, "roa": 10.0,
            "grossprofit_margin": 40.0, "netprofit_margin": 25.0,
            "dt_profprofit_growth_rate": 5.0, "or_yoy": 8.0, "q_profit_yoy": 6.0,
        }])
        records = conn.fetch_fundamentals("600036.SH", "20241231")
        assert records[0]["announce_date"] == datetime(2024, 4, 1)

    def test_field_mapping(self) -> None:
        """Verify roe, roa, gross_margin, net_margin are correctly mapped."""
        conn, pro = _make_connector()
        self._mock_fina_indicator(pro, [{
            "ts_code": "600036.SH",
            "ann_date": "20240401",
            "f_ann_date": "20240402",
            "end_date": "20241231",
            "roe": 15.5, "roa": 10.2,
            "grossprofit_margin": 42.3, "netprofit_margin": 26.1,
            "dt_profprofit_growth_rate": 5.0, "or_yoy": 8.0, "q_profit_yoy": 6.0,
        }])
        records = conn.fetch_fundamentals("600036.SH", "20241231")
        rec = records[0]
        assert rec["roe"] == 15.5
        assert rec["roa"] == 10.2
        assert rec["gross_margin"] == 42.3
        assert rec["net_margin"] == 26.1

    def test_asset_id_conversion(self) -> None:
        """Verify _to_asset_id converts ts_code in the output."""
        conn, pro = _make_connector()
        self._mock_fina_indicator(pro, [{
            "ts_code": "600036.SH",
            "ann_date": "20240401",
            "f_ann_date": "20240402",
            "end_date": "20241231",
            "roe": 15.0, "roa": 10.0,
            "grossprofit_margin": 40.0, "netprofit_margin": 25.0,
            "dt_profprofit_growth_rate": 5.0, "or_yoy": 8.0, "q_profit_yoy": 6.0,
        }])
        records = conn.fetch_fundamentals("600036.SH", "20241231")
        assert records[0]["asset_id"] == "SSE:600036"

    def test_report_date_parsed(self) -> None:
        conn, pro = _make_connector()
        self._mock_fina_indicator(pro, [{
            "ts_code": "600036.SH",
            "ann_date": "20240401",
            "f_ann_date": "20240402",
            "end_date": "20241231",
            "roe": 15.0, "roa": 10.0,
            "grossprofit_margin": 40.0, "netprofit_margin": 25.0,
            "dt_profprofit_growth_rate": 5.0, "or_yoy": 8.0, "q_profit_yoy": 6.0,
        }])
        records = conn.fetch_fundamentals("600036.SH", "20241231")
        assert records[0]["report_date"] == datetime(2024, 12, 31)

    def test_multiple_rows(self) -> None:
        conn, pro = _make_connector()
        self._mock_fina_indicator(pro, [
            {
                "ts_code": "600036.SH", "ann_date": "20240401",
                "f_ann_date": "20240402", "end_date": "20241231",
                "roe": 15.0, "roa": 10.0,
                "grossprofit_margin": 40.0, "netprofit_margin": 25.0,
                "dt_profprofit_growth_rate": 5.0, "or_yoy": 8.0, "q_profit_yoy": 6.0,
            },
            {
                "ts_code": "600036.SH", "ann_date": "20231001",
                "f_ann_date": None, "end_date": "20230930",
                "roe": 12.0, "roa": 8.0,
                "grossprofit_margin": 38.0, "netprofit_margin": 22.0,
                "dt_profprofit_growth_rate": 3.0, "or_yoy": 5.0, "q_profit_yoy": 4.0,
            },
        ])
        records = conn.fetch_fundamentals("600036.SH", "20241231")
        assert len(records) == 2
        # second row: f_ann_date is None → falls back to ann_date
        assert records[1]["announce_date"] == datetime(2023, 10, 1)
