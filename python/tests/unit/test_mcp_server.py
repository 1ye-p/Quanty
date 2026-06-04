"""Unit tests for cquant.mcp_server."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import polars as pl


def _make_test_df(db_rows: list, schema: list[str]):
    """Create a Polars DataFrame from raw row tuples, or a mock empty."""
    if not db_rows:
        empty = MagicMock()
        empty.is_empty.return_value = True
        return empty
    return pl.DataFrame(db_rows, schema=schema, orient="row")


class TestQueryBacktestResult:
    _SCHEMA = [
        "run_id", "engine", "strategy_id", "dataset_version",
        "started_at", "completed_at", "status", "metrics_uri", "error_message",
    ]

    def _call(self, run_id: str, db_rows: list) -> dict:
        """Helper: mock Catalog, call the tool, parse JSON."""
        from cquant.mcp_server.server import query_backtest_result

        mock_catalog = MagicMock()
        mock_catalog.query.return_value = _make_test_df(db_rows, self._SCHEMA)
        with patch("cquant.mcp_server.server._get_catalog", return_value=mock_catalog):
            result = query_backtest_result(run_id)
        return json.loads(result)

    def test_returns_run_data(self) -> None:
        row = ("r1", "vector", "strat_a", "v1", "2026-01-01", "2026-01-02",
               "completed", "/metrics/r1.json", None)
        data = self._call("r1", [row])
        assert data["run_id"] == "r1"
        assert data["strategy_id"] == "strat_a"
        assert data["status"] == "completed"

    def test_not_found_returns_error(self) -> None:
        data = self._call("nonexistent", [])
        assert "error" in data
        assert "not found" in data["error"]

    def test_db_error_returns_error(self) -> None:
        from cquant.mcp_server.server import query_backtest_result
        with patch("cquant.mcp_server.server._get_catalog", side_effect=Exception("conn failed")):
            result = json.loads(query_backtest_result("r1"))
        assert "error" in result


class TestQueryFactorIC:
    _SCHEMA = [
        "job_id", "factor_name", "feature_set_version", "status",
        "summary_json", "created_at",
    ]

    def _call(self, factor_name: str, fsv: str, db_rows: list) -> dict:
        from cquant.mcp_server.server import query_factor_ic

        mock_catalog = MagicMock()
        mock_catalog.query.return_value = _make_test_df(db_rows, self._SCHEMA)
        with patch("cquant.mcp_server.server._get_catalog", return_value=mock_catalog):
            result = query_factor_ic(factor_name, fsv)
        return json.loads(result)

    def test_returns_summary(self) -> None:
        summary = json.dumps({"mean_ic": 0.05, "ir": 1.2})
        row = ("j1", "momentum_20d", "v1", "done", summary, "2026-01-01")
        data = self._call("momentum_20d", "v1", [row])
        assert data["factor_name"] == "momentum_20d"
        assert isinstance(data["summary_json"], dict)
        assert data["summary_json"]["mean_ic"] == 0.05

    def test_not_found_returns_error(self) -> None:
        data = self._call("unknown_factor", "", [])
        assert "error" in data

    def test_without_fsv_omits_filter(self) -> None:
        """When feature_set_version is empty, no version filter is applied."""
        from cquant.mcp_server.server import query_factor_ic
        mock_catalog = MagicMock()
        mock_catalog.query.return_value = _make_test_df([], self._SCHEMA)
        with patch("cquant.mcp_server.server._get_catalog", return_value=mock_catalog):
            query_factor_ic("my_factor", "")
        call_sql = mock_catalog.query.call_args[0][0]
        assert "AND feature_set_version" not in call_sql


class TestQueryRiskSnapshot:
    _SCHEMA = [
        "run_id", "snapshot_ts", "strategy_id", "gross_leverage",
        "net_leverage", "beta", "drawdown", "var_95", "cvar_95",
    ]

    def _call(self, run_id: str, strategy_id: str, db_rows: list) -> dict:
        from cquant.mcp_server.server import query_risk_snapshot

        mock_catalog = MagicMock()
        mock_catalog.query.return_value = _make_test_df(db_rows, self._SCHEMA)
        with patch("cquant.mcp_server.server._get_catalog", return_value=mock_catalog):
            result = query_risk_snapshot(run_id=run_id, strategy_id=strategy_id)
        return json.loads(result)

    def test_returns_snapshot_by_run_id(self) -> None:
        row = ("r1", "2026-01-01T12:00:00", "strat_a", 1.5, 0.8, 0.95, -0.12, -0.08, -0.10)
        data = self._call("r1", "", [row])
        assert data["run_id"] == "r1"
        assert data["gross_leverage"] == 1.5

    def test_no_args_returns_error(self) -> None:
        data = self._call("", "", [])
        assert "error" in data
        assert "run_id" in data["error"] or "strategy_id" in data["error"]

    def test_not_found_returns_error(self) -> None:
        data = self._call("nonexistent", "", [])
        assert "error" in data


class TestGetStockHistory:
    def _call(self, symbol: str, start: str, end: str, mock_df=None, exc=None) -> dict:
        from cquant.mcp_server.tools.market_data import get_stock_history
        import pandas as pd
        from unittest.mock import patch

        if exc is not None:
            with patch("cquant.mcp_server.tools.market_data.ak") as mock_ak:
                mock_ak.stock_zh_a_hist.side_effect = exc
                return json.loads(get_stock_history(symbol, start, end))

        if mock_df is None:
            mock_df = pd.DataFrame({
                "日期": ["2026-01-02", "2026-01-03"],
                "开盘": [10.0, 10.5],
                "最高": [10.8, 11.0],
                "最低": [9.9, 10.2],
                "收盘": [10.5, 10.8],
                "成交量": [1000000, 1200000],
                "成交额": [10500000.0, 12960000.0],
                "涨跌幅": [0.48, 2.86],
            })

        with patch("cquant.mcp_server.tools.market_data.ak") as mock_ak:
            mock_ak.stock_zh_a_hist.return_value = mock_df
            return json.loads(get_stock_history(symbol, start, end))

    def test_returns_records(self) -> None:
        data = self._call("600036", "20260101", "20260103")
        assert data["symbol"] == "600036"
        assert data["count"] == 2
        assert len(data["records"]) == 2
        assert "close" in data["records"][0]

    def test_invalid_symbol_rejected(self) -> None:
        from cquant.mcp_server.tools.market_data import get_stock_history
        result = json.loads(get_stock_history("SH600036", "20260101", "20260103"))
        assert "error" in result
        assert "Invalid symbol" in result["error"]

    def test_invalid_date_rejected(self) -> None:
        from cquant.mcp_server.tools.market_data import get_stock_history
        result = json.loads(get_stock_history("600036", "2026-01-01", "20260103"))
        assert "error" in result

    def test_akshare_error_returns_error(self) -> None:
        data = self._call("600036", "20260101", "20260103", exc=Exception("timeout"))
        assert "error" in data
        assert "AKShare fetch failed" in data["error"]

    def test_empty_df_returns_error(self) -> None:
        import pandas as pd
        data = self._call("600036", "20260101", "20260103", mock_df=pd.DataFrame())
        assert "error" in data
