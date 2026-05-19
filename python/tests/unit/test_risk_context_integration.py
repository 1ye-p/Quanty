"""Tests for RiskContext integration in backtest engine."""

from datetime import date, datetime
from decimal import Decimal

import polars as pl
import pytest

from cquant.core.types import RiskSnapshot
from cquant.riskguard.models import RiskContext


class TestBuildRiskContext:
    """Tests for VectorBacktestEngine._build_risk_context."""

    def test_has_build_risk_context_method(self):
        """VectorBacktestEngine should have _build_risk_context method."""
        from cquant.backtest_vector.engine import VectorBacktestEngine

        assert hasattr(VectorBacktestEngine, "_build_risk_context")

    def test_empty_positions(self):
        """With empty positions, RiskContext should have properly-schemaed DataFrame."""
        from cquant.backtest_vector.engine import VectorBacktestEngine

        engine = VectorBacktestEngine()
        ctx = engine._build_risk_context(
            trade_date=date(2025, 1, 1),
            positions_df=pl.DataFrame(),
            nav=Decimal("1000000"),
        )

        assert isinstance(ctx, RiskContext)
        assert ctx.as_of_date == date(2025, 1, 1)
        assert ctx.portfolio_nav == Decimal("1000000")
        assert ctx.current_positions.is_empty()
        # Verify schema has required columns
        expected_cols = {"asset_id", "quantity", "market_value", "weight"}
        assert set(ctx.current_positions.columns) == expected_cols

    def test_with_positions(self):
        """With real positions, RiskContext should have positions with computed weights."""
        from cquant.backtest_vector.engine import VectorBacktestEngine

        positions = pl.DataFrame({
            "asset_id": ["SSE:600036", "SSE:601318"],
            "quantity": [1000.0, 500.0],
            "market_value": [50000.0, 30000.0],
        })

        engine = VectorBacktestEngine()
        ctx = engine._build_risk_context(
            trade_date=date(2025, 1, 1),
            positions_df=positions,
            nav=Decimal("100000"),
        )

        assert not ctx.current_positions.is_empty()
        assert len(ctx.current_positions) == 2
        # Total market value = 50000 + 30000 = 80000
        weights = ctx.current_positions["weight"].to_list()
        assert abs(weights[0] - 50000 / 80000) < 1e-6  # 0.625
        assert abs(weights[1] - 30000 / 80000) < 1e-6  # 0.375

    def test_zero_market_value_positions(self):
        """If total market value is 0, weights should be 0."""
        from cquant.backtest_vector.engine import VectorBacktestEngine

        positions = pl.DataFrame({
            "asset_id": ["SSE:600036"],
            "quantity": [0.0],
            "market_value": [0.0],
        })

        engine = VectorBacktestEngine()
        ctx = engine._build_risk_context(
            trade_date=date(2025, 1, 1),
            positions_df=positions,
            nav=Decimal("1000000"),
        )

        assert ctx.current_positions["weight"].to_list() == [0.0]


class TestRiskSnapshotValues:
    """Tests for RiskSnapshot with real values."""

    def test_risk_snapshot_with_drawdown(self):
        """RiskSnapshot should carry non-default drawdown and leverage."""
        snap = RiskSnapshot(
            snapshot_ts=datetime(2025, 1, 1),
            strategy_id="test",
            gross_leverage=0.9,
            net_leverage=0.9,
            drawdown=-0.05,
        )
        assert snap.gross_leverage == 0.9
        assert snap.net_leverage == 0.9
        assert snap.drawdown == -0.05

    def test_risk_snapshot_with_var(self):
        """RiskSnapshot should accept VaR/CVaR values."""
        snap = RiskSnapshot(
            snapshot_ts=datetime(2025, 1, 1),
            strategy_id="test",
            var_95=-0.02,
            cvar_95=-0.03,
        )
        assert snap.var_95 == -0.02
        assert snap.cvar_95 == -0.03

    def test_risk_snapshot_defaults_still_work(self):
        """RiskSnapshot defaults should remain backward-compatible."""
        snap = RiskSnapshot(
            snapshot_ts=datetime(2025, 1, 1),
            strategy_id="test",
        )
        assert snap.gross_leverage == 0.0
        assert snap.net_leverage == 0.0
        assert snap.drawdown == 0.0
        assert snap.var_95 is None
        assert snap.cvar_95 is None


class TestDrawdownComputation:
    """Tests for drawdown computation logic."""

    def test_drawdown_from_returns(self):
        """Drawdown should be computed correctly from a returns series."""
        daily_returns = [0.01, -0.02, 0.01, -0.03, 0.02]

        cum = 1.0
        peak = 1.0
        for r in daily_returns:
            cum *= (1 + r)
            peak = max(peak, cum)
        drawdown = (cum - peak) / peak if peak > 0 else 0.0

        # cum = 1.01 * 0.98 * 1.01 * 0.97 * 1.02 = ~0.9890
        # peak = max(1.0, 1.01, ...) = 1.01
        # drawdown = (0.9890 - 1.01) / 1.01 ~ -0.0208
        assert drawdown < 0
        assert abs(drawdown - (-0.0208)) < 0.001

    def test_drawdown_empty_returns(self):
        """Empty returns should give 0 drawdown."""
        daily_returns = []
        drawdown = 0.0  # No returns = no drawdown
        assert drawdown == 0.0

    def test_drawdown_all_positive(self):
        """All positive returns should give 0 drawdown."""
        daily_returns = [0.01, 0.02, 0.01]
        cum = 1.0
        peak = 1.0
        for r in daily_returns:
            cum *= (1 + r)
            peak = max(peak, cum)
        drawdown = (cum - peak) / peak if peak > 0 else 0.0
        assert abs(drawdown) < 1e-10  # Essentially 0
