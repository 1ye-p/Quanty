"""News source connectors."""

from cquant.newsflow.connectors.base import NewsConnector, NewsSpec, RawNewsEnvelope
from cquant.newsflow.connectors.eastmoney import EastmoneyConnector
from cquant.newsflow.connectors.rss import RSSConnector
from cquant.newsflow.connectors.sina import SinaFinanceConnector

__all__ = [
    "EastmoneyConnector",
    "NewsConnector",
    "NewsSpec",
    "RSSConnector",
    "RawNewsEnvelope",
    "SinaFinanceConnector",
]
