"""Tests for risk data layer: RiskSnapshot persistence, rolling risk metrics, and drawdown analysis."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from cquant.backtest_vector.run import (
    BacktestRunner,
    BacktestRunSpec,
    _compute_beta,
    _compute_sector_exposure,
    _detect_drawdown_periods,
)


class TestRiskSnapshotFix:
    """Test that _persist_positions computes real leverage, beta, and sector exposure."""

    def test_compute_beta_basic(self):
        """Test beta calculation with known correlation."""
        # Perfect correlation: beta should be 1.0
        portfolio_returns = [0.01, 0.02, -0.01, 0.03, -0.02] * 15  # 75 returns
        benchmark_returns = [0.01, 0.02, -0.01, 0.03, -0.02] * 15
        beta = _compute_beta(portfolio_returns, benchmark_returns, window=60)
        assert beta is not None
        assert abs(beta - 1.0) < 0.01

    def test_compute_beta_inverse(self):
        """Test beta with inverse returns."""
        portfolio_returns = [0.01, -0.02, 0.03, -0.01, 0.02] * 15
        benchmark_returns = [-0.01, 0.02, -0.03, 0.01, -0.02] * 15
        beta = _compute_beta(portfolio_returns, benchmark_returns, window=60)
        assert beta is not None
        assert beta < 0  # Negative correlation

    def test_compute_beta_insufficient_data(self):
        """Test beta returns None when insufficient data."""
        portfolio_returns = [0.01, 0.02]
        benchmark_returns = [0.01, 0.02]
        beta = _compute_beta(portfolio_returns, benchmark_returns, window=60)
        assert beta is None

    def test_compute_sector_exposure_basic(self):
        """Test sector exposure computation."""
        positions = pl.DataFrame({
            "asset_id": ["AAPL", "MSFT", "GOOGL"],
            "target_weight": [0.3, 0.4, 0.3],
        })
        sector_map = {"AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology"}
        exposure = _compute_sector_exposure(positions, sector_map)
        assert "Technology" in exposure
        assert abs(exposure["Technology"] - 1.0) < 0.01

    def test_compute_sector_exposure_multiple_sectors(self):
        """Test sector exposure with multiple sectors."""
        positions = pl.DataFrame({
            "asset_id": ["AAPL", "JPM", "JNJ"],
            "target_weight": [0.4, 0.3, 0.3],
        })
        sector_map = {"AAPL": "Technology", "JPM": "Financials", "JNJ": "Healthcare"}
        exposure = _compute_sector_exposure(positions, sector_map)
        assert len(exposure) == 3
        assert abs(exposure["Technology"] - 0.4) < 0.01
        assert abs(exposure["Financials"] - 0.3) < 0.01
        assert abs(exposure["Healthcare"] - 0.3) < 0.01

    def test_compute_sector_exposure_empty(self):
        """Test sector exposure with empty positions."""
        positions = pl.DataFrame({"asset_id": [], "target_weight": []})
        sector_map = {"AAPL": "Technology"}
        exposure = _compute_sector_exposure(positions, sector_map)
        assert exposure == {}

    def test_compute_sector_exposure_unknown_sector(self):
        """Test sector exposure with unknown sector."""
        positions = pl.DataFrame({
            "asset_id": ["AAPL", "UNKNOWN"],
            "target_weight": [0.5, 0.5],
        })
        sector_map = {"AAPL": "Technology"}
        exposure = _compute_sector_exposure(positions, sector_map)
        assert "Technology" in exposure
        assert "Unknown" in exposure


class TestRollingRiskMetrics:
    """Test rolling risk metrics computation."""

    def test_persist_rolling_risk_metrics_basic(self):
        """Test that rolling risk metrics are computed and persisted."""
        # Create mock result
        mock_catalog = MagicMock()
        mock_conn = MagicMock()
        mock_catalog._get_conn.return_value = mock_conn

        # Create mock portfolio returns with valid dates (use datetime objects)
        base_date = date(2024, 1, 1)
        dates = [date(2024, 1, (i % 28) + 1) for i in range(100)]
        returns = [0.01 * (i % 5 - 2) for i in range(100)]  # Some variation
        portfolio_returns = pl.DataFrame({
            "trade_date": dates,
            "portfolio_return": returns,
            "nav": [1000000 * (1 + r) for r in returns],
        })

        # Create mock spec
        mock_spec = MagicMock()
        mock_spec.benchmark_asset_id = ""
        mock_spec.prices = pl.DataFrame()

        mock_result = MagicMock()
        mock_result.portfolio_returns = portfolio_returns
        mock_result.spec = mock_spec

        runner = BacktestRunner(mock_catalog)
        runner._persist_rolling_risk_metrics(mock_result, "test_run_id")

        # Verify executemany was called
        assert mock_conn.executemany.called
        call_args = mock_conn.executemany.call_args
        rows = call_args[0][1]

        # Should have rows for windows 20, 60 (not 252 since only 100 returns)
        assert len(rows) > 0

        # Check that each row has correct structure
        for row in rows:
            assert len(row) == 8
            assert row[0] == "test_run_id"  # run_id
            assert row[2] in [20, 60, 252]  # window
            assert isinstance(row[3], float)  # rolling_var
            assert isinstance(row[4], float)  # rolling_cvar
            assert isinstance(row[5], float)  # rolling_vol
            assert isinstance(row[6], float)  # rolling_sharpe

    def test_persist_rolling_risk_metrics_empty_returns(self):
        """Test that empty returns are handled gracefully."""
        mock_catalog = MagicMock()
        mock_result = MagicMock()
        mock_result.portfolio_returns = pl.DataFrame()

        runner = BacktestRunner(mock_catalog)
        runner._persist_rolling_risk_metrics(mock_result, "test_run_id")

        # Should not call executemany
        mock_catalog._get_conn.assert_not_called()


class TestDrawdownAnalysis:
    """Test drawdown period detection."""

    def test_detect_drawdown_periods_basic(self):
        """Test basic drawdown detection."""
        nav_series = [
            (date(2024, 1, 1), 100.0),
            (date(2024, 1, 2), 110.0),  # Peak
            (date(2024, 1, 3), 99.0),   # Drawdown starts
            (date(2024, 1, 4), 95.0),   # Trough
            (date(2024, 1, 5), 115.0),  # Recovery (above previous peak)
        ]
        periods = _detect_drawdown_periods(nav_series)
        assert len(periods) == 1
        assert periods[0]["start_date"] == date(2024, 1, 2)  # Peak date, not first drop
        assert periods[0]["trough_date"] == date(2024, 1, 4)
        assert periods[0]["recovery_date"] == date(2024, 1, 5)
        assert periods[0]["max_drawdown"] < 0
        assert periods[0]["duration_days"] == 3  # peak to recovery
        assert periods[0]["recovery_days"] == 1  # trough to recovery

    def test_detect_drawdown_periods_no_drawdown(self):
        """Test when there's no drawdown (monotonically increasing)."""
        nav_series = [
            (date(2024, 1, 1), 100.0),
            (date(2024, 1, 2), 110.0),
            (date(2024, 1, 3), 120.0),
            (date(2024, 1, 4), 130.0),
        ]
        periods = _detect_drawdown_periods(nav_series)
        assert len(periods) == 0

    def test_detect_drawdown_periods_multiple(self):
        """Test detection of multiple drawdown periods."""
        nav_series = [
            (date(2024, 1, 1), 100.0),
            (date(2024, 1, 2), 110.0),  # Peak 1
            (date(2024, 1, 3), 99.0),   # Drawdown 1 starts
            (date(2024, 1, 4), 115.0),  # Recovery + new peak
            (date(2024, 1, 5), 100.0),  # Drawdown 2 starts
            (date(2024, 1, 6), 125.0),  # Recovery
        ]
        periods = _detect_drawdown_periods(nav_series)
        assert len(periods) == 2

    def test_detect_drawdown_periods_ongoing(self):
        """Test detection of ongoing drawdown (no recovery)."""
        nav_series = [
            (date(2024, 1, 1), 100.0),
            (date(2024, 1, 2), 110.0),  # Peak
            (date(2024, 1, 3), 95.0),   # Drawdown starts
            (date(2024, 1, 4), 90.0),   # Still in drawdown
        ]
        periods = _detect_drawdown_periods(nav_series)
        assert len(periods) == 1
        assert periods[0]["recovery_date"] is None
        assert periods[0]["recovery_days"] == -1

    def test_detect_drawdown_periods_insufficient_data(self):
        """Test with insufficient data points."""
        nav_series = [(date(2024, 1, 1), 100.0)]
        periods = _detect_drawdown_periods(nav_series)
        assert len(periods) == 0

    def test_persist_drawdown_periods(self):
        """Test that drawdown periods are persisted correctly."""
        mock_catalog = MagicMock()
        mock_conn = MagicMock()
        mock_catalog._get_conn.return_value = mock_conn

        # Create mock portfolio returns with drawdown
        dates = [date(2024, 1, i + 1) for i in range(10)]
        navs = [100.0, 110.0, 105.0, 100.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0]
        returns = [0.0] + [(navs[i] / navs[i-1] - 1) for i in range(1, len(navs))]

        portfolio_returns = pl.DataFrame({
            "trade_date": dates,
            "portfolio_return": returns,
            "nav": navs,
        })

        mock_result = MagicMock()
        mock_result.portfolio_returns = portfolio_returns

        runner = BacktestRunner(mock_catalog)
        runner._persist_drawdown_periods(mock_result, "test_run_id")

        # Verify executemany was called
        assert mock_conn.executemany.called
        call_args = mock_conn.executemany.call_args
        rows = call_args[0][1]

        # Should have at least one drawdown period
        assert len(rows) > 0

        # Check row structure
        for row in rows:
            assert len(row) == 9
            assert row[0] == "test_run_id"  # run_id
            assert isinstance(row[1], int)  # period_id
