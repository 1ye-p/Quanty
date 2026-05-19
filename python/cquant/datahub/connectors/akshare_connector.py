"""cquant.datahub.connectors.akshare_connector — AKShare data connector.

Fetches CN A-share OHLCV bars and basic market data via AKShare.
Requires: akshare>=1.14 installed in the cQuanty conda environment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import polars as pl

from cquant.core.enums import Frequency, Market
from cquant.core.errors import IngestError
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch

logger = logging.getLogger(__name__)


class AKShareConnector(DataConnector):
    """Connector for AKShare (CN market, daily and intraday bars)."""

    @property
    def source_name(self) -> str:
        return "akshare"

    @property
    def supported_markets(self) -> list[Market]:
        return [Market.CN]

    @property
    def supported_frequencies(self) -> list[Frequency]:
        return [Frequency.D1, Frequency.M1, Frequency.M5, Frequency.M15, Frequency.M30, Frequency.H1]

    def fetch(self, spec: DataSpec) -> Iterable[RawBatch]:
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError as exc:
            raise IngestError("akshare is not installed. Run: pip install akshare") from exc

        fetched_at = datetime.now(tz=timezone.utc).isoformat()
        start_str = spec.start_date.strftime("%Y%m%d")
        end_str = spec.end_date.strftime("%Y%m%d")

        for symbol in spec.symbols:
            try:
                df_pd = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust="",  # Raw unadjusted; normalization handles adjustment
                )
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
                logger.error("AKShare fetch failed for %s: %s", symbol, exc)
                raise IngestError(f"AKShare fetch failed for {symbol}: {exc}") from exc
