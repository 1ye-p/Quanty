"""cquant.datahub — Multi-source data ingestion, normalization, and DuckDB catalog."""

from cquant.datahub.catalog import Catalog
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch
from cquant.datahub.ingest import IngestionSpec, MarketIngestionOrchestrator

__all__ = [
    "Catalog",
    "DataConnector",
    "DataSpec",
    "RawBatch",
    "IngestionSpec",
    "MarketIngestionOrchestrator",
]
