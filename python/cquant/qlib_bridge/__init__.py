"""cquant.qlib_bridge — cQuant 对 Qlib 的封装层（唯一出口）。

所有需要使用 Qlib 功能的模块，只导入此包，不直接 import qlib。
"""
from __future__ import annotations

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback, require_qlib


def __getattr__(name: str):
    """延迟导入 CQuantDataHandler 和 QlibEvaluator（避免循环导入）。"""
    if name == "CQuantDataHandler":
        from cquant.qlib_bridge.data_handler import CQuantDataHandler
        return CQuantDataHandler
    if name == "QlibEvaluator":
        from cquant.qlib_bridge.evaluator import QlibEvaluator
        return QlibEvaluator
    raise AttributeError(f"module 'cquant.qlib_bridge' has no attribute {name!r}")


__all__ = [
    "QLIB_AVAILABLE",
    "qlib_or_fallback",
    "require_qlib",
    "CQuantDataHandler",
    "QlibEvaluator",
]
