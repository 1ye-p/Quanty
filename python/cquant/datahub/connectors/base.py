"""cquant.datahub.connectors.base — DataConnector ABC and shared data contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

import polars as pl

from cquant.core.enums import AssetClass, Exchange, Frequency, Market


@dataclass
class DataSpec:
    """Specification for a data fetch request."""

    symbols: list[str]
    start_date: date
    end_date: date
    frequency: Frequency = Frequency.D1
    market: Market = Market.CN
    exchanges: list[Exchange] = field(default_factory=list)
    asset_class: AssetClass = AssetClass.EQUITY
    # Fields to include in the output (None = all available)
    fields: list[str] | None = None
    # Extra connector-specific parameters
    extra: dict = field(default_factory=dict)


@dataclass
class RawBatch:
    """A batch of raw data from a single source, before normalization."""

    source: str               # Connector name, e.g. "akshare", "tushare"
    dataset: str              # Dataset type, e.g. "daily_bar", "fundamentals"
    data: pl.DataFrame        # Raw rows (vendor-native column names and types)
    fetched_at: str           # ISO-8601 UTC timestamp
    spec: DataSpec | None = None
    checksum: str = ""        # SHA-256 of serialized data (filled by ingestion layer)


class DataConnector(ABC):
    """Abstract base for all data source connectors.

    Each connector is responsible for exactly one external data source
    (AKShare, Tushare, Yahoo Finance, etc.).  Normalization to the Silver
    schema happens in the pipeline layer, not here.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique stable identifier for this connector, e.g. 'akshare'."""

    @property
    @abstractmethod
    def supported_markets(self) -> list[Market]:
        """Markets this connector can fetch data for."""

    @property
    @abstractmethod
    def supported_frequencies(self) -> list[Frequency]:
        """Bar frequencies this connector supports."""

    @abstractmethod
    def fetch(self, spec: DataSpec) -> Iterable[RawBatch]:
        """Fetch data according to *spec* and yield one or more RawBatch objects.

        Implementations should:
        - Respect spec.start_date / spec.end_date
        - Split large requests into manageable batches
        - Not perform normalization (return vendor-native format)
        - Raise IngestError on unrecoverable failures
        """

    def can_fetch(self, spec: DataSpec) -> bool:
        """Return True if this connector supports the given DataSpec."""
        return spec.market in self.supported_markets and spec.frequency in self.supported_frequencies
