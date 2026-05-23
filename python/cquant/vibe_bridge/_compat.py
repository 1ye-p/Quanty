"""cquant.vibe_bridge._compat — Vibe-Trading 可用性检测与降级工具。

提供 VIBE_AVAILABLE 标志和路由工具函数，使 cQuant 在 Vibe-Trading
不可用时优雅降级到原生实现，而不是崩溃。
"""
from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

# vibe_bridge/ → cquant/ → python/ → quant/ = 3 parents to project root
# Then lib/vibe-trading/agent (the directory that must be on sys.path)
_VIBE_AGENT_ROOT = Path(__file__).resolve().parents[3] / "lib" / "vibe-trading" / "agent"
_VIBE_AGENT_STR = str(_VIBE_AGENT_ROOT)

VIBE_AVAILABLE: bool = False

if _VIBE_AGENT_ROOT.exists():
    if _VIBE_AGENT_STR not in sys.path:
        sys.path.insert(0, _VIBE_AGENT_STR)
    try:
        import src.factors.zoo  # noqa: F401
        VIBE_AVAILABLE = True
        logger.debug("Vibe-Trading 可用（路径：%s）", _VIBE_AGENT_ROOT)
    except ImportError as _exc:
        logger.debug("Vibe-Trading import 失败：%s", _exc)
else:
    logger.debug("Vibe-Trading agent 目录未找到（%s 不存在）", _VIBE_AGENT_ROOT)

T = TypeVar("T")


def require_vibe() -> None:
    """检查 Vibe-Trading 是否可用，不可用时抛出 ImportError。"""
    if not VIBE_AVAILABLE:
        raise ImportError(
            "Vibe-Trading 未安装。请按以下步骤安装：\n"
            "  git submodule update --init lib/vibe-trading\n"
            "  conda run -n cQuanty pip install langgraph langchain-openai"
        )


def vibe_or_fallback(
    vibe_fn: Callable[[], T],
    fallback_fn: Callable[[], T],
) -> T:
    """根据 VIBE_AVAILABLE 自动路由到 Vibe 实现或 cQuant 原生实现。"""
    if VIBE_AVAILABLE:
        return vibe_fn()
    return fallback_fn()
