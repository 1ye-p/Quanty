"""Tests for qlib_bridge QuantDB storage backends (pg_storage, provider, init)."""
from __future__ import annotations

import pytest

from cquant.qlib_bridge._compat import QLIB_AVAILABLE


# ---------------------------------------------------------------------------
# TestTickerConversion
# ---------------------------------------------------------------------------

class TestTickerConversion:
    """Test _ticker_to_sec_id and _sec_id_to_ticker helpers."""

    def test_ticker_to_sec_id_sz(self) -> None:
        from cquant.qlib_bridge.pg_storage import _ticker_to_sec_id
        assert _ticker_to_sec_id("000001.SZ") == "000001.XSHE"

    def test_ticker_to_sec_id_sh(self) -> None:
        from cquant.qlib_bridge.pg_storage import _ticker_to_sec_id
        assert _ticker_to_sec_id("600000.SH") == "600000.XSHG"

    def test_sec_id_to_ticker_xshe(self) -> None:
        from cquant.qlib_bridge.pg_storage import _sec_id_to_ticker
        assert _sec_id_to_ticker("000001.XSHE") == "000001.SZ"

    def test_sec_id_to_ticker_xshg(self) -> None:
        from cquant.qlib_bridge.pg_storage import _sec_id_to_ticker
        assert _sec_id_to_ticker("600000.XSHG") == "600000.SH"

    def test_roundtrip_ticker_to_sec_and_back(self) -> None:
        from cquant.qlib_bridge.pg_storage import _ticker_to_sec_id, _sec_id_to_ticker
        for ticker in ("000001.SZ", "600000.SH", "300750.SZ", "688981.SH"):
            assert _sec_id_to_ticker(_ticker_to_sec_id(ticker)) == ticker

    def test_roundtrip_sec_to_ticker_and_back(self) -> None:
        from cquant.qlib_bridge.pg_storage import _ticker_to_sec_id, _sec_id_to_ticker
        for sec_id in ("000001.XSHE", "600000.XSHG", "300750.XSHE", "688981.XSHG"):
            assert _ticker_to_sec_id(_sec_id_to_ticker(sec_id)) == sec_id

    def test_ticker_to_sec_id_invalid_format(self) -> None:
        from cquant.qlib_bridge.pg_storage import _ticker_to_sec_id
        with pytest.raises(ValueError, match="Invalid ticker format"):
            _ticker_to_sec_id("000001")

    def test_ticker_to_sec_id_unknown_suffix(self) -> None:
        from cquant.qlib_bridge.pg_storage import _ticker_to_sec_id
        with pytest.raises(ValueError, match="Unknown exchange suffix"):
            _ticker_to_sec_id("000001.HK")

    def test_sec_id_to_ticker_invalid_format(self) -> None:
        from cquant.qlib_bridge.pg_storage import _sec_id_to_ticker
        with pytest.raises(ValueError, match="Invalid sec_id format"):
            _sec_id_to_ticker("000001")

    def test_sec_id_to_ticker_unknown_suffix(self) -> None:
        from cquant.qlib_bridge.pg_storage import _sec_id_to_ticker
        with pytest.raises(ValueError, match="Unknown Qlib suffix"):
            _sec_id_to_ticker("000001.XLON")

    def test_case_insensitive_suffix(self) -> None:
        from cquant.qlib_bridge.pg_storage import _ticker_to_sec_id
        assert _ticker_to_sec_id("000001.sz") == "000001.XSHE"
        assert _ticker_to_sec_id("600000.sh") == "600000.XSHG"


# ---------------------------------------------------------------------------
# TestStorageInit
# ---------------------------------------------------------------------------

class TestStorageInit:
    """Test that storage classes can be imported and have expected attributes."""

    @pytest.mark.skipif(not QLIB_AVAILABLE, reason="qlib not installed")
    def test_calendar_storage_importable(self) -> None:
        from cquant.qlib_bridge.pg_storage import QuantDBCalendarStorage
        assert QuantDBCalendarStorage is not None

    @pytest.mark.skipif(not QLIB_AVAILABLE, reason="qlib not installed")
    def test_instrument_storage_importable(self) -> None:
        from cquant.qlib_bridge.pg_storage import QuantDBInstrumentStorage
        assert QuantDBInstrumentStorage is not None

    @pytest.mark.skipif(not QLIB_AVAILABLE, reason="qlib not installed")
    def test_feature_storage_importable(self) -> None:
        from cquant.qlib_bridge.pg_storage import QuantDBFeatureStorage
        assert QuantDBFeatureStorage is not None

    @pytest.mark.skipif(not QLIB_AVAILABLE, reason="qlib not installed")
    def test_provider_classes_importable(self) -> None:
        from cquant.qlib_bridge.provider import (
            QuantDBCalendarProvider,
            QuantDBFeatureProvider,
            QuantDBInstrumentProvider,
        )
        assert QuantDBCalendarProvider is not None
        assert QuantDBInstrumentProvider is not None
        assert QuantDBFeatureProvider is not None

    @pytest.mark.skipif(not QLIB_AVAILABLE, reason="qlib not installed")
    def test_init_function_importable(self) -> None:
        from cquant.qlib_bridge.init import init_qlib_with_quantdb
        assert callable(init_qlib_with_quantdb)


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------

class TestInit:
    """Test bridge __init__ exports."""

    def test_bridge_has_qlib_available(self) -> None:
        import cquant.qlib_bridge as bridge
        assert hasattr(bridge, "QLIB_AVAILABLE")
        assert isinstance(bridge.QLIB_AVAILABLE, bool)

    def test_bridge_has_require_qlib(self) -> None:
        import cquant.qlib_bridge as bridge
        assert hasattr(bridge, "require_qlib")
        assert callable(bridge.require_qlib)

    def test_bridge_has_qlib_or_fallback(self) -> None:
        import cquant.qlib_bridge as bridge
        assert hasattr(bridge, "qlib_or_fallback")
        assert callable(bridge.qlib_or_fallback)

    def test_bridge_has_init_qlib_with_quantdb(self) -> None:
        import cquant.qlib_bridge as bridge
        assert hasattr(bridge, "init_qlib_with_quantdb")
        assert callable(bridge.init_qlib_with_quantdb)

    def test_bridge_has_qlib_risk_analysis(self) -> None:
        import cquant.qlib_bridge as bridge
        assert hasattr(bridge, "qlib_risk_analysis")
        assert callable(bridge.qlib_risk_analysis)


# ---------------------------------------------------------------------------
# TestFieldMapping
# ---------------------------------------------------------------------------

class TestFieldMapping:
    """Test feature field name mapping."""

    def test_field_map_contains_ohlcv(self) -> None:
        from cquant.qlib_bridge.pg_storage import _FIELD_MAP
        assert "$open" in _FIELD_MAP
        assert "$close" in _FIELD_MAP
        assert "$high" in _FIELD_MAP
        assert "$low" in _FIELD_MAP
        assert "$volume" in _FIELD_MAP

    def test_field_map_values_are_db_columns(self) -> None:
        from cquant.qlib_bridge.pg_storage import _FIELD_MAP
        assert _FIELD_MAP["$open"] == "open"
        assert _FIELD_MAP["$close"] == "close"
        assert _FIELD_MAP["$high"] == "high"
        assert _FIELD_MAP["$low"] == "low"
        assert _FIELD_MAP["$volume"] == "volume"


# ---------------------------------------------------------------------------
# TestEvaluationBridgeFix
# ---------------------------------------------------------------------------

class TestEvaluationBridgeFix:
    """Test that evaluation.py no longer has direct qlib imports at module level."""

    def test_no_direct_qlib_import_at_module_level(self) -> None:
        import ast
        import inspect

        import cquant.factorlab.evaluation as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        top_level_imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    top_level_imports.append(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level_imports.append(alias.name)

        qlib_at_top = [m for m in top_level_imports if "qlib" in m]
        assert qlib_at_top == [], (
            f"evaluation.py has top-level qlib imports: {qlib_at_top}"
        )

    def test_risk_analysis_bridge_importable(self) -> None:
        from cquant.qlib_bridge.risk_analysis import qlib_risk_analysis
        assert callable(qlib_risk_analysis)

    def test_risk_analysis_bridge_empty_returns(self) -> None:
        import numpy as np
        from cquant.qlib_bridge.risk_analysis import qlib_risk_analysis
        result = qlib_risk_analysis(np.array([]))
        assert result is None
