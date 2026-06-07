"""Tests for qlib_bridge routing: StorageFactory, DuckDB storage, and fallback behavior."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import polars as pl
import pytest

from cquant.qlib_bridge._compat import QLIB_AVAILABLE


# ---------------------------------------------------------------------------
# StorageFactory tests
# ---------------------------------------------------------------------------

class TestStorageFactory:
    """Tests for StorageFactory."""

    def test_valid_sources(self):
        """StorageFactory accepts all valid data sources."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        for source in ("quantdb", "duckdb", "tushare", "akshare"):
            catalog = MagicMock()
            token = "test_token" if source == "tushare" else None
            factory = StorageFactory(
                data_source=source,
                catalog=catalog,
                tushare_token=token,
            )
            assert factory.data_source == source

    def test_invalid_source_raises(self):
        """StorageFactory raises ValueError for invalid source."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        with pytest.raises(ValueError, match="Invalid data_source"):
            StorageFactory(data_source="invalid_source")

    def test_env_var_fallback(self):
        """StorageFactory falls back to CQUANT_QLIB_DATA_SOURCE env var."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        with patch.dict(os.environ, {"CQUANT_QLIB_DATA_SOURCE": "akshare"}):
            factory = StorageFactory(akshare_enabled=True)
            assert factory.data_source == "akshare"

    def test_default_source(self):
        """StorageFactory defaults to 'quantdb'."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        factory = StorageFactory(catalog=MagicMock())
        assert factory.data_source == "quantdb"

    def test_duckdb_requires_catalog(self):
        """StorageFactory raises ValueError when catalog is None for duckdb source."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        factory = StorageFactory(data_source="duckdb", catalog=None)
        with pytest.raises(ValueError, match="Catalog is required"):
            factory.create_calendar_storage()

    def test_tushare_requires_token(self):
        """StorageFactory raises ValueError when token is empty for tushare source."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        factory = StorageFactory(data_source="tushare", tushare_token="")
        with pytest.raises(ValueError, match="Tushare token is required"):
            factory.create_calendar_storage()

    def test_create_calendar_storage(self):
        """StorageFactory creates calendar storage for each source."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        # DuckDB/QuantDB source
        catalog = MagicMock()
        factory = StorageFactory(data_source="quantdb", catalog=catalog)
        with patch("cquant.qlib_bridge.duckdb_storage.DuckDBCalendarStorage") as mock_cls:
            factory.create_calendar_storage(freq="day", future=False)
            mock_cls.assert_called_once_with(freq="day", future=False, catalog=catalog)

    def test_create_instrument_storage(self):
        """StorageFactory creates instrument storage."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        catalog = MagicMock()
        factory = StorageFactory(data_source="quantdb", catalog=catalog)
        with patch("cquant.qlib_bridge.duckdb_storage.DuckDBInstrumentStorage") as mock_cls:
            factory.create_instrument_storage(market="all", freq="day")
            mock_cls.assert_called_once_with(market="all", freq="day", catalog=catalog)

    def test_create_feature_storage(self):
        """StorageFactory creates feature storage."""
        from cquant.qlib_bridge.storage_factory import StorageFactory

        catalog = MagicMock()
        factory = StorageFactory(data_source="quantdb", catalog=catalog)
        with patch("cquant.qlib_bridge.duckdb_storage.DuckDBFeatureStorage") as mock_cls:
            factory.create_feature_storage(instrument="000001.XSHE", field="$close", freq="day")
            mock_cls.assert_called_once_with(
                instrument="000001.XSHE", field="$close", freq="day", catalog=catalog
            )


# ---------------------------------------------------------------------------
# DuckDB storage tests (using mock Catalog)
# ---------------------------------------------------------------------------

class TestDuckDBStorage:
    """Tests for DuckDB storage backends."""

    @pytest.fixture
    def mock_catalog(self):
        """Create a mock Catalog."""
        catalog = MagicMock()
        return catalog

    def test_duckdb_calendar_storage_init(self, mock_catalog):
        """DuckDBCalendarStorage initializes correctly."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBCalendarStorage

        storage = DuckDBCalendarStorage(freq="day", future=False, catalog=mock_catalog)
        assert storage.freq == "day"
        assert storage.future is False

    def test_duckdb_instrument_storage_init(self, mock_catalog):
        """DuckDBInstrumentStorage initializes correctly."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBInstrumentStorage

        storage = DuckDBInstrumentStorage(market="all", freq="day", catalog=mock_catalog)
        assert storage.market == "all"
        assert storage.freq == "day"

    def test_duckdb_feature_storage_init(self, mock_catalog):
        """DuckDBFeatureStorage initializes correctly."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBFeatureStorage

        storage = DuckDBFeatureStorage(
            instrument="000001.XSHE", field="$close", freq="day", catalog=mock_catalog
        )
        assert storage.instrument == "000001.XSHE"
        assert storage.field == "$close"

    def test_duckdb_calendar_loads_data(self, mock_catalog):
        """DuckDBCalendarStorage loads calendar data from catalog."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBCalendarStorage

        # Mock catalog query response
        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [
            {"trade_date": "2024-01-02"},
            {"trade_date": "2024-01-03"},
            {"trade_date": "2024-01-04"},
        ]
        mock_catalog.query.return_value = mock_df

        storage = DuckDBCalendarStorage(freq="day", future=False, catalog=mock_catalog)
        data = storage.data

        assert len(data) == 3
        assert data[0] == "2024-01-02"
        assert data[2] == "2024-01-04"
        mock_catalog.query.assert_called_once()

    def test_duckdb_calendar_caches_data(self, mock_catalog):
        """DuckDBCalendarStorage caches calendar data."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBCalendarStorage

        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [{"trade_date": "2024-01-02"}]
        mock_catalog.query.return_value = mock_df

        storage = DuckDBCalendarStorage(freq="day", future=False, catalog=mock_catalog)

        # Access data twice
        data1 = storage.data
        data2 = storage.data

        assert data1 == data2
        # Query should only be called once due to caching
        mock_catalog.query.assert_called_once()

    def test_duckdb_calendar_clear_resets_cache(self, mock_catalog):
        """DuckDBCalendarStorage.clear() resets cache."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBCalendarStorage

        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [{"trade_date": "2024-01-02"}]
        mock_catalog.query.return_value = mock_df

        storage = DuckDBCalendarStorage(freq="day", future=False, catalog=mock_catalog)
        _ = storage.data
        storage.clear()
        _ = storage.data

        # Query should be called twice after clear
        assert mock_catalog.query.call_count == 2

    def test_duckdb_calendar_read_only(self, mock_catalog):
        """DuckDBCalendarStorage raises on write operations."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBCalendarStorage

        storage = DuckDBCalendarStorage(freq="day", future=False, catalog=mock_catalog)

        with pytest.raises(NotImplementedError):
            storage.extend(["2024-01-05"])

        with pytest.raises(NotImplementedError):
            storage.insert(0, "2024-01-05")

        with pytest.raises(NotImplementedError):
            storage.remove("2024-01-02")

    def test_duckdb_instrument_loads_data(self, mock_catalog):
        """DuckDBInstrumentStorage loads instrument data from catalog."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBInstrumentStorage

        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [
            {"asset_id": "000001.SZ", "start_date": "2020-01-01", "end_date": "2024-12-31"},
            {"asset_id": "600000.SH", "start_date": "2019-01-01", "end_date": "2024-12-31"},
        ]
        mock_catalog.query.return_value = mock_df

        storage = DuckDBInstrumentStorage(market="all", freq="day", catalog=mock_catalog)
        data = storage.data

        assert len(data) == 2
        assert "000001.XSHE" in data
        assert "600000.XSHG" in data

    def test_duckdb_feature_loads_data(self, mock_catalog):
        """DuckDBFeatureStorage loads feature data from catalog."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBFeatureStorage

        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_col = MagicMock()
        mock_col.to_numpy.return_value = np.array([10.0, 10.5, 11.0], dtype=np.float32)
        mock_df.__getitem__ = MagicMock(return_value=mock_col)
        mock_catalog.query.return_value = mock_df

        storage = DuckDBFeatureStorage(
            instrument="000001.XSHE", field="$close", freq="day", catalog=mock_catalog
        )
        series = storage.data

        assert len(series) == 3
        assert series.iloc[0] == 10.0
        assert series.iloc[2] == 11.0

    def test_duckdb_feature_empty_result(self, mock_catalog):
        """DuckDBFeatureStorage handles empty query result."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBFeatureStorage

        mock_df = MagicMock()
        mock_df.is_empty.return_value = True
        mock_catalog.query.return_value = mock_df

        storage = DuckDBFeatureStorage(
            instrument="000001.XSHE", field="$close", freq="day", catalog=mock_catalog
        )
        series = storage.data

        assert len(series) == 0

    def test_duckdb_feature_unknown_field(self, mock_catalog):
        """DuckDBFeatureStorage raises ValueError for unknown field."""
        if not QLIB_AVAILABLE:
            pytest.skip("Qlib not available")

        from cquant.qlib_bridge.duckdb_storage import DuckDBFeatureStorage

        storage = DuckDBFeatureStorage(
            instrument="000001.XSHE", field="$unknown", freq="day", catalog=mock_catalog
        )
        with pytest.raises(ValueError, match="Unknown field"):
            storage._resolve_column()


# ---------------------------------------------------------------------------
# Fallback behavior tests
# ---------------------------------------------------------------------------

class TestFallbackBehavior:
    """Tests for fallback behavior when Qlib is not available."""

    def test_factor_bridge_fallback(self):
        """compute_factors_qlib falls back to native when Qlib unavailable."""
        from cquant.qlib_bridge.factor_bridge import compute_factors_qlib

        prices = pl.DataFrame({
            "asset_id": ["000001.SZ"] * 5,
            "trade_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "open": [10.0, 10.5, 11.0, 10.8, 11.2],
            "high": [10.5, 11.0, 11.5, 11.2, 11.5],
            "low": [9.8, 10.2, 10.8, 10.5, 10.9],
            "close": [10.3, 10.8, 11.2, 10.9, 11.3],
            "volume": [1000, 1200, 1100, 900, 1300],
        })

        result = compute_factors_qlib(prices, use_qlib=False)

        assert "asset_id" in result.columns
        assert "trade_date" in result.columns
        assert len(result) == 5

    def test_ml_bridge_fallback(self):
        """train_model_qlib falls back to native when Qlib unavailable."""
        from cquant.qlib_bridge.ml_bridge import train_model_qlib

        np.random.seed(42)
        n_samples = 100
        train_data = pl.DataFrame({
            "feature_1": np.random.randn(n_samples).tolist(),
            "feature_2": np.random.randn(n_samples).tolist(),
            "label": np.random.randn(n_samples).tolist(),
        })
        valid_data = pl.DataFrame({
            "feature_1": np.random.randn(20).tolist(),
            "feature_2": np.random.randn(20).tolist(),
            "label": np.random.randn(20).tolist(),
        })

        result = train_model_qlib(
            train_data=train_data,
            valid_data=valid_data,
            feature_names=["feature_1", "feature_2"],
            target_name="label",
            model_type="lgbm",
            use_qlib=False,
        )

        assert result.backend.startswith("native")
        assert "mse" in result.metrics
        assert "rmse" in result.metrics
        assert "r2" in result.metrics

    def test_backtest_bridge_fallback(self):
        """run_backtest_qlib falls back to native when Qlib unavailable."""
        from cquant.qlib_bridge.backtest_bridge import run_backtest_qlib

        prices = pl.DataFrame({
            "asset_id": ["000001.SZ"] * 5 + ["000002.SZ"] * 5,
            "trade_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"] * 2,
            "open": [10.0, 10.5, 11.0, 10.8, 11.2, 20.0, 20.5, 21.0, 20.8, 21.2],
            "high": [10.5, 11.0, 11.5, 11.2, 11.5, 20.5, 21.0, 21.5, 21.2, 21.5],
            "low": [9.8, 10.2, 10.8, 10.5, 10.9, 19.8, 20.2, 20.8, 20.5, 20.9],
            "close": [10.3, 10.8, 11.2, 10.9, 11.3, 20.3, 20.8, 21.2, 20.9, 21.3],
            "volume": [1000, 1200, 1100, 900, 1300, 2000, 2200, 2100, 1900, 2300],
        })

        signals = pl.DataFrame({
            "asset_id": ["000001.SZ", "000002.SZ"],
            "trade_date": ["2024-01-01", "2024-01-01"],
            "weight": [0.5, 0.5],
        })

        result = run_backtest_qlib(
            prices=prices,
            signals=signals,
            strategy_id="test",
            use_qlib=False,
        )

        assert result.backend == "native"
        assert result.strategy_id == "test"
        assert "total_return" in result.metrics

    def test_qlib_or_fallback_utility(self):
        """qlib_or_fallback routes correctly based on QLIB_AVAILABLE."""
        from cquant.qlib_bridge._compat import qlib_or_fallback

        result = qlib_or_fallback(
            qlib_fn=lambda: "qlib_result",
            fallback_fn=lambda: "native_result",
        )

        if QLIB_AVAILABLE:
            assert result == "qlib_result"
        else:
            assert result == "native_result"


# ---------------------------------------------------------------------------
# Init multi-source tests
# ---------------------------------------------------------------------------

class TestInitMultiSource:
    """Tests for multi-source initialization."""

    def test_init_with_quantdb_source(self):
        """init_qlib_with_quantdb works with quantdb source."""
        from cquant.qlib_bridge.init import init_qlib_with_quantdb

        catalog = MagicMock()

        with patch("qlib.init") as mock_init:
            init_qlib_with_quantdb(catalog=catalog, data_source="quantdb")
            mock_init.assert_called_once()

    def test_init_with_akshare_source(self):
        """init_qlib_with_quantdb works with akshare source."""
        from cquant.qlib_bridge.init import init_qlib_with_quantdb

        with patch("qlib.init") as mock_init:
            init_qlib_with_quantdb(data_source="akshare")
            mock_init.assert_called_once()

    def test_init_creates_correct_providers(self):
        """init_qlib_with_quantdb creates providers from StorageFactory."""
        from cquant.qlib_bridge.init import init_qlib_with_quantdb

        catalog = MagicMock()

        with patch("qlib.init") as mock_init:
            init_qlib_with_quantdb(catalog=catalog, data_source="quantdb", region="cn")

            call_kwargs = mock_init.call_args[1]
            assert "calendar_provider" in call_kwargs
            assert "instrument_provider" in call_kwargs
            assert "feature_provider" in call_kwargs
            assert call_kwargs["region"] == "cn"


# ---------------------------------------------------------------------------
# Bridge module import tests
# ---------------------------------------------------------------------------

class TestBridgeImports:
    """Tests that all bridge modules can be imported."""

    def test_import_storage_factory(self):
        """StorageFactory can be imported."""
        from cquant.qlib_bridge.storage_factory import StorageFactory
        assert StorageFactory is not None

    def test_import_duckdb_storage(self):
        """DuckDB storage can be imported."""
        from cquant.qlib_bridge.duckdb_storage import DuckDBCalendarStorage
        assert DuckDBCalendarStorage is not None

    def test_import_factor_bridge(self):
        """factor_bridge can be imported."""
        from cquant.qlib_bridge.factor_bridge import compute_factors_qlib
        assert compute_factors_qlib is not None

    def test_import_ml_bridge(self):
        """ml_bridge can be imported."""
        from cquant.qlib_bridge.ml_bridge import train_model_qlib
        assert train_model_qlib is not None

    def test_import_backtest_bridge(self):
        """backtest_bridge can be imported."""
        from cquant.qlib_bridge.backtest_bridge import run_backtest_qlib
        assert run_backtest_qlib is not None
