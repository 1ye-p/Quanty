"""Unit tests for cquant.vibe_bridge._compat."""

from __future__ import annotations

from unittest.mock import patch
import pytest


class TestVibeCompat:
    def test_vibe_available_is_bool(self) -> None:
        from cquant.vibe_bridge._compat import VIBE_AVAILABLE
        assert isinstance(VIBE_AVAILABLE, bool)

    def test_require_vibe_raises_when_unavailable(self) -> None:
        from cquant.vibe_bridge._compat import require_vibe
        with patch("cquant.vibe_bridge._compat.VIBE_AVAILABLE", False):
            with pytest.raises(ImportError, match="Vibe-Trading"):
                require_vibe()

    def test_require_vibe_passes_when_available(self) -> None:
        from cquant.vibe_bridge._compat import require_vibe
        with patch("cquant.vibe_bridge._compat.VIBE_AVAILABLE", True):
            require_vibe()  # should not raise

    def test_vibe_or_fallback_uses_vibe_when_available(self) -> None:
        from cquant.vibe_bridge._compat import vibe_or_fallback
        with patch("cquant.vibe_bridge._compat.VIBE_AVAILABLE", True):
            result = vibe_or_fallback(lambda: "vibe", lambda: "fallback")
        assert result == "vibe"

    def test_vibe_or_fallback_uses_fallback_when_unavailable(self) -> None:
        from cquant.vibe_bridge._compat import vibe_or_fallback
        with patch("cquant.vibe_bridge._compat.VIBE_AVAILABLE", False):
            result = vibe_or_fallback(lambda: "vibe", lambda: "fallback")
        assert result == "fallback"

    def test_vibe_available_true_with_submodule(self) -> None:
        """Actual VIBE_AVAILABLE should be True since submodule is installed."""
        from cquant.vibe_bridge._compat import VIBE_AVAILABLE
        # With the submodule present, VIBE_AVAILABLE should be True
        assert VIBE_AVAILABLE is True, (
            "Expected VIBE_AVAILABLE=True since lib/vibe-trading/agent exists. "
            "Check sys.path setup in _compat.py."
        )

    def test_getattr_unknown_raises_attribute_error(self) -> None:
        import cquant.vibe_bridge as vb
        with pytest.raises(AttributeError):
            _ = vb.nonexistent_attr
