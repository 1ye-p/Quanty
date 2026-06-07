"""cquant.qlib_bridge.duckdb_storage — DuckDB-backed Qlib storage implementations.

Provides CalendarStorage, InstrumentStorage, and FeatureStorage backed by
cQuant's silver layer via Catalog.  These are thin wrappers around the existing
QuantDB storage classes in ``pg_storage.py``, using the same Catalog interface.

This module exists to give a clear "duckdb" entry point distinct from the
legacy "quantdb" alias.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cquant.qlib_bridge._compat import QLIB_AVAILABLE

if QLIB_AVAILABLE:
    from qlib.data.storage import CalendarStorage, FeatureStorage, InstrumentStorage

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Re-export from pg_storage — the Catalog interface is the same
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:
    from cquant.qlib_bridge.pg_storage import (
        QuantDBCalendarStorage as DuckDBCalendarStorage,
        QuantDBFeatureStorage as DuckDBFeatureStorage,
        QuantDBInstrumentStorage as DuckDBInstrumentStorage,
    )

    __all__ = [
        "DuckDBCalendarStorage",
        "DuckDBInstrumentStorage",
        "DuckDBFeatureStorage",
    ]
else:
    __all__ = []
