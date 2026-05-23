"""TOML 配置加载层测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from cquant.core.toml_config import load_toml_defaults, get_backtest_defaults

_REPO_ROOT = Path(__file__).resolve().parents[3]


class TestLoadTomlDefaults:
    def test_loads_backtest_toml(self) -> None:
        config = load_toml_defaults("backtest", config_dir=_REPO_ROOT / "configs" / "defaults")
        assert isinstance(config, dict)
        assert "engine" in config
        assert "costs" in config

    def test_missing_file_returns_empty_dict(self) -> None:
        config = load_toml_defaults("nonexistent_config", config_dir=_REPO_ROOT / "configs" / "defaults")
        assert config == {}


class TestGetBacktestDefaults:
    def test_initial_cash_loaded_from_toml(self) -> None:
        defaults = get_backtest_defaults()
        assert "initial_cash" in defaults
        assert isinstance(defaults["initial_cash"], (int, float))
        assert defaults["initial_cash"] > 0

    def test_commission_rate_loaded(self) -> None:
        defaults = get_backtest_defaults()
        assert "commission_rate" in defaults
        assert isinstance(defaults["commission_rate"], float)

    def test_benchmark_loaded(self) -> None:
        defaults = get_backtest_defaults()
        assert "benchmark" in defaults
