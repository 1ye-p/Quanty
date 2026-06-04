"""cquant.qlib_bridge.provider — Qlib Provider classes backed by QuantDB.

Registers Calendar, Instrument, and Feature providers that read from
cQuant's data warehouse (QuantDB) instead of flat files.

These classes implement the ``qlib.data.provider.Provider`` interface
so that ``qlib.init()`` can use QuantDB as its data source.
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
# Provider classes
# ---------------------------------------------------------------------------

if QLIB_AVAILABLE:
    from cquant.qlib_bridge.pg_storage import (
        QuantDBCalendarStorage,
        QuantDBFeatureStorage,
        QuantDBInstrumentStorage,
    )

    class QuantDBCalendarProvider:
        """Factory that creates QuantDBCalendarStorage instances.

        Registered with Qlib's provider registry so that calendar queries
        are routed to QuantDB.
        """

        def __init__(self, catalog: "Catalog") -> None:
            self._catalog = catalog

        def __call__(self, freq: str, future: bool = False, **kwargs) -> CalendarStorage:
            return QuantDBCalendarStorage(
                freq=freq,
                future=future,
                catalog=self._catalog,
                **kwargs,
            )

    class QuantDBInstrumentProvider:
        """Factory that creates QuantDBInstrumentStorage instances."""

        def __init__(self, catalog: "Catalog") -> None:
            self._catalog = catalog

        def __call__(self, market: str, freq: str = "day", **kwargs) -> InstrumentStorage:
            return QuantDBInstrumentStorage(
                market=market,
                freq=freq,
                catalog=self._catalog,
                **kwargs,
            )

    class QuantDBFeatureProvider:
        """Factory that creates QuantDBFeatureStorage instances."""

        def __init__(self, catalog: "Catalog") -> None:
            self._catalog = catalog

        def __call__(
            self, instrument: str, field: str, freq: str = "day", **kwargs
        ) -> FeatureStorage:
            return QuantDBFeatureStorage(
                instrument=instrument,
                field=field,
                freq=freq,
                catalog=self._catalog,
                **kwargs,
            )
