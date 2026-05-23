"""cquant.vibe_bridge — cQuant 对 Vibe-Trading 的封装层（唯一出口）。

所有需要使用 Vibe-Trading 功能的模块，只导入此包，
不直接 import vibe-trading 内部模块。
"""
from __future__ import annotations

from cquant.vibe_bridge._compat import VIBE_AVAILABLE, vibe_or_fallback, require_vibe


def __getattr__(name: str):
    """延迟导入子模块（避免循环导入和启动时依赖错误）。"""
    if name == "load_zoo":
        from cquant.vibe_bridge.alpha_zoo import load_zoo
        return load_zoo
    if name == "VibeFactor":
        from cquant.vibe_bridge.alpha_zoo import VibeFactor
        return VibeFactor
    if name == "VibSwarmLoader":
        from cquant.vibe_bridge.swarm import VibSwarmLoader
        return VibSwarmLoader
    if name == "load_vibe_providers":
        from cquant.vibe_bridge.providers import load_vibe_providers
        return load_vibe_providers
    if name == "list_vibe_providers":
        from cquant.vibe_bridge.providers import list_vibe_providers
        return list_vibe_providers
    raise AttributeError(f"module 'cquant.vibe_bridge' has no attribute {name!r}")


__all__ = [
    "VIBE_AVAILABLE",
    "vibe_or_fallback",
    "require_vibe",
    "load_zoo",
    "VibeFactor",
    "VibSwarmLoader",
    "load_vibe_providers",
    "list_vibe_providers",
]
