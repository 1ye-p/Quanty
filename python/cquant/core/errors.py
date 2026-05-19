"""cquant.core.errors — Typed exception hierarchy for cQuant."""


class CQuantError(Exception):
    """Base exception for all cQuant errors."""


class DataNotFoundError(CQuantError):
    """Requested market data or dataset was not found."""


class IngestError(CQuantError):
    """Error during data ingestion (fetch, parse, or normalize)."""


class MarketCalendarError(CQuantError):
    """Error resolving trading calendar, suspension, or price limit data."""


class FactorComputeError(CQuantError):
    """Error during factor computation or pipeline execution."""


class BacktestError(CQuantError):
    """Error during backtest execution."""


class RiskDecisionError(CQuantError):
    """Risk check could not be evaluated (missing data, config error)."""


class InvalidSignalError(CQuantError):
    """Signal frame contains invalid or incompatible values."""


class PluginError(CQuantError):
    """Plugin discovery, loading, or capability resolution failed."""


class SchemaValidationError(CQuantError):
    """A data frame or JSON document failed schema validation."""


class CatalogError(CQuantError):
    """DuckDB catalog operation failed."""
