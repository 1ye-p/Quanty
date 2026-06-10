"""cquant.qlib_bridge — cQuant 对 Qlib 的封装层（唯一出口）。

所有需要使用 Qlib 功能的模块，只导入此包，不直接 import qlib。
"""
from __future__ import annotations

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback, require_qlib


def __getattr__(name: str):
    """延迟导入（避免循环导入）。"""
    if name == "CQuantDataHandler":
        from cquant.qlib_bridge.data_handler import CQuantDataHandler
        return CQuantDataHandler
    if name == "QlibEvaluator":
        from cquant.qlib_bridge.evaluator import QlibEvaluator
        return QlibEvaluator
    if name == "RollingConfig":
        from cquant.qlib_bridge.ml_rolling import RollingConfig
        return RollingConfig
    if name == "generate_rolling_splits":
        from cquant.qlib_bridge.ml_rolling import generate_rolling_splits
        return generate_rolling_splits
    if name == "ensemble_fold_predictions":
        from cquant.qlib_bridge.ml_rolling import ensemble_fold_predictions
        return ensemble_fold_predictions
    if name == "init_qlib_with_quantdb":
        from cquant.qlib_bridge.init import init_qlib_with_quantdb
        return init_qlib_with_quantdb
    if name == "qlib_risk_analysis":
        from cquant.qlib_bridge.risk_analysis import qlib_risk_analysis
        return qlib_risk_analysis
    if name == "StorageFactory":
        from cquant.qlib_bridge.storage_factory import StorageFactory
        return StorageFactory
    if name == "compute_factors_qlib":
        from cquant.qlib_bridge.factor_bridge import compute_factors_qlib
        return compute_factors_qlib
    if name == "train_model_qlib":
        from cquant.qlib_bridge.ml_bridge import train_model_qlib
        return train_model_qlib
    if name == "run_backtest_qlib":
        from cquant.qlib_bridge.backtest_bridge import run_backtest_qlib
        return run_backtest_qlib
    if name == "predict":
        from cquant.qlib_bridge.prediction_bridge import predict
        return predict
    raise AttributeError(f"module 'cquant.qlib_bridge' has no attribute {name!r}")


__all__ = [
    "QLIB_AVAILABLE",
    "qlib_or_fallback",
    "require_qlib",
    "CQuantDataHandler",
    "QlibEvaluator",
    "RollingConfig",
    "generate_rolling_splits",
    "ensemble_fold_predictions",
    "init_qlib_with_quantdb",
    "qlib_risk_analysis",
    "StorageFactory",
    "compute_factors_qlib",
    "train_model_qlib",
    "run_backtest_qlib",
    "predict",
]
