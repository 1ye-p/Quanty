"""cquant.datahub.connectors.yfinance_connector — Yahoo Finance connector (US/HK)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import polars as pl

from cquant.core.enums import Frequency, Market
from cquant.core.errors import IngestError
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch

logger = logging.getLogger(__name__)


class YahooFinanceConnector(DataConnector):
    """Connector for Yahoo Finance (US and HK equities, daily bars)."""

    @property
    def source_name(self) -> str:
        return "yfinance"

    @property
    def supported_markets(self) -> list[Market]:
        return [Market.US, Market.HK]

    @property
    def supported_frequencies(self) -> list[Frequency]:
        return [Frequency.D1, Frequency.W1, Frequency.MO1, Frequency.H1, Frequency.M1]

    def fetch(self, spec: DataSpec) -> Iterable[RawBatch]:
        try:
            import yfinance as yf  # type: ignore[import-untyped]
        except ImportError as exc:
            raise IngestError("yfinance is not installed. Run: pip install yfinance") from exc

        fetched_at = datetime.now(tz=timezone.utc).isoformat()

        for symbol in spec.symbols:
            yf_ticker = _to_yf_ticker(symbol)
            try:
                ticker = yf.Ticker(yf_ticker)
                df_pd = ticker.history(
                    start=spec.start_date.isoformat(),
                    end=spec.end_date.isoformat(),
                    interval="1d",
                    auto_adjust=False,  # Fetch raw; normalization applies adj
                )
                df_pd = df_pd.reset_index()
                df = pl.from_pandas(df_pd)
                df = df.with_columns(pl.lit(symbol).alias("symbol"))

                yield RawBatch(
                    source=self.source_name,
                    dataset="daily_bar",
                    data=df,
                    fetched_at=fetched_at,
                    spec=spec,
                )
            except Exception as exc:
                logger.error("yfinance fetch failed for %s: %s", symbol, exc)
                raise IngestError(f"yfinance fetch failed for {symbol}: {exc}") from exc


def _to_yf_ticker(asset_id: str) -> str:
    """Convert cQuant asset_id to Yahoo Finance ticker format."""
    if ":" not in asset_id:
        return asset_id
    exchange, symbol = asset_id.split(":", 1)
    if exchange == "HKEX":
        return f"{symbol}.HK"
    # US exchanges: symbol is already in Yahoo format
    return symbol
