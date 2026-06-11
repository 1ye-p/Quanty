"""cquant.datahub — Multi-source data ingestion, normalization, and DuckDB catalog."""

from cquant.datahub.adjustment_verifier import AdjustmentVerifier
from cquant.datahub.catalog import Catalog
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch
from cquant.datahub.ingest import IngestionSpec, MarketIngestionOrchestrator
from cquant.datahub.quality_scorer import DataQualityScorer
from cquant.datahub.universe import PointInTimeUniverse

__all__ = [
    "AdjustmentVerifier",
    "Catalog",
    "DataConnector",
    "DataQualityScorer",
    "DataSpec",
    "IngestionSpec",
    "MarketIngestionOrchestrator",
    "PointInTimeUniverse",
    "RawBatch",
]
