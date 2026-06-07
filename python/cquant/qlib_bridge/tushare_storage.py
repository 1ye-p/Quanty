"""cquant.qlib_bridge.tushare_storage — Tushare-backed Qlib storage implementations.

Provides CalendarStorage, InstrumentStorage, and FeatureStorage backed by
the Tushare Pro API.  Requires a valid Tushare Pro token.

Tushare API docs: https://tushare.pro/document/2
"""
from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ticker conversion helpers (same as pg_storage)
# ---------------------------------------------------------------------------

_SUFFIX_MAP = {
    "SZ": "XSHE",
    "SH": "XSHG",
}
_SUFFIX_MAP_REV = {v: k for k, v in _SUFFIX_MAP.items()}

_FIELD_MAP: dict[str, str] = {
    "$open": "open",
    "$close": "close",
    "$high": "high",
    "$low": "low",
    "$volume": "vol",
    "$factor": "adj_factor",
}


def _ticker_to_sec_id(ticker: str) -> str:
    parts = ticker.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid ticker format: {ticker!r}")
    code, suffix = parts
    qlib_suffix = _SUFFIX_MAP.get(suffix.upper())
    if qlib_suffix is None:
        raise ValueError(f"Unknown exchange suffix {suffix!r}")
    return f"{code}.{qlib_suffix}"


def _sec_id_to_ticker(sec_id: str) -> str:
    parts = sec_id.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid sec_id format: {sec_id!r}")
    code, qlib_suffix = parts
    cquant_suffix = _SUFFIX_MAP_REV.get(qlib_suffix.upper())
    if cquant_suffix is None:
        raise ValueError(f"Unknown Qlib suffix {qlib_suffix!r}")
    return f"{code}.{cquant_suffix}"


def _get_tushare_api(token: str):
    """Lazy-import and init tushare pro API."""
    try:
        import tushare as ts
        ts.set_token(token)
        return ts.pro_api()
    except ImportError:
        raise ImportError(
            "tushare is not installed. Install with: pip install tushare"
        )


# ---------------------------------------------------------------------------
# CalendarStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class TushareCalendarStorage(CalendarStorage):
        """Read trading calendar from Tushare Pro API.

        Parameters
        ----------
        freq:
            Frequency string (currently only ``"day"`` supported).
        future:
            Whether to include future dates.
        token:
            Tushare Pro API token.
        """

        def __init__(self, freq: str, future: bool, token: str, **kwargs) -> None:
            super().__init__(freq, future, **kwargs)
            self._token = token
            self._cache: list[CalVT] | None = None

        def _load_calendar(self) -> list[CalVT]:
            if self._cache is not None:
                return self._cache
            try:
                pro = _get_tushare_api(self._token)
                df = pro.trade_cal(
                    exchange="SSE",
                    start_date="19900101",
                    end_date="20301231",
                    fields="cal_date,is_open",
                )
                df = df[df["is_open"] == 1].sort_values("cal_date")
                self._cache = [
                    pd.Timestamp(row["cal_date"]).strftime("%Y-%m-%d")
                    for _, row in df.iterrows()
                ]
            except Exception as exc:
                logger.warning("TushareCalendarStorage: failed to load calendar: %s", exc)
                self._cache = []
            return self._cache

        @property
        def data(self) -> list[CalVT]:
            return self._load_calendar()

        def clear(self) -> None:
            self._cache = None

        def extend(self, iterable: Iterable[CalVT]) -> None:
            raise NotImplementedError("TushareCalendarStorage is read-only")

        def index(self, value: CalVT) -> int:
            return self._load_calendar().index(value)

        def insert(self, index: int, value: CalVT) -> None:
            raise NotImplementedError("TushareCalendarStorage is read-only")

        def remove(self, value: CalVT) -> None:
            raise NotImplementedError("TushareCalendarStorage is read-only")

        def __setitem__(self, i, value) -> None:
            raise NotImplementedError("TushareCalendarStorage is read-only")

        def __delitem__(self, i) -> None:
            raise NotImplementedError("TushareCalendarStorage is read-only")

        def __getitem__(self, i) -> Union[CalVT, list[CalVT]]:
            return self._load_calendar()[i]

        def __len__(self) -> int:
            return len(self._load_calendar())


# ---------------------------------------------------------------------------
# InstrumentStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class TushareInstrumentStorage(InstrumentStorage):
        """Read instrument membership from Tushare Pro API.

        Parameters
        ----------
        market:
            Market or index name (e.g. ``"csi300"``, ``"all"``).
        freq:
            Frequency string (e.g. ``"day"``).
        token:
            Tushare Pro API token.
        """

        def __init__(self, market: str, freq: str, token: str, **kwargs) -> None:
            super().__init__(market, freq, **kwargs)
            self._token = token
            self._cache: dict[InstKT, InstVT] | None = None

        def _load_instruments(self) -> dict[InstKT, InstVT]:
            if self._cache is not None:
                return self._cache
            try:
                pro = _get_tushare_api(self._token)
                market_lower = self.market.lower()

                if market_lower in ("all", "a_share", "cn"):
                    df = pro.stock_basic(
                        exchange="",
                        list_status="L",
                        fields="ts_code,name,list_date,delist_date",
                    )
                elif market_lower == "csi300":
                    df = pro.index_weight(
                        index_code="399300.SZ",
                        start_date="20000101",
                        end_date="20301231",
                        fields="con_code,start_date,end_date",
                    )
                else:
                    logger.warning(
                        "TushareInstrumentStorage: market=%r not supported, returning all",
                        self.market,
                    )
                    df = pro.stock_basic(
                        exchange="",
                        list_status="L",
                        fields="ts_code,name,list_date,delist_date",
                    )

                result: dict[InstKT, InstVT] = {}
                if "con_code" in df.columns:
                    # Index weight format
                    for _, row in df.iterrows():
                        ticker = str(row["con_code"])
                        try:
                            sec_id = _ticker_to_sec_id(ticker)
                        except ValueError:
                            sec_id = ticker
                        start = str(row.get("start_date", ""))
                        end = str(row.get("end_date", ""))
                        result.setdefault(sec_id, []).append((start, end))
                else:
                    # Stock basic format
                    for _, row in df.iterrows():
                        ticker = str(row["ts_code"])
                        try:
                            sec_id = _ticker_to_sec_id(ticker)
                        except ValueError:
                            sec_id = ticker
                        start = str(row.get("list_date", ""))
                        end = str(row.get("delist_date", ""))
                        result.setdefault(sec_id, []).append((start, end))

                self._cache = result
            except Exception as exc:
                logger.warning("TushareInstrumentStorage: failed to load instruments: %s", exc)
                self._cache = {}
            return self._cache

        @property
        def data(self) -> dict[InstKT, InstVT]:
            return self._load_instruments()

        def clear(self) -> None:
            self._cache = None

        def update(self, *args, **kwargs) -> None:
            raise NotImplementedError("TushareInstrumentStorage is read-only")

        def __setitem__(self, k: InstKT, v: InstVT) -> None:
            raise NotImplementedError("TushareInstrumentStorage is read-only")

        def __delitem__(self, k: InstKT) -> None:
            raise NotImplementedError("TushareInstrumentStorage is read-only")

        def __getitem__(self, k: InstKT) -> InstVT:
            return self._load_instruments()[k]

        def __len__(self) -> int:
            return len(self._load_instruments())


# ---------------------------------------------------------------------------
# FeatureStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class TushareFeatureStorage(FeatureStorage):
        """Read OHLCV features from Tushare Pro API.

        Parameters
        ----------
        instrument:
            Qlib sec_id (e.g. ``"000001.XSHE"``).
        field:
            Qlib field name (e.g. ``"$close"``).
        freq:
            Frequency string (e.g. ``"day"``).
        token:
            Tushare Pro API token.
        """

        def __init__(
            self, instrument: str, field: str, freq: str, token: str, **kwargs
        ) -> None:
            super().__init__(instrument, field, freq, **kwargs)
            self._token = token
            self._series: pd.Series | None = None
            self._start_idx: int | None = None

        def _resolve_column(self) -> str:
            col = _FIELD_MAP.get(self.field)
            if col is None:
                raise ValueError(
                    f"Unknown field '{self.field}'. Supported: {list(_FIELD_MAP.keys())}"
                )
            return col

        def _load_data(self) -> pd.Series:
            if self._series is not None:
                return self._series

            try:
                ticker = _sec_id_to_ticker(self.instrument)
            except ValueError:
                ticker = self.instrument

            col = self._resolve_column()

            try:
                pro = _get_tushare_api(self._token)
                df = pro.daily(
                    ts_code=ticker,
                    start_date="19900101",
                    end_date="20301231",
                    fields=f"trade_date,{col}",
                )
                if df is None or df.empty:
                    self._series = pd.Series(dtype=np.float32)
                    self._start_idx = None
                    return self._series

                df = df.sort_values("trade_date")
                values = df[col].to_numpy().astype(np.float32)
                self._series = pd.Series(values, index=pd.RangeIndex(0, len(values)))
                self._start_idx = 0
            except Exception as exc:
                logger.warning(
                    "TushareFeatureStorage: failed to load %s/%s: %s",
                    self.instrument, self.field, exc,
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
            raise NotImplementedError("TushareFeatureStorage is read-only")

        def __getitem__(self, i) -> Union[Tuple[int, float], pd.Series]:
            s = self._load_data()
            if s.empty:
                if isinstance(i, int):
                    return (None, None)
                return pd.Series(dtype=np.float32)
            return s[i]

        def __len__(self) -> int:
            return len(self._load_data())
