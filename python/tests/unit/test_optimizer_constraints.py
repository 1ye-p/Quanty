"""Tests for ConstraintConfig validation and optimizer integration."""

from __future__ import annotations

import numpy as np
import pytest

from cquant.portfolio_opt.constraints import (
    ConstraintConfig,
    FactorExposureLimit,
    SectorLimit,
)
from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer


# ── ConstraintConfig validation ──────────────────────────────────────────────


class TestSectorLimit:
    def test_valid(self):
        sl = SectorLimit(min_weight=0.1, max_weight=0.5)
        assert sl.min_weight == 0.1
        assert sl.max_weight == 0.5

    def test_min_exceeds_max_raises(self):
        with pytest.raises(ValueError, match="min_weight .* cannot exceed"):
            SectorLimit(min_weight=0.6, max_weight=0.3)

    def test_negative_min_raises(self):
        with pytest.raises(ValueError, match="min_weight must be >= 0"):
            SectorLimit(min_weight=-0.1)

    def test_max_over_one_raises(self):
        with pytest.raises(ValueError, match="max_weight must be <= 1"):
            SectorLimit(max_weight=1.5)


class TestFactorExposureLimit:
    def test_valid(self):
        fl = FactorExposureLimit(min_exposure=-0.3, max_exposure=0.3)
        assert fl.min_exposure == -0.3

    def test_min_exceeds_max_raises(self):
        with pytest.raises(ValueError, match="min_exposure .* cannot exceed"):
            FactorExposureLimit(min_exposure=0.5, max_exposure=-0.5)


class TestConstraintConfigValidate:
    def test_default_config_valid(self):
        cfg = ConstraintConfig()
        assert cfg.validate() == []

    def test_weight_bounds_valid(self):
        cfg = ConstraintConfig(min_weight=0.05, max_weight=0.4)
        assert cfg.validate() == []

    def test_min_weight_over_max_weight(self):
        cfg = ConstraintConfig(min_weight=0.5, max_weight=0.3)
        errors = cfg.validate()
        assert any("min_weight" in e and "cannot exceed" in e for e in errors)

    def test_max_weight_over_one(self):
        cfg = ConstraintConfig(max_weight=1.5)
        errors = cfg.validate()
        assert any("max_weight" in e for e in errors)

    def test_negative_min_weight(self):
        cfg = ConstraintConfig(min_weight=-0.1)
        errors = cfg.validate()
        assert any("min_weight" in e for e in errors)

    def test_per_asset_bounds_valid(self):
        cfg = ConstraintConfig(
            min_weights={"A": 0.05},
            max_weights={"A": 0.3},
        )
        assert cfg.validate() == []

    def test_per_asset_min_over_max(self):
        cfg = ConstraintConfig(
            min_weights={"A": 0.5},
            max_weights={"A": 0.3},
        )
        errors = cfg.validate()
        assert any("min_weights" in e for e in errors)

    def test_per_asset_out_of_range(self):
        cfg = ConstraintConfig(min_weights={"A": 1.5})
        errors = cfg.validate()
        assert any("min_weights" in e for e in errors)

    def test_negative_max_turnover(self):
        cfg = ConstraintConfig(max_turnover=-0.1)
        errors = cfg.validate()
        assert any("max_turnover" in e for e in errors)

    def test_negative_turnover_penalty(self):
        cfg = ConstraintConfig(turnover_penalty=-1.0)
        errors = cfg.validate()
        assert any("turnover_penalty" in e for e in errors)

    def test_sector_limit_valid(self):
        cfg = ConstraintConfig(
            sector_limits={"银行": SectorLimit(min_weight=0.1, max_weight=0.4)}
        )
        assert cfg.validate() == []

    def test_sector_limit_invalid(self):
        with pytest.raises(ValueError, match="min_weight .* cannot exceed"):
            SectorLimit(min_weight=0.5, max_weight=0.3)

    def test_factor_limit_valid(self):
        cfg = ConstraintConfig(
            factor_limits={"momentum": FactorExposureLimit(min_exposure=-0.2, max_exposure=0.2)}
        )
        assert cfg.validate() == []

    def test_factor_limit_invalid(self):
        with pytest.raises(ValueError, match="min_exposure .* cannot exceed"):
            FactorExposureLimit(min_exposure=0.5, max_exposure=-0.5)

    def test_negative_tracking_error(self):
        cfg = ConstraintConfig(max_tracking_error=-0.01)
        errors = cfg.validate()
        assert any("max_tracking_error" in e for e in errors)


class TestConstraintConfigExclusion:
    def test_explicit_exclude(self):
        cfg = ConstraintConfig(exclude_assets={"A", "B"})
        assert cfg.get_excluded_assets() == {"A", "B"}

    def test_exclude_st(self):
        cfg = ConstraintConfig(
            exclude_st=True,
            st_assets={"ST_A", "ST_B"},
            exclude_assets={"C"},
        )
        excluded = cfg.get_excluded_assets()
        assert excluded == {"ST_A", "ST_B", "C"}

    def test_exclude_suspended(self):
        cfg = ConstraintConfig(
            exclude_suspended=True,
            suspended_assets={"SUSP_1"},
        )
        assert cfg.get_excluded_assets() == {"SUSP_1"}

    def test_exclude_combined(self):
        cfg = ConstraintConfig(
            exclude_st=True,
            st_assets={"ST_X"},
            exclude_suspended=True,
            suspended_assets={"SUSP_Y"},
            exclude_assets={"Z"},
        )
        assert cfg.get_excluded_assets() == {"ST_X", "SUSP_Y", "Z"}

    def test_no_exclusion(self):
        cfg = ConstraintConfig()
        assert cfg.get_excluded_assets() == set()


# ── MeanVarianceOptimizer with constraints ───────────────────────────────────


def _sample_data():
    """Return a small 3-asset dataset for testing."""
    expected_returns = {"A": 0.10, "B": 0.12, "C": 0.08}
    covariance = {
        "A": {"A": 0.04, "B": 0.006, "C": 0.002},
        "B": {"A": 0.006, "B": 0.09, "C": 0.009},
        "C": {"A": 0.002, "B": 0.009, "C": 0.01},
    }
    return expected_returns, covariance


class TestMVOWithConstraintConfig:
    def test_basic_optimize(self):
        ret, cov = _sample_data()
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6
        assert result.expected_return > 0

    def test_with_constraint_config(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(max_weight=0.5)
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        for w in result.weights.values():
            assert w <= 0.5 + 1e-6

    def test_asset_exclusion(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(exclude_assets={"C"})
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        assert result.weights.get("C", 0.0) == 0.0
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6

    def test_st_exclusion(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(exclude_st=True, st_assets={"B"})
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        assert result.weights.get("B", 0.0) == 0.0

    def test_sector_limit(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(
            sector_map={"A": "bank", "B": "bank", "C": "tech"},
            sector_limits={
                "bank": SectorLimit(min_weight=0.0, max_weight=0.4),
            },
        )
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        bank_weight = result.weights["A"] + result.weights["B"]
        assert bank_weight <= 0.4 + 1e-4

    def test_sector_limit_min(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(
            sector_map={"A": "tech", "B": "tech", "C": "bank"},
            sector_limits={
                "tech": SectorLimit(min_weight=0.5, max_weight=1.0),
            },
        )
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        tech_weight = result.weights["A"] + result.weights["B"]
        assert tech_weight >= 0.5 - 1e-4

    def test_factor_exposure_limit(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(
            factor_loadings={
                "A": {"momentum": 0.8},
                "B": {"momentum": 0.5},
                "C": {"momentum": -0.3},
            },
            factor_limits={
                "momentum": FactorExposureLimit(min_exposure=-0.1, max_exposure=0.3),
            },
        )
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        exposure = (
            result.weights["A"] * 0.8
            + result.weights["B"] * 0.5
            + result.weights["C"] * (-0.3)
        )
        assert exposure >= -0.1 - 1e-3
        assert exposure <= 0.3 + 1e-3

    def test_tracking_error_budget(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(
            max_tracking_error=0.05,
            benchmark_weights={"A": 0.5, "B": 0.3, "C": 0.2},
        )
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        # Verify optimizer runs without error; weights sum to 1
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6

    def test_max_turnover(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(
            current_weights={"A": 0.4, "B": 0.35, "C": 0.25},
            max_turnover=0.3,
            turnover_penalty=0.01,
        )
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        turnover = result.metadata.get("turnover", 0)
        assert turnover <= 0.3 + 1e-4

    def test_legacy_dict_still_works(self):
        ret, cov = _sample_data()
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints={"max_weight": 0.6})
        for w in result.weights.values():
            assert w <= 0.6 + 1e-6

    def test_invalid_constraints_raises(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(min_weight=0.8, max_weight=0.3)
        opt = MeanVarianceOptimizer()
        with pytest.raises(ValueError, match="Invalid constraints"):
            opt.optimize(ret, cov, constraints=cfg)

    def test_target_return(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(target_return=0.10)
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        assert abs(result.expected_return - 0.10) < 0.01

    def test_per_asset_bounds(self):
        ret, cov = _sample_data()
        cfg = ConstraintConfig(
            min_weights={"A": 0.2},
            max_weights={"A": 0.5},
        )
        opt = MeanVarianceOptimizer()
        result = opt.optimize(ret, cov, constraints=cfg)
        assert result.weights["A"] >= 0.2 - 1e-6
        assert result.weights["A"] <= 0.5 + 1e-6
