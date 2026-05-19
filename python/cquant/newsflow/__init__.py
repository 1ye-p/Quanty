"""cquant.newsflow — Polling-based news ingestion, normalization, and PIT filtering."""

from cquant.newsflow.connectors.base import NewsConnector, NewsSpec, RawNewsEnvelope
from cquant.newsflow.connectors.eastmoney import EastmoneyConnector
from cquant.newsflow.connectors.rss import RSSConnector
from cquant.newsflow.connectors.sina import SinaFinanceConnector
from cquant.newsflow.ingest import NewsIngestionOrchestrator
from cquant.newsflow.normalize import NEWS_EVENT_SCHEMA, NewsNormalizer, build_dedupe_key
from cquant.newsflow.pit import PITGate

__all__ = [
    "EastmoneyConnector",
    "NEWS_EVENT_SCHEMA",
    "NewsConnector",
    "NewsIngestionOrchestrator",
    "NewsNormalizer",
    "NewsSpec",
    "PITGate",
    "RSSConnector",
    "RawNewsEnvelope",
    "SinaFinanceConnector",
    "build_dedupe_key",
]
