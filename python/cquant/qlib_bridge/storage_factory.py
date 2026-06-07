"""cquant.qlib_bridge.storage_factory — Multi-source storage factory for Qlib.

Provides ``StorageFactory`` which creates Qlib CalendarStorage, InstrumentStorage,
and FeatureStorage instances based on the configured data source.  Supported
sources: ``quantdb`` (default, cQuant silver layer), ``duckdb``, ``tushare``,
``akshare``.

The data source is selected via the ``CQUANT_QLIB_DATA_SOURCE`` environment
variable or the ``data_source`` parameter.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, require_qlib

if QLIB_AVAILABLE:
    from qlib.data.storage import CalendarStorage, FeatureStorage, InstrumentStorage

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)

# Valid data sources
_VALID_SOURCES = frozenset({"quantdb", "duckdb", "tushare", "akshare"})

# Default source
_DEFAULT_SOURCE = "quantdb"


class StorageFactory:
    """Factory that creates Qlib storage instances from the configured data source.

    Parameters
    ----------
    data_source:
        One of ``"quantdb"``, ``"duckdb"``, ``"tushare"``, ``"akshare"``.
        Falls back to ``CQUANT_QLIB_DATA_SOURCE`` env var, then ``"quantdb"``.
    catalog:
        Initialized ``Catalog`` connection (required for ``quantdb`` / ``duckdb`` sources).
    tushare_token:
        Tushare Pro API token (required for ``tushare`` source).
    akshare_enabled:
        Whether AKShare is available (for ``akshare`` source).

    Raises
    ------
    ImportError
        If Qlib is not installed.
    ValueError
        If *data_source* is not a valid source name.
    """

    def __init__(
        self,
        data_source: str | None = None,
        catalog: "Catalog | None" = None,
        tushare_token: str | None = None,
        akshare_enabled: bool = True,
    ) -> None:
        require_qlib()

        self._data_source = (
            data_source
            or os.environ.get("CQUANT_QLIB_DATA_SOURCE", _DEFAULT_SOURCE)
        ).lower()

        if self._data_source not in _VALID_SOURCES:
            raise ValueError(
                f"Invalid data_source={self._data_source!r}; "
                f"valid sources: {sorted(_VALID_SOURCES)}"
            )

        self._catalog = catalog
        self._tushare_token = tushare_token or os.environ.get("TUSHARE_TOKEN", "")
        self._akshare_enabled = akshare_enabled

        logger.info(
            "StorageFactory: data_source=%s, catalog=%s, tushare_token=%s",
            self._data_source,
            "provided" if catalog else "None",
            "provided" if self._tushare_token else "None",
        )

    @property
    def data_source(self) -> str:
        """Current data source name."""
        return self._data_source

    def create_calendar_storage(self, freq: str = "day", future: bool = False) -> "CalendarStorage":
        """Create a CalendarStorage instance for the configured data source.

        Parameters
        ----------
        freq:
            Frequency string (e.g. ``"day"``).
        future:
            Whether to include future dates.

        Returns
        -------
        CalendarStorage
            Qlib CalendarStorage backed by the configured source.
        """
        if self._data_source in ("quantdb", "duckdb"):
            return self._create_duckdb_calendar(freq, future)
        elif self._data_source == "tushare":
            return self._create_tushare_calendar(freq, future)
        elif self._data_source == "akshare":
            return self._create_akshare_calendar(freq, future)
        else:
            raise ValueError(f"Unsupported data_source: {self._data_source}")

    def create_instrument_storage(self, market: str = "all", freq: str = "day") -> "InstrumentStorage":
        """Create an InstrumentStorage instance for the configured data source.

        Parameters
        ----------
        market:
            Market or index name (e.g. ``"csi300"``, ``"all"``).
        freq:
            Frequency string (e.g. ``"day"``).

        Returns
        -------
        InstrumentStorage
            Qlib InstrumentStorage backed by the configured source.
        """
        if self._data_source in ("quantdb", "duckdb"):
            return self._create_duckdb_instrument(market, freq)
        elif self._data_source == "tushare":
            return self._create_tushare_instrument(market, freq)
        elif self._data_source == "akshare":
            return self._create_akshare_instrument(market, freq)
        else:
            raise ValueError(f"Unsupported data_source: {self._data_source}")

    def create_feature_storage(
        self, instrument: str, field: str, freq: str = "day"
    ) -> "FeatureStorage":
        """Create a FeatureStorage instance for the configured data source.

        Parameters
        ----------
        instrument:
            Qlib sec_id (e.g. ``"000001.XSHE"``).
        field:
            Qlib field name (e.g. ``"$close"``).
        freq:
            Frequency string (e.g. ``"day"``).

        Returns
        -------
        FeatureStorage
            Qlib FeatureStorage backed by the configured source.
        """
        if self._data_source in ("quantdb", "duckdb"):
            return self._create_duckdb_feature(instrument, field, freq)
        elif self._data_source == "tushare":
            return self._create_tushare_feature(instrument, field, freq)
        elif self._data_source == "akshare":
            return self._create_akshare_feature(instrument, field, freq)
        else:
            raise ValueError(f"Unsupported data_source: {self._data_source}")

    # ------------------------------------------------------------------
    # DuckDB / QuantDB backends
    # ------------------------------------------------------------------

    def _create_duckdb_calendar(self, freq: str, future: bool) -> "CalendarStorage":
        if self._catalog is None:
            raise ValueError("Catalog is required for duckdb/quantdb data source")
        from cquant.qlib_bridge.duckdb_storage import DuckDBCalendarStorage
        return DuckDBCalendarStorage(freq=freq, future=future, catalog=self._catalog)

    def _create_duckdb_instrument(self, market: str, freq: str) -> "InstrumentStorage":
        if self._catalog is None:
            raise ValueError("Catalog is required for duckdb/quantdb data source")
        from cquant.qlib_bridge.duckdb_storage import DuckDBInstrumentStorage
        return DuckDBInstrumentStorage(market=market, freq=freq, catalog=self._catalog)

    def _create_duckdb_feature(self, instrument: str, field: str, freq: str) -> "FeatureStorage":
        if self._catalog is None:
            raise ValueError("Catalog is required for duckdb/quantdb data source")
        from cquant.qlib_bridge.duckdb_storage import DuckDBFeatureStorage
        return DuckDBFeatureStorage(instrument=instrument, field=field, freq=freq, catalog=self._catalog)

    # ------------------------------------------------------------------
    # Tushare backends
    # ------------------------------------------------------------------

    def _create_tushare_calendar(self, freq: str, future: bool) -> "CalendarStorage":
        if not self._tushare_token:
            raise ValueError("Tushare token is required for tushare data source")
        from cquant.qlib_bridge.tushare_storage import TushareCalendarStorage
        return TushareCalendarStorage(freq=freq, future=future, token=self._tushare_token)

    def _create_tushare_instrument(self, market: str, freq: str) -> "InstrumentStorage":
        if not self._tushare_token:
            raise ValueError("Tushare token is required for tushare data source")
        from cquant.qlib_bridge.tushare_storage import TushareInstrumentStorage
        return TushareInstrumentStorage(market=market, freq=freq, token=self._tushare_token)

    def _create_tushare_feature(self, instrument: str, field: str, freq: str) -> "FeatureStorage":
        if not self._tushare_token:
            raise ValueError("Tushare token is required for tushare data source")
        from cquant.qlib_bridge.tushare_storage import TushareFeatureStorage
        return TushareFeatureStorage(instrument=instrument, field=field, freq=freq, token=self._tushare_token)

    # ------------------------------------------------------------------
    # AKShare backends
    # ------------------------------------------------------------------

    def _create_akshare_calendar(self, freq: str, future: bool) -> "CalendarStorage":
        if not self._akshare_enabled:
            raise ValueError("AKShare is not enabled")
        from cquant.qlib_bridge.akshare_storage import AKShareCalendarStorage
        return AKShareCalendarStorage(freq=freq, future=future)

    def _create_akshare_instrument(self, market: str, freq: str) -> "InstrumentStorage":
        if not self._akshare_enabled:
            raise ValueError("AKShare is not enabled")
        from cquant.qlib_bridge.akshare_storage import AKShareInstrumentStorage
        return AKShareInstrumentStorage(market=market, freq=freq)

    def _create_akshare_feature(self, instrument: str, field: str, freq: str) -> "FeatureStorage":
        if not self._akshare_enabled:
            raise ValueError("AKShare is not enabled")
        from cquant.qlib_bridge.akshare_storage import AKShareFeatureStorage
        return AKShareFeatureStorage(instrument=instrument, field=field, freq=freq)
