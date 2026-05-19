"""cquant.datahub.connectors.tushare_connector — Tushare Pro data connector.

Fetches CN A-share daily bars, fundamentals, and corporate action data.
Requires: tushare>=1.4 and a valid TUSHARE_TOKEN environment variable.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Iterable

import polars as pl

from cquant.core.enums import Frequency, Market
from cquant.core.errors import IngestError
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch

logger = logging.getLogger(__name__)


class TushareConnector(DataConnector):
    """Connector for Tushare Pro (CN market: bars, fundamentals, adj_factor, calendar)."""

    def __init__(self, token: str | None = None) -> None:
        # Priority: explicit arg > settings (reads from .env) > env var
        if token:
            self._token = token
        else:
            try:
                from cquant.core.config import settings
                self._token = settings.tushare_token or os.environ.get("TUSHARE_TOKEN", "")
            except Exception:
                self._token = os.environ.get("TUSHARE_TOKEN", "")
        self._pro: object | None = None

    @property
    def source_name(self) -> str:
        return "tushare"

    @property
    def supported_markets(self) -> list[Market]:
        return [Market.CN]

    @property
    def supported_frequencies(self) -> list[Frequency]:
        return [Frequency.D1, Frequency.W1, Frequency.MO1]

    def _get_pro(self) -> object:
        if self._pro is None:
            try:
                import tushare as ts  # type: ignore[import-untyped]
            except ImportError as exc:
                raise IngestError("tushare is not installed. Run: pip install tushare") from exc
            if not self._token:
                raise IngestError(
                    "TUSHARE_TOKEN is not set. Export it as an environment variable."
                )
            ts.set_token(self._token)
            self._pro = ts.pro_api()
        return self._pro

    def fetch(self, spec: DataSpec) -> Iterable[RawBatch]:
        pro = self._get_pro()
        fetched_at = datetime.now(tz=timezone.utc).isoformat()
        start_str = spec.start_date.strftime("%Y%m%d")
        end_str = spec.end_date.strftime("%Y%m%d")

        for symbol in spec.symbols:
            # Tushare uses "000001.SZ" format; datahub uses "SZSE:000001"
            ts_code = _to_tushare_code(symbol)
            try:
                df_pd = pro.daily(  # type: ignore[union-attr]
                    ts_code=ts_code,
                    start_date=start_str,
                    end_date=end_str,
                )
                df = pl.from_pandas(df_pd)
                yield RawBatch(
                    source=self.source_name,
                    dataset="daily_bar",
                    data=df,
                    fetched_at=fetched_at,
                    spec=spec,
                )
            except Exception as exc:
                logger.error("Tushare fetch failed for %s: %s", symbol, exc)
                raise IngestError(f"Tushare fetch failed for {symbol}: {exc}") from exc

    def fetch_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pl.DataFrame:
        """Fetch adjustment factors (复权因子) for a single symbol."""
        pro = self._get_pro()
        df_pd = pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)  # type: ignore[union-attr]
        return pl.from_pandas(df_pd)

    def fetch_trade_calendar(self, exchange: str = "SSE", start_date: str = "20200101", end_date: str = "20271231") -> pl.DataFrame:
        """Fetch trading calendar (交易日历) from Tushare."""
        pro = self._get_pro()
        df_pd = pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date)  # type: ignore[union-attr]
        return pl.from_pandas(df_pd)


def _to_tushare_code(asset_id: str) -> str:
    """Convert cQuant asset_id (e.g. 'SSE:600036') to Tushare code ('600036.SH')."""
    if ":" not in asset_id:
        return asset_id
    exchange, symbol = asset_id.split(":", 1)
    suffix = {"SSE": "SH", "SZSE": "SZ"}.get(exchange, exchange)
    return f"{symbol}.{suffix}"
