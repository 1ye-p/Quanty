"""cquant.core.toml_config — TOML 配置文件加载工具。

从 configs/defaults/*.toml 加载默认配置，供 CLI 和引擎使用。
优先级：命令行参数 > 环境变量 > TOML 配置文件 > 代码硬编码默认值。
"""
from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 项目根目录（从此文件位置向上推导：core -> cquant -> python -> project_root）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_DIR = _PROJECT_ROOT / "configs" / "defaults"


def load_toml_defaults(
    config_name: str,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """从 configs/defaults/{config_name}.toml 加载配置。

    参数
    ----
    config_name:
        配置文件名（不含 .toml 后缀），例如 "backtest"。
    config_dir:
        配置目录路径，默认为项目根目录下的 configs/defaults/。

    返回
    ----
    配置字典，文件不存在或解析失败时返回空字典。
    """
    dir_path = config_dir or _DEFAULT_CONFIG_DIR
    config_path = dir_path / f"{config_name}.toml"

    if not config_path.exists():
        logger.debug("配置文件不存在：%s", config_path)
        return {}

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as exc:
        logger.warning("加载配置文件 %s 失败：%s", config_path, exc)
        return {}


def get_backtest_defaults() -> dict[str, Any]:
    """获取回测引擎的扁平化默认参数。

    从 backtest.toml 中提取常用参数，方便 CLI 的 argparse 使用。
    所有字段均有安全的后备默认值。
    """
    config = load_toml_defaults("backtest")
    if not config:
        return {}

    engine = config.get("engine", {})
    portfolio = config.get("portfolio", {})
    costs = config.get("costs", {})
    commission = costs.get("commission", {})
    stamp_duty = costs.get("stamp_duty", {})
    slippage = costs.get("slippage", {})

    return {
        "initial_cash": float(engine.get("initial_cash", 1_000_000.0)),
        "bar_frequency": engine.get("bar_frequency", "1d"),
        "allow_short": bool(engine.get("allow_short", False)),
        "max_gross_leverage": float(engine.get("max_gross_leverage", 1.0)),
        "benchmark": portfolio.get("benchmark", ""),
        "cash_reserve_ratio": float(portfolio.get("cash_reserve_ratio", 0.01)),
        "commission_rate": float(commission.get("rate", 0.0003)),
        "commission_minimum": float(commission.get("minimum_per_order", 5.0)),
        "stamp_duty_rate": float(stamp_duty.get("rate", 0.001)),
        "slippage_rate": float(slippage.get("rate", 0.0001)),
    }
