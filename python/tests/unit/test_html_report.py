"""Tests for HTML report SVG generators."""

from __future__ import annotations

import pytest

from cquant.api_server.routes.backtests import (
    _attribution_bar_svg,
    _drawdown_to_svg,
    _return_dist_to_svg,
    _tca_pie_svg,
    _rolling_vol_to_svg,
)


# ── _drawdown_to_svg ─────────────────────────────────────────────────────────


class TestDrawdownToSvg:
    def test_empty_data(self):
        result = _drawdown_to_svg([])
        assert "暂无回撤数据" in result
        assert "<svg" not in result

    def test_normal_data(self):
        data = [
            {"trade_date": "2025-01-01", "drawdown": 0.0},
            {"trade_date": "2025-02-01", "drawdown": -0.05},
            {"trade_date": "2025-03-01", "drawdown": -0.02},
        ]
        result = _drawdown_to_svg(data)
        assert "<svg" in result
        assert "</svg>" in result
        assert "polyline" in result
        assert "polygon" in result

    def test_all_zero_drawdown(self):
        data = [
            {"trade_date": "2025-01-01", "drawdown": 0.0},
            {"trade_date": "2025-02-01", "drawdown": 0.0},
        ]
        result = _drawdown_to_svg(data)
        assert "<svg" in result
        assert "</svg>" in result

    def test_custom_dimensions(self):
        data = [{"trade_date": "2025-01-01", "drawdown": -0.1}]
        result = _drawdown_to_svg(data, width=400, height=100)
        assert 'viewBox="0 0 400 100"' in result


# ── _rolling_vol_to_svg ──────────────────────────────────────────────────────


class TestRollingVolToSvg:
    def test_empty_data(self):
        result = _rolling_vol_to_svg([])
        assert "暂无滚动波动率数据" in result
        assert "<svg" not in result

    def test_normal_data(self):
        data = [
            {"trade_date": "2025-01-01", "volatility": 0.15},
            {"trade_date": "2025-02-01", "volatility": 0.20},
            {"trade_date": "2025-03-01", "volatility": 0.12},
        ]
        result = _rolling_vol_to_svg(data)
        assert "<svg" in result
        assert "</svg>" in result
        assert "polyline" in result

    def test_single_point(self):
        data = [{"trade_date": "2025-01-01", "volatility": 0.18}]
        result = _rolling_vol_to_svg(data)
        assert "<svg" in result

    def test_custom_dimensions(self):
        data = [{"trade_date": "2025-01-01", "volatility": 0.15}]
        result = _rolling_vol_to_svg(data, width=600, height=150)
        assert 'viewBox="0 0 600 150"' in result


# ── _return_dist_to_svg ──────────────────────────────────────────────────────


class TestReturnDistToSvg:
    def test_empty_data(self):
        result = _return_dist_to_svg([])
        assert "暂无收益率数据" in result
        assert "<svg" not in result

    def test_normal_data(self):
        returns = [0.01, -0.02, 0.015, -0.005, 0.03, -0.01, 0.005, 0.02, -0.015, 0.01]
        result = _return_dist_to_svg(returns)
        assert "<svg" in result
        assert "</svg>" in result
        assert "rect" in result

    def test_uniform_returns(self):
        returns = [0.01] * 20
        result = _return_dist_to_svg(returns)
        assert "<svg" in result

    def test_custom_bins(self):
        returns = [0.01 * i for i in range(-5, 6)]
        result = _return_dist_to_svg(returns, bins=10)
        assert "<svg" in result

    def test_single_return(self):
        result = _return_dist_to_svg([0.05])
        assert "<svg" in result


# ── _tca_pie_svg ─────────────────────────────────────────────────────────────


class TestTcaPieSvg:
    def test_empty_data(self):
        result = _tca_pie_svg({})
        assert "暂无交易成本数据" in result
        assert "<svg" not in result

    def test_all_zero(self):
        result = _tca_pie_svg({
            "total_commission": 0,
            "total_slippage": 0,
            "total_stamp_duty": 0,
        })
        assert "暂无交易成本数据" in result

    def test_normal_data(self):
        tca = {
            "total_commission": 150.5,
            "total_slippage": 80.3,
            "total_stamp_duty": 45.2,
        }
        result = _tca_pie_svg(tca)
        assert "<svg" in result
        assert "</svg>" in result
        assert "path" in result
        assert "佣金" in result
        assert "滑点" in result
        assert "印花税" in result

    def test_single_slice(self):
        tca = {"total_commission": 100, "total_slippage": 0, "total_stamp_duty": 0}
        result = _tca_pie_svg(tca)
        assert "<svg" in result
        assert "path" in result

    def test_custom_dimensions(self):
        tca = {"total_commission": 50, "total_slippage": 30, "total_stamp_duty": 20}
        result = _tca_pie_svg(tca, width=300, height=250)
        assert 'viewBox="0 0 300 250"' in result


# ── _attribution_bar_svg ─────────────────────────────────────────────────────


class TestAttributionBarSvg:
    def test_empty_data(self):
        result = _attribution_bar_svg({})
        assert "<svg" in result
        assert "</svg>" in result
        assert "rect" in result

    def test_normal_data(self):
        attr = {
            "allocation_effect": 0.02,
            "selection_effect": 0.015,
            "interaction_effect": -0.005,
        }
        result = _attribution_bar_svg(attr)
        assert "<svg" in result
        assert "</svg>" in result
        assert "配置效应" in result
        assert "选择效应" in result
        assert "交互效应" in result

    def test_all_positive(self):
        attr = {
            "allocation_effect": 0.01,
            "selection_effect": 0.02,
            "interaction_effect": 0.005,
        }
        result = _attribution_bar_svg(attr)
        assert "<svg" in result

    def test_all_negative(self):
        attr = {
            "allocation_effect": -0.01,
            "selection_effect": -0.02,
            "interaction_effect": -0.005,
        }
        result = _attribution_bar_svg(attr)
        assert "<svg" in result

    def test_custom_dimensions(self):
        result = _attribution_bar_svg(
            {"allocation_effect": 0.01, "selection_effect": 0.02, "interaction_effect": 0.0},
            width=500, height=180,
        )
        assert 'viewBox="0 0 500 180"' in result
