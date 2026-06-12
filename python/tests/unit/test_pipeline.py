"""Unit tests for cquant.pipeline module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cquant.pipeline.config import PipelineConfig
from cquant.pipeline.orchestrator import PipelineOrchestrator


# ---------------------------------------------------------------------------
# PipelineConfig tests
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    """Tests for PipelineConfig defaults and customisation."""

    def test_defaults(self):
        cfg = PipelineConfig()
        assert cfg.feature_set_version == "tdx_bulk_v1"
        assert cfg.factor_names == []
        assert cfg.model_types == ["lgbm"]
        assert cfg.n_splits == 3
        assert cfg.gap_days == 5
        assert cfg.strategy_type == "ml_model"
        assert cfg.top_n == 10
        assert cfg.initial_cash == 1_000_000.0
        assert cfg.rebalance_frequency == "weekly"
        assert cfg.promotion_threshold == 0.02
        assert cfg.auto_promote is False
        assert cfg.retrain_day == 6
        assert cfg.retrain_hour == 20

    def test_custom_values(self):
        cfg = PipelineConfig(
            feature_set_version="custom_v2",
            model_types=["lgbm", "xgb"],
            n_splits=5,
            top_n=20,
            auto_promote=True,
            retrain_day=0,
            retrain_hour=9,
        )
        assert cfg.feature_set_version == "custom_v2"
        assert cfg.model_types == ["lgbm", "xgb"]
        assert cfg.n_splits == 5
        assert cfg.top_n == 20
        assert cfg.auto_promote is True
        assert cfg.retrain_day == 0
        assert cfg.retrain_hour == 9

    def test_dataclass_equality(self):
        cfg1 = PipelineConfig()
        cfg2 = PipelineConfig()
        assert cfg1 == cfg2

    def test_dataclass_repr(self):
        cfg = PipelineConfig()
        r = repr(cfg)
        assert "PipelineConfig" in r
        assert "tdx_bulk_v1" in r

    def test_factor_names_override(self):
        cfg = PipelineConfig(factor_names=["alpha001", "alpha002"])
        assert cfg.factor_names == ["alpha001", "alpha002"]


# ---------------------------------------------------------------------------
# PipelineOrchestrator tests
# ---------------------------------------------------------------------------


class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator initialisation and state."""

    def test_init_with_defaults(self):
        catalog = MagicMock()
        orch = PipelineOrchestrator(catalog)
        assert orch.config == PipelineConfig()
        assert orch.last_run is None

    def test_init_with_custom_config(self):
        catalog = MagicMock()
        cfg = PipelineConfig(top_n=20, auto_promote=True)
        orch = PipelineOrchestrator(catalog, cfg)
        assert orch.config.top_n == 20
        assert orch.config.auto_promote is True

    def test_config_property_returns_config(self):
        catalog = MagicMock()
        cfg = PipelineConfig(n_splits=7)
        orch = PipelineOrchestrator(catalog, cfg)
        assert orch.config.n_splits == 7

    def test_last_run_initially_none(self):
        catalog = MagicMock()
        orch = PipelineOrchestrator(catalog)
        assert orch.last_run is None

    def test_run_full_pipeline_returns_dict(self):
        """run_full_pipeline returns a dict with expected keys."""
        catalog = MagicMock()

        # Patch all stage methods to avoid real execution
        with patch.object(PipelineOrchestrator, "_stage_factors", return_value={"status": "success", "rows": 100}):
            with patch.object(PipelineOrchestrator, "_stage_ml", return_value={"status": "success", "model_ids": ["m1"]}):
                with patch.object(PipelineOrchestrator, "_stage_backtest", return_value={"status": "success", "run_id": "bt1"}):
                    with patch.object(PipelineOrchestrator, "_stage_analysis", return_value={"status": "success", "sharpe": 1.5}):
                        with patch.object(PipelineOrchestrator, "_stage_promotion", return_value={"status": "skipped", "reason": "auto_promote disabled"}):
                            orch = PipelineOrchestrator(catalog)
                            result = orch.run_full_pipeline()

        assert "run_id" in result
        assert "stages" in result
        assert "status" in result
        assert "started_at" in result
        assert "finished_at" in result
        assert "duration_seconds" in result
        assert result["status"] == "success"
        assert "factors" in result["stages"]
        assert "ml" in result["stages"]
        assert "backtest" in result["stages"]
        assert "analysis" in result["stages"]
        assert "promotion" in result["stages"]

    def test_run_full_pipeline_updates_last_run(self):
        """After running, last_run is populated."""
        catalog = MagicMock()

        with patch.object(PipelineOrchestrator, "_stage_factors", return_value={"status": "success"}):
            with patch.object(PipelineOrchestrator, "_stage_ml", return_value={"status": "success", "model_ids": []}):
                with patch.object(PipelineOrchestrator, "_stage_backtest", return_value={"status": "success", "run_id": ""}):
                    with patch.object(PipelineOrchestrator, "_stage_analysis", return_value={"status": "success"}):
                        with patch.object(PipelineOrchestrator, "_stage_promotion", return_value={"status": "skipped"}):
                            orch = PipelineOrchestrator(catalog)
                            assert orch.last_run is None
                            orch.run_full_pipeline()
                            assert orch.last_run is not None
                            assert orch.last_run["status"] == "success"

    def test_run_full_pipeline_detects_partial_failure(self):
        """When any stage errors, status is partial_failure."""
        catalog = MagicMock()

        with patch.object(PipelineOrchestrator, "_stage_factors", return_value={"status": "success"}):
            with patch.object(PipelineOrchestrator, "_stage_ml", return_value={"status": "error", "error": "boom"}):
                with patch.object(PipelineOrchestrator, "_stage_backtest", return_value={"status": "success", "run_id": ""}):
                    with patch.object(PipelineOrchestrator, "_stage_analysis", return_value={"status": "success"}):
                        with patch.object(PipelineOrchestrator, "_stage_promotion", return_value={"status": "skipped"}):
                            orch = PipelineOrchestrator(catalog)
                            result = orch.run_full_pipeline()
                            assert result["status"] == "partial_failure"
