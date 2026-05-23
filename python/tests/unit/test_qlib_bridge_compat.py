"""测试 qlib_bridge 可用性检测与降级工具。"""
from __future__ import annotations

import pytest


class TestQlibAvailability:
    def test_qlib_available_is_bool(self) -> None:
        from cquant.qlib_bridge._compat import QLIB_AVAILABLE
        assert isinstance(QLIB_AVAILABLE, bool)

    def test_qlib_available_is_true_when_installed(self) -> None:
        from cquant.qlib_bridge._compat import QLIB_AVAILABLE
        assert QLIB_AVAILABLE is True

    def test_require_qlib_passes_when_available(self) -> None:
        from cquant.qlib_bridge._compat import QLIB_AVAILABLE, require_qlib
        if QLIB_AVAILABLE:
            require_qlib()  # 不应抛出

    def test_qlib_or_fallback_uses_qlib_when_available(self) -> None:
        from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback
        result = qlib_or_fallback(lambda: "qlib", lambda: "fallback")
        if QLIB_AVAILABLE:
            assert result == "qlib"
        else:
            assert result == "fallback"

    def test_qlib_or_fallback_return_type(self) -> None:
        from cquant.qlib_bridge._compat import qlib_or_fallback
        result = qlib_or_fallback(lambda: 42, lambda: 0)
        assert isinstance(result, int)

    def test_bridge_package_importable(self) -> None:
        import cquant.qlib_bridge as bridge
        assert hasattr(bridge, "QLIB_AVAILABLE")
        assert hasattr(bridge, "require_qlib")
        assert hasattr(bridge, "qlib_or_fallback")
