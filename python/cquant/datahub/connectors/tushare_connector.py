"""cquant.datahub.connectors.tushare_connector — Tushare Pro data connector.

Fetches CN A-share daily bars, fundamentals, and corporate action data.
Requires: tushare>=1.4 and a valid TUSHARE_TOKEN environment variable.
"""

from __future__ import annotations
import time as _time

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
        import time as _time
        pro = self._get_pro()
        fetched_at = datetime.now(tz=timezone.utc).isoformat()
        start_str = spec.start_date.strftime("%Y%m%d")
        end_str = spec.end_date.strftime("%Y%m%d")

        for i, symbol in enumerate(spec.symbols):
            # Tushare rate limit: 40 requests/minute → sleep 1.5s between calls
            if i > 0:
                _time.sleep(1.5)
            # Tushare uses "000001.SZ" format; datahub uses "SZSE:000001"
            ts_code = _to_tushare_code(symbol)
            try:
                df_pd = pro.daily(  # type: ignore[union-attr]
                    ts_code=ts_code,
                    start_date=start_str,
                    end_date=end_str,
                )
                df = pl.from_pandas(df_pd)
                # 转换 ts_code 为 asset_id 格式 (000001.SZ -> SZSE:000001)
                if "ts_code" in df.columns:
                    df = df.with_columns(
                        pl.col("ts_code").map_elements(_to_asset_id, return_dtype=pl.Utf8).alias("asset_id")
                    )
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

    def fetch_valuation_daily(self, ts_code: str, start: str, end: str) -> pl.DataFrame:
        """从 pro.daily_basic 取逐日估值（PE/PB/PS/市值/换手率/股息率）。
        天然 PIT：trade_date 即数据可用日。
        """
        pro = self._get_pro()
        df_pd = pro.daily_basic(  # type: ignore[union-attr]
            ts_code=ts_code, start_date=start, end_date=end,
            fields="ts_code,trade_date,pe_ttm,pb,ps_ttm,total_mv,turnover_rate,dv_ttm",
        )
        df = pl.from_pandas(df_pd)
        df = df.with_columns([
            (pl.col("total_mv") * 1e4).alias("market_cap"),  # 万元 → 元
            pl.col("dv_ttm").alias("dividend_yield"),
        ])
        return df

    def fetch_dividend(self, ts_code: str) -> list[dict]:
        """从 pro.dividend 取分红事件，映射到 silver_corporate_actions 列结构。

        仅保留已实施（``div_proc == '实施'``）的分红方案，否则会重复计入预案/
        年报等草案。``div_proc`` 全流程包含 ``预案/股东大会通过/停止实施/实施``，
        一家公司每年可能有多条历史草案，只取 ``实施`` 行可避免 ex_date 聚合时的
        多重计数。

        Parameters
        ----------
        ts_code
            Tushare 代码，如 ``'000001.SZ'``。

        Returns
        -------
        list[dict]
            每条 dict 与 ``silver_corporate_actions`` 列结构一致（``action_id`` /
            ``asset_id`` / ``action_type`` / ``ex_date`` / ``record_date`` /
            ``pay_date`` / ``cash_amount`` / ``ratio`` / ``source``）。
        """
        pro = self._get_pro()
        df_pd = pro.dividend(  # type: ignore[union-attr]
            ts_code=ts_code,
            fields="ts_code,div_proc,ex_date,record_date,ann_date,cash_div,stk_div",
        )
        df = pl.from_pandas(df_pd)

        # 仅保留已实施的分红方案，过滤掉预案/停止实施/股东大会通过等草案
        if "div_proc" in df.columns:
            df = df.filter(pl.col("div_proc") == "实施")
        if df.is_empty():
            return []

        records: list[dict] = []
        for row in df.to_dicts():
            ex_date = _parse(row.get("ex_date"))
            if ex_date is None:
                # 无除权日的事件无法在时间轴上对齐，跳过
                continue
            asset_id = _to_asset_id(row["ts_code"])
            ex_str = ex_date.strftime("%Y%m%d")
            cash_div = row.get("cash_div")
            stk_div = row.get("stk_div")
            # action_id: asset_id + ex_date + type，唯一标识一条已实施分红
            action_id = f"{asset_id}:{ex_str}:dividend"

            # stk_div (每股送转股) 映射到 ratio 列；cash_div 映射到 cash_amount 列
            ratio = float(stk_div) if stk_div is not None else None
            cash_amount = float(cash_div) if cash_div is not None else None

            records.append({
                "action_id": action_id,
                "asset_id": asset_id,
                "action_type": "dividend",
                "ex_date": ex_date,
                "record_date": _parse(row.get("record_date")),
                "pay_date": None,  # pro.dividend 未单独提供派息日，留空
                "ratio": ratio,
                "cash_amount": cash_amount,
                "currency": "CNY",
                "description": None,
                "source": "tushare",
            })
        return records

    def fetch_fundamentals(self, ts_code: str, period: str) -> list[dict]:
        """从 pro.fina_indicator 取财报指标，f_ann_date 优先（决策 5-B）。"""
        pro = self._get_pro()
        df_pd = pro.fina_indicator(  # type: ignore[union-attr]
            ts_code=ts_code, period=period,
            fields="ts_code,ann_date,f_ann_date,end_date,roe,roa,grossprofit_margin,"
                   "netprofit_margin,dt_profprofit_growth_rate,or_yoy,q_profit_yoy",
        )
        df = pl.from_pandas(df_pd)
        records: list[dict] = []
        for row in df.to_dicts():
            announce_raw = row.get("f_ann_date") or row.get("ann_date")  # f_ann_date 优先
            records.append({
                "asset_id": _to_asset_id(row["ts_code"]),
                "report_date": _parse(row["end_date"]),
                "announce_date": _parse(announce_raw),
                "roe": row.get("roe"),
                "roa": row.get("roa"),
                "gross_margin": row.get("grossprofit_margin"),
                "net_margin": row.get("netprofit_margin"),
            })
        return records


def _to_tushare_code(asset_id: str) -> str:
    """Convert cQuant asset_id (e.g. 'SSE:600036') to Tushare code ('600036.SH')."""
    if ":" not in asset_id:
        return asset_id
    exchange, symbol = asset_id.split(":", 1)
    suffix = {"SSE": "SH", "SZSE": "SZ"}.get(exchange, exchange)
    return f"{symbol}.{suffix}"


def _to_asset_id(ts_code: str) -> str:
    """Convert Tushare code (e.g. '600036.SH') to cQuant asset_id ('SSE:600036')."""
    if "." not in ts_code:
        return ts_code
    symbol, suffix = ts_code.split(".", 1)
    exchange = {"SH": "SSE", "SZ": "SZSE"}.get(suffix, suffix)
    return f"{exchange}:{symbol}"


def _parse(date_str: str | None) -> datetime | None:
    """Parse a Tushare date string (YYYYMMDD or YYYY-MM-DD) into a datetime."""
    if not date_str:
        return None
    clean = date_str.replace("-", "")
    try:
        return datetime.strptime(clean, "%Y%m%d")
    except (ValueError, TypeError):
        return None
