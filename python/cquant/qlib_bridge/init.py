"""cquant.qlib_bridge.init — Initialize Qlib with QuantDB storage backends.

Provides ``init_qlib_with_quantdb()`` which configures Qlib to read all
data from cQuant's data warehouse instead of flat files.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, require_qlib

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


def init_qlib_with_quantdb(
    catalog: "Catalog",
    region: str = "cn",
    **qlib_kwargs,
) -> None:
    """Initialize Qlib with QuantDB as the data backend.

    This replaces Qlib's default file-based storage with QuantDB-backed
    implementations, so that all calendar, instrument, and feature queries
    are routed to cQuant's data warehouse.

    Parameters
    ----------
    catalog:
        Initialized ``Catalog`` connection to cQuant's DuckDB/PostgreSQL backend.
    region:
        Market region (default ``"cn"`` for China A-shares).
    **qlib_kwargs:
        Additional keyword arguments passed to ``qlib.init()``.

    Raises
    ------
    ImportError
        If Qlib is not installed.

    Example
    -------
    ::

        from cquant.datahub.catalog import Catalog
        from cquant.qlib_bridge import init_qlib_with_quantdb

        catalog = Catalog("data/catalog.duckdb")
        catalog.initialize()
        init_qlib_with_quantdb(catalog)
    """
    require_qlib()

    import qlib
    from qlib.config import C

    from cquant.qlib_bridge.provider import (
        QuantDBCalendarProvider,
        QuantDBFeatureProvider,
        QuantDBInstrumentProvider,
    )

    # Register QuantDB providers with Qlib's provider registry
    calendar_provider = QuantDBCalendarProvider(catalog)
    instrument_provider = QuantDBInstrumentProvider(catalog)
    feature_provider = QuantDBFeatureProvider(catalog)

    # Build the qlib init kwargs
    init_config = {
        "region": region,
        "calendar_provider": calendar_provider,
        "instrument_provider": instrument_provider,
        "feature_provider": feature_provider,
    }
    init_config.update(qlib_kwargs)

    logger.info(
        "init_qlib_with_quantdb: initializing Qlib with region=%s, "
        "QuantDB-backed calendar/instrument/feature providers",
        region,
    )

    qlib.init(**init_config)

    logger.info("init_qlib_with_quantdb: Qlib initialized successfully")
