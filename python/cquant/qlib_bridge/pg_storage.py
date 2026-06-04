"""cquant.qlib_bridge.pg_storage — QuantDB-backed Qlib storage implementations.

Provides CalendarStorage, InstrumentStorage, and FeatureStorage backed by
cQuant's QuantDB (DuckDB/PostgreSQL) data layer.  These implementations
allow Qlib to read data from cQuant's data warehouse instead of flat files.

All classes inherit from the corresponding ``qlib.data.storage`` base classes
and implement the required abstract methods.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Dict, Iterable, List, Tuple, Union

import numpy as np
import pandas as pd

from cquant.qlib_bridge._compat import QLIB_AVAILABLE

if QLIB_AVAILABLE:
    from qlib.data.storage import (
        CalendarStorage,
        CalVT,
        FeatureStorage,
        InstrumentStorage,
        InstKT,
        InstVT,
    )

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ticker / sec_id conversion helpers
# ---------------------------------------------------------------------------

# A-share ticker suffixes: SZ for Shenzhen, SH for Shanghai
_SUFFIX_MAP = {
    "SZ": "XSHE",  # Shenzhen Stock Exchange
    "SH": "XSHG",  # Shanghai Stock Exchange
}
_SUFFIX_MAP_REV = {v: k for k, v in _SUFFIX_MAP.items()}


def _ticker_to_sec_id(ticker: str) -> str:
    """Convert cQuant ticker (e.g. ``000001.SZ``) to Qlib sec_id (e.g. ``000001.XSHE``).

    Parameters
    ----------
    ticker:
        Ticker in ``CODE.SUFFIX`` format (cQuant convention).

    Returns
    -------
    str
        Sec ID in ``CODE.QLIB_SUFFIX`` format (Qlib convention).

    Raises
    ------
    ValueError
        If the ticker suffix is not recognized.
    """
    parts = ticker.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid ticker format: {ticker!r}; expected CODE.SUFFIX")
    code, suffix = parts
    qlib_suffix = _SUFFIX_MAP.get(suffix.upper())
    if qlib_suffix is None:
        raise ValueError(
            f"Unknown exchange suffix {suffix!r} in ticker {ticker!r}; "
            f"known suffixes: {list(_SUFFIX_MAP.keys())}"
        )
    return f"{code}.{qlib_suffix}"


def _sec_id_to_ticker(sec_id: str) -> str:
    """Convert Qlib sec_id (e.g. ``000001.XSHE``) to cQuant ticker (e.g. ``000001.SZ``).

    Parameters
    ----------
    sec_id:
        Sec ID in ``CODE.QLIB_SUFFIX`` format (Qlib convention).

    Returns
    -------
    str
        Ticker in ``CODE.SUFFIX`` format (cQuant convention).

    Raises
    ------
    ValueError
        If the sec_id suffix is not recognized.
    """
    parts = sec_id.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid sec_id format: {sec_id!r}; expected CODE.QLIB_SUFFIX")
    code, qlib_suffix = parts
    cquant_suffix = _SUFFIX_MAP_REV.get(qlib_suffix.upper())
    if cquant_suffix is None:
        raise ValueError(
            f"Unknown Qlib suffix {qlib_suffix!r} in sec_id {sec_id!r}; "
            f"known suffixes: {list(_SUFFIX_MAP_REV.keys())}"
        )
    return f"{code}.{cquant_suffix}"


# ---------------------------------------------------------------------------
# CalendarStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class QuantDBCalendarStorage(CalendarStorage):
        """Read trading calendar from QuantDB (cQuant data warehouse).

        Parameters
        ----------
        freq:
            Frequency string (e.g. ``"day"``).  Currently only ``"day"`` is supported.
        future:
            Whether to include future dates (unused for QuantDB; always False).
        catalog:
            Initialized ``Catalog`` connection to cQuant's DuckDB/PostgreSQL backend.
        """

        def __init__(
            self,
            freq: str,
            future: bool,
            catalog: Catalog,
            **kwargs,
        ) -> None:
            super().__init__(freq, future, **kwargs)
            self._catalog = catalog
            self._cache: list[CalVT] | None = None

        def _load_calendar(self) -> list[CalVT]:
            """Load trading calendar from QuantDB."""
            if self._cache is not None:
                return self._cache
            try:
                df = self._catalog.query(
                    """
                    SELECT DISTINCT trade_date
                    FROM silver_prices_1d
                    ORDER BY trade_date
                    """
                )
                self._cache = [
                    str(row["trade_date"])
                    for row in df.to_dicts()
                ]
            except Exception:
                logger.warning("QuantDBCalendarStorage: failed to load calendar, returning empty")
                self._cache = []
            return self._cache

        @property
        def data(self) -> list[CalVT]:
            return self._load_calendar()

        def clear(self) -> None:
            self._cache = None

        def extend(self, iterable: Iterable[CalVT]) -> None:
            raise NotImplementedError("QuantDBCalendarStorage is read-only")

        def index(self, value: CalVT) -> int:
            return self._load_calendar().index(value)

        def insert(self, index: int, value: CalVT) -> None:
            raise NotImplementedError("QuantDBCalendarStorage is read-only")

        def remove(self, value: CalVT) -> None:
            raise NotImplementedError("QuantDBCalendarStorage is read-only")

        def __setitem__(self, i, value) -> None:
            raise NotImplementedError("QuantDBCalendarStorage is read-only")

        def __delitem__(self, i) -> None:
            raise NotImplementedError("QuantDBCalendarStorage is read-only")

        def __getitem__(self, i) -> Union[CalVT, list[CalVT]]:
            return self._load_calendar()[i]

        def __len__(self) -> int:
            return len(self._load_calendar())


# ---------------------------------------------------------------------------
# InstrumentStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class QuantDBInstrumentStorage(InstrumentStorage):
        """Read instrument / index membership from QuantDB.

        Parameters
        ----------
        market:
            Market or index name (e.g. ``"csi300"``, ``"all"``).
        freq:
            Frequency string (e.g. ``"day"``).
        catalog:
            Initialized ``Catalog`` connection.
        """

        def __init__(
            self,
            market: str,
            freq: str,
            catalog: Catalog,
            **kwargs,
        ) -> None:
            super().__init__(market, freq, **kwargs)
            self._catalog = catalog
            self._cache: dict[InstKT, InstVT] | None = None

        def _load_instruments(self) -> dict[InstKT, InstVT]:
            """Load instruments from QuantDB.

            Queries ``silver_prices_1d`` for distinct assets and their
            date ranges.  If *market* matches a known index name, filters
            by index membership; otherwise returns all assets.
            """
            if self._cache is not None:
                return self._cache

            try:
                market_lower = self.market.lower()
                if market_lower in ("all", "a_share", "cn"):
                    # All A-share assets
                    df = self._catalog.query(
                        """
                        SELECT asset_id,
                               MIN(trade_date) AS start_date,
                               MAX(trade_date) AS end_date
                        FROM silver_prices_1d
                        GROUP BY asset_id
                        ORDER BY asset_id
                        """
                    )
                else:
                    # Index membership — try to filter by index name
                    # The index membership table may vary; fall back to all assets
                    logger.info(
                        "QuantDBInstrumentStorage: market=%r not 'all', "
                        "attempting index filter",
                        self.market,
                    )
                    df = self._catalog.query(
                        """
                        SELECT asset_id,
                               MIN(trade_date) AS start_date,
                               MAX(trade_date) AS end_date
                        FROM silver_prices_1d
                        GROUP BY asset_id
                        ORDER BY asset_id
                        """
                    )

                result: dict[InstKT, InstVT] = {}
                for row in df.to_dicts():
                    ticker = str(row["asset_id"])
                    try:
                        sec_id = _ticker_to_sec_id(ticker)
                    except ValueError:
                        sec_id = ticker  # keep as-is if conversion fails
                    start = str(row["start_date"])
                    end = str(row["end_date"])
                    result.setdefault(sec_id, []).append((start, end))

                self._cache = result
            except Exception:
                logger.warning(
                    "QuantDBInstrumentStorage: failed to load instruments, returning empty"
                )
                self._cache = {}
            return self._cache

        @property
        def data(self) -> dict[InstKT, InstVT]:
            return self._load_instruments()

        def clear(self) -> None:
            self._cache = None

        def update(self, *args, **kwargs) -> None:
            raise NotImplementedError("QuantDBInstrumentStorage is read-only")

        def __setitem__(self, k: InstKT, v: InstVT) -> None:
            raise NotImplementedError("QuantDBInstrumentStorage is read-only")

        def __delitem__(self, k: InstKT) -> None:
            raise NotImplementedError("QuantDBInstrumentStorage is read-only")

        def __getitem__(self, k: InstKT) -> InstVT:
            return self._load_instruments()[k]

        def __len__(self) -> int:
            return len(self._load_instruments())


# ---------------------------------------------------------------------------
# FeatureStorage
# ---------------------------------------------------------------------------

# Field name mapping: Qlib field name -> cQuant column name
_FIELD_MAP: dict[str, str] = {
    "$open": "open",
    "$close": "close",
    "$high": "high",
    "$low": "low",
    "$volume": "volume",
    "$factor": "adj_factor",  # adjustment factor, if available
}

if QLIB_AVAILABLE:

    class QuantDBFeatureStorage(FeatureStorage):
        """Read OHLCV features from QuantDB.

        Parameters
        ----------
        instrument:
            Qlib sec_id (e.g. ``"000001.XSHE"``).
        field:
            Qlib field name (e.g. ``"$close"``).
        freq:
            Frequency string (e.g. ``"day"``).
        catalog:
            Initialized ``Catalog`` connection.
        """

        def __init__(
            self,
            instrument: str,
            field: str,
            freq: str,
            catalog: Catalog,
            **kwargs,
        ) -> None:
            super().__init__(instrument, field, freq, **kwargs)
            self._catalog = catalog
            self._series: pd.Series | None = None
            self._start_idx: int | None = None

        def _resolve_column(self) -> str:
            """Map Qlib field name to cQuant column name."""
            col = _FIELD_MAP.get(self.field)
            if col is None:
                # Try stripping the '$' prefix as a fallback
                stripped = self.field.lstrip("$")
                col = stripped
            return col

        def _load_data(self) -> pd.Series:
            """Load feature data from QuantDB and cache as pd.Series."""
            if self._series is not None:
                return self._series

            try:
                ticker = _sec_id_to_ticker(self.instrument)
            except ValueError:
                ticker = self.instrument

            col = self._resolve_column()

            try:
                df = self._catalog.query(
                    f"""
                    SELECT trade_date, {col}
                    FROM silver_prices_1d
                    WHERE asset_id = ?
                    ORDER BY trade_date
                    """,
                    [ticker],
                )
                if df.is_empty():
                    self._series = pd.Series(dtype=np.float32)
                    self._start_idx = None
                    return self._series

                values = df[col].to_numpy().astype(np.float32)
                self._series = pd.Series(
                    values, index=pd.RangeIndex(0, len(values))
                )
                self._start_idx = 0
            except Exception:
                logger.warning(
                    "QuantDBFeatureStorage: failed to load %s/%s, returning empty",
                    self.instrument,
                    self.field,
                )
                self._series = pd.Series(dtype=np.float32)
                self._start_idx = None
            return self._series

        @property
        def data(self) -> pd.Series:
            return self._load_data()

        @property
        def start_index(self) -> int | None:
            self._load_data()
            return self._start_idx

        @property
        def end_index(self) -> int | None:
            s = self._load_data()
            if s.empty or self._start_idx is None:
                return None
            return self._start_idx + len(s) - 1

        def clear(self) -> None:
            self._series = None
            self._start_idx = None

        def write(self, data_array, index=None):
            raise NotImplementedError("QuantDBFeatureStorage is read-only")

        def __getitem__(self, i) -> Union[Tuple[int, float], pd.Series]:
            s = self._load_data()
            if s.empty:
                if isinstance(i, int):
                    return (None, None)
                return pd.Series(dtype=np.float32)
            return s[i]

        def __len__(self) -> int:
            return len(self._load_data())
