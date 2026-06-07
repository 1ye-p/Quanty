"""cquant.qlib_bridge.akshare_storage — AKShare-backed Qlib storage implementations.

Provides CalendarStorage, InstrumentStorage, and FeatureStorage backed by
the AKShare library (open-source Chinese financial data API).

AKShare docs: https://akshare.akfamily.xyz/
"""
from __future__ import annotations

import logging
from typing import Dict, Iterable, Tuple, Union

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
# Ticker conversion helpers
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
    "$volume": "volume",
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


def _sec_id_to_ak_symbol(sec_id: str) -> str:
    """Convert Qlib sec_id to AKShare symbol format (e.g. ``000001.XSHE`` -> ``000001``)."""
    parts = sec_id.rsplit(".", 1)
    return parts[0] if len(parts) == 2 else sec_id


def _import_akshare():
    """Lazy-import akshare."""
    try:
        import akshare as ak
        return ak
    except ImportError:
        raise ImportError(
            "akshare is not installed. Install with: pip install akshare"
        )


# ---------------------------------------------------------------------------
# CalendarStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class AKShareCalendarStorage(CalendarStorage):
        """Read trading calendar from AKShare.

        Parameters
        ----------
        freq:
            Frequency string (currently only ``"day"`` supported).
        future:
            Whether to include future dates.
        """

        def __init__(self, freq: str, future: bool, **kwargs) -> None:
            super().__init__(freq, future, **kwargs)
            self._cache: list[CalVT] | None = None

        def _load_calendar(self) -> list[CalVT]:
            if self._cache is not None:
                return self._cache
            try:
                ak = _import_akshare()
                # AKShare provides tool_trade_date_hist_sina for SSE calendar
                df = ak.tool_trade_date_hist_sina()
                if df is not None and not df.empty:
                    df = df.sort_values("trade_date")
                    self._cache = [
                        pd.Timestamp(d).strftime("%Y-%m-%d")
                        for d in df["trade_date"].tolist()
                    ]
                else:
                    self._cache = []
            except Exception as exc:
                logger.warning("AKShareCalendarStorage: failed to load calendar: %s", exc)
                self._cache = []
            return self._cache

        @property
        def data(self) -> list[CalVT]:
            return self._load_calendar()

        def clear(self) -> None:
            self._cache = None

        def extend(self, iterable: Iterable[CalVT]) -> None:
            raise NotImplementedError("AKShareCalendarStorage is read-only")

        def index(self, value: CalVT) -> int:
            return self._load_calendar().index(value)

        def insert(self, index: int, value: CalVT) -> None:
            raise NotImplementedError("AKShareCalendarStorage is read-only")

        def remove(self, value: CalVT) -> None:
            raise NotImplementedError("AKShareCalendarStorage is read-only")

        def __setitem__(self, i, value) -> None:
            raise NotImplementedError("AKShareCalendarStorage is read-only")

        def __delitem__(self, i) -> None:
            raise NotImplementedError("AKShareCalendarStorage is read-only")

        def __getitem__(self, i) -> Union[CalVT, list[CalVT]]:
            return self._load_calendar()[i]

        def __len__(self) -> int:
            return len(self._load_calendar())


# ---------------------------------------------------------------------------
# InstrumentStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class AKShareInstrumentStorage(InstrumentStorage):
        """Read instrument membership from AKShare.

        Parameters
        ----------
        market:
            Market or index name (e.g. ``"csi300"``, ``"all"``).
        freq:
            Frequency string (e.g. ``"day"``).
        """

        def __init__(self, market: str, freq: str, **kwargs) -> None:
            super().__init__(market, freq, **kwargs)
            self._cache: dict[InstKT, InstVT] | None = None

        def _load_instruments(self) -> dict[InstKT, InstVT]:
            if self._cache is not None:
                return self._cache
            try:
                ak = _import_akshare()
                market_lower = self.market.lower()

                if market_lower in ("all", "a_share", "cn"):
                    df = ak.stock_info_a_code_name()
                    if df is not None and not df.empty:
                        result: dict[InstKT, InstVT] = {}
                        for _, row in df.iterrows():
                            code = str(row.get("code", ""))
                            if not code:
                                continue
                            # Determine exchange suffix
                            if code.startswith(("6", "9")):
                                sec_id = f"{code}.XSHG"
                            else:
                                sec_id = f"{code}.XSHE"
                            result.setdefault(sec_id, []).append(("", ""))
                        self._cache = result
                    else:
                        self._cache = {}
                elif market_lower == "csi300":
                    df = ak.index_stock_cons_weight_csindex(symbol="000300")
                    if df is not None and not df.empty:
                        result = {}
                        for _, row in df.iterrows():
                            code = str(row.get("成分券代码", row.get("symbol", "")))
                            if not code:
                                continue
                            if code.startswith(("6", "9")):
                                sec_id = f"{code}.XSHG"
                            else:
                                sec_id = f"{code}.XSHE"
                            result.setdefault(sec_id, []).append(("", ""))
                        self._cache = result
                    else:
                        self._cache = {}
                else:
                    logger.warning(
                        "AKShareInstrumentStorage: market=%r not supported, returning empty",
                        self.market,
                    )
                    self._cache = {}
            except Exception as exc:
                logger.warning("AKShareInstrumentStorage: failed to load instruments: %s", exc)
                self._cache = {}
            return self._cache

        @property
        def data(self) -> dict[InstKT, InstVT]:
            return self._load_instruments()

        def clear(self) -> None:
            self._cache = None

        def update(self, *args, **kwargs) -> None:
            raise NotImplementedError("AKShareInstrumentStorage is read-only")

        def __setitem__(self, k: InstKT, v: InstVT) -> None:
            raise NotImplementedError("AKShareInstrumentStorage is read-only")

        def __delitem__(self, k: InstKT) -> None:
            raise NotImplementedError("AKShareInstrumentStorage is read-only")

        def __getitem__(self, k: InstKT) -> InstVT:
            return self._load_instruments()[k]

        def __len__(self) -> int:
            return len(self._load_instruments())


# ---------------------------------------------------------------------------
# FeatureStorage
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:

    class AKShareFeatureStorage(FeatureStorage):
        """Read OHLCV features from AKShare.

        Parameters
        ----------
        instrument:
            Qlib sec_id (e.g. ``"000001.XSHE"``).
        field:
            Qlib field name (e.g. ``"$close"``).
        freq:
            Frequency string (e.g. ``"day"``).
        """

        def __init__(
            self, instrument: str, field: str, freq: str, **kwargs
        ) -> None:
            super().__init__(instrument, field, freq, **kwargs)
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

            ak_symbol = _sec_id_to_ak_symbol(self.instrument)
            col = self._resolve_column()

            try:
                ak = _import_akshare()
                df = ak.stock_zh_a_hist(
                    symbol=ak_symbol,
                    period="daily",
                    start_date="19900101",
                    end_date="20301231",
                    adjust="qfq",
                )
                if df is None or df.empty:
                    self._series = pd.Series(dtype=np.float32)
                    self._start_idx = None
                    return self._series

                # AKShare column mapping
                ak_col_map = {
                    "open": "开盘",
                    "close": "收盘",
                    "high": "最高",
                    "low": "最低",
                    "volume": "成交量",
                }
                ak_col = ak_col_map.get(col, col)

                if ak_col not in df.columns:
                    # Try English column names as fallback
                    if col in df.columns:
                        ak_col = col
                    else:
                        logger.warning(
                            "AKShareFeatureStorage: column %r not found in %s",
                            col, list(df.columns),
                        )
                        self._series = pd.Series(dtype=np.float32)
                        self._start_idx = None
                        return self._series

                values = df[ak_col].to_numpy().astype(np.float32)
                self._series = pd.Series(values, index=pd.RangeIndex(0, len(values)))
                self._start_idx = 0
            except Exception as exc:
                logger.warning(
                    "AKShareFeatureStorage: failed to load %s/%s: %s",
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
            raise NotImplementedError("AKShareFeatureStorage is read-only")

        def __getitem__(self, i) -> Union[Tuple[int, float], pd.Series]:
            s = self._load_data()
            if s.empty:
                if isinstance(i, int):
                    return (None, None)
                return pd.Series(dtype=np.float32)
            return s[i]

        def __len__(self) -> int:
            return len(self._load_data())
