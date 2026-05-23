"""cquant.qlib_bridge._compat — Qlib 可用性检测与降级工具。

提供 QLIB_AVAILABLE 标志和路由工具函数，使 cQuant 在 Qlib 不可用时
优雅降级到原生实现，而不是崩溃。
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

try:
    import qlib  # noqa: F401
    QLIB_AVAILABLE: bool = True
    logger.debug("Qlib %s 可用", qlib.__version__)
except ImportError:
    QLIB_AVAILABLE = False
    logger.debug("Qlib 不可用，将使用 cQuant 原生实现")

T = TypeVar("T")


def require_qlib() -> None:
    """检查 Qlib 是否可用，不可用时抛出 ImportError。"""
    if not QLIB_AVAILABLE:
        raise ImportError(
            "Qlib 未安装。请按以下步骤安装：\n"
            "  git submodule update --init lib/qlib\n"
            "  conda run -n cQuanty pip install -e lib/qlib --no-deps"
        )


def qlib_or_fallback(
    qlib_fn: Callable[[], T],
    fallback_fn: Callable[[], T],
) -> T:
    """根据 QLIB_AVAILABLE 自动路由到 Qlib 实现或 cQuant 原生实现。

    Parameters
    ----------
    qlib_fn:
        Qlib 实现（无参数 callable）。
    fallback_fn:
        cQuant 原生实现（Qlib 不可用时调用）。
    """
    if QLIB_AVAILABLE:
        return qlib_fn()
    return fallback_fn()
