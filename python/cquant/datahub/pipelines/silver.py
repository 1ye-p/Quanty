"""cquant.datahub.pipelines.silver — Normalize raw batches to Silver schema.

Silver normalization rules:
- Unify asset_id to '{exchange}:{symbol}' format
- Normalize column names to cQuant canonical names
- Parse trade_date to Python date
- Retain both raw price and adj_factor for forward adjustment
- Mark suspended days and price limits (via market_calendar injection)
"""

from __future__ import annotations

import logging
from datetime import date

import polars as pl

from cquant.core.enums import Exchange
from cquant.datahub.connectors.base import RawBatch

logger = logging.getLogger(__name__)

# ── Column name maps per source ────────────────────────────────────────────────
_AKSHARE_RENAME = {
    "日期": "trade_date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
}

_TUSHARE_RENAME = {
    "trade_date": "trade_date",
    "open": "open",
    "close": "close",
    "high": "high",
    "low": "low",
    "vol": "volume",
    "amount": "amount",
    "ts_code": "_ts_code",
}

_YFINANCE_RENAME = {
    "Date": "trade_date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


class SilverNormalizer:
    """Transforms a RawBatch into a Silver-compatible Polars DataFrame."""

    def normalize(self, batch: RawBatch) -> pl.DataFrame:
        """Return a normalized Silver DataFrame from *batch*."""
        df = batch.data.clone()

        if batch.source == "akshare":
            df = self._normalize_akshare(df, batch)
        elif batch.source == "tushare":
            df = self._normalize_tushare(df, batch)
        elif batch.source == "yfinance":
            df = self._normalize_yfinance(df, batch)
        elif batch.source == "tdx":
            df = self._normalize_tdx(df, batch)
        elif batch.source == "csv_parquet":
            df = self._normalize_generic(df, batch)
        else:
            logger.warning("Unknown source %r; attempting generic normalization.", batch.source)
            df = self._normalize_generic(df, batch)

        df = self._ensure_required_columns(df)
        df = self._clean_data_quality(df)
        return df

    # ── Source-specific normalizers ────────────────────────────────────────────

    def _normalize_akshare(self, df: pl.DataFrame, batch: RawBatch) -> pl.DataFrame:
        rename = {k: v for k, v in _AKSHARE_RENAME.items() if k in df.columns}
        df = df.rename(rename)
        if "trade_date" in df.columns:
            df = df.with_columns(pl.col("trade_date").cast(pl.Date))
        # asset_id comes from the symbol column added by the connector
        if "symbol" in df.columns and "asset_id" not in df.columns:
            df = df.with_columns(
                pl.col("symbol").map_elements(_akshare_to_asset_id, return_dtype=pl.Utf8).alias("asset_id")
            )
        df = df.with_columns(pl.lit("akshare").alias("source"))
        return df

    def _normalize_tushare(self, df: pl.DataFrame, batch: RawBatch) -> pl.DataFrame:
        rename = {k: v for k, v in _TUSHARE_RENAME.items() if k in df.columns}
        df = df.rename(rename)
        if "trade_date" in df.columns:
            df = df.with_columns(pl.col("trade_date").cast(pl.Utf8).str.to_date("%Y%m%d"))
        if "_ts_code" in df.columns and "asset_id" not in df.columns:
            df = df.with_columns(
                pl.col("_ts_code").map_elements(_tushare_to_asset_id, return_dtype=pl.Utf8).alias("asset_id")
            ).drop("_ts_code")
        df = df.with_columns(pl.lit("tushare").alias("source"))
        return df

    def _normalize_yfinance(self, df: pl.DataFrame, batch: RawBatch) -> pl.DataFrame:
        rename = {k: v for k, v in _YFINANCE_RENAME.items() if k in df.columns}
        df = df.rename(rename)
        if "trade_date" in df.columns:
            df = df.with_columns(pl.col("trade_date").cast(pl.Date))
        if "symbol" in df.columns and "asset_id" not in df.columns:
            df = df.with_columns(pl.col("symbol").alias("asset_id"))
        df = df.with_columns(pl.lit("yfinance").alias("source"))
        return df

    def _normalize_tdx(self, df: pl.DataFrame, batch: RawBatch) -> pl.DataFrame:
        """Normalize TDX DuckDB data. Connector already provides asset_id."""
        if "date" in df.columns and "trade_date" not in df.columns:
            df = df.rename({"date": "trade_date"})
        if "trade_date" in df.columns:
            df = df.with_columns(pl.col("trade_date").cast(pl.Date))
        # TDX connector provides qfq_factor; use it as adj_factor
        if "qfq_factor" in df.columns:
            df = df.rename({"qfq_factor": "adj_factor"})
        df = df.with_columns(pl.lit("tdx").alias("source"))
        return df

    def _normalize_generic(self, df: pl.DataFrame, batch: RawBatch) -> pl.DataFrame:
        """Best-effort normalization for CSV/Parquet with standard column names."""
        if "date" in df.columns and "trade_date" not in df.columns:
            df = df.rename({"date": "trade_date"})
        if "trade_date" in df.columns:
            df = df.with_columns(pl.col("trade_date").cast(pl.Date, strict=False))
        df = df.with_columns(pl.lit(batch.source).alias("source"))
        return df

    # ── Schema enforcement ────────────────────────────────────────────────────

    def _ensure_required_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        required_float = ["open", "high", "low", "close", "volume"]
        for col in required_float:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).cast(pl.Float64).alias(col))
            else:
                df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))

        if "amount" not in df.columns:
            df = df.with_columns(pl.lit(0.0).alias("amount"))
        if "is_suspended" not in df.columns:
            df = df.with_columns(pl.lit(False).alias("is_suspended"))
        if "adj_factor" not in df.columns:
            df = df.with_columns(pl.lit(1.0).alias("adj_factor"))
        if "adj_close" not in df.columns:
            df = df.with_columns(
                (pl.col("close") * pl.col("adj_factor")).alias("adj_close")
            )

        return df.sort(["asset_id", "trade_date"]) if "asset_id" in df.columns else df

    def _clean_data_quality(self, df: pl.DataFrame) -> pl.DataFrame:
        """Filter obviously invalid price/volume data.

        Removes:
        - Rows with zero or negative close prices
        Clips:
        - Negative volumes to 0
        """
        # Remove rows with zero or negative close prices
        if "close" in df.columns:
            initial_len = len(df)
            df = df.filter(pl.col("close") > 0)
            removed = initial_len - len(df)
            if removed > 0:
                logger.warning(
                    "Removed %d rows with non-positive close price", removed
                )

        # Clip negative volumes to 0
        if "volume" in df.columns:
            df = df.with_columns(
                pl.col("volume").clip(lower_bound=0)
            )

        # 检测 adj_close 与 close 之间的异常跳空（adj_factor 突变信号）
        if "adj_close" in df.columns and "close" in df.columns:
            try:
                check_df = (
                    df.sort(["asset_id", "trade_date"])
                    .with_columns([
                        pl.col("adj_close").log().diff().over("asset_id").alias("_adj_ret"),
                        pl.col("close").log().diff().over("asset_id").alias("_raw_ret"),
                    ])
                )
                suspicious = check_df.filter(
                    (pl.col("_adj_ret").abs() > 0.30)
                    & (pl.col("_raw_ret").abs() < 0.10)
                )
                if not suspicious.is_empty():
                    logger.warning(
                        "检测到 %d 行疑似 adj_close 跳空异常（adj_factor 可能因除权/复权突变），"
                        "请检查相关 asset_id 和日期。",
                        len(suspicious),
                    )
            except Exception:
                pass  # 检测失败时静默忽略，不影响正常数据处理

        # ── Winsorize: 裁剪 adj_close 单日涨跌幅超过 ±50% 的异常行 ────────────
        # 日涨跌 > ±50% 几乎必然是复权数据错误或非连续交易日对比，直接删除
        if "adj_close" in df.columns and len(df) > 1:
            df_with_ret = df.sort(["asset_id", "trade_date"]).with_columns(
                (pl.col("adj_close") / pl.col("adj_close").shift(1).over("asset_id") - 1.0)
                .alias("_daily_ret_chk")
            )
            extreme_mask = df_with_ret["_daily_ret_chk"].abs() > 0.5
            n_extreme = int(extreme_mask.sum())
            if n_extreme > 0:
                logger.warning(
                    "Winsorize: 检测到 %d 行 adj_close 单日涨跌幅超过 ±50%%，已删除。",
                    n_extreme,
                )
                df = df_with_ret.filter(
                    pl.col("_daily_ret_chk").is_null() | (pl.col("_daily_ret_chk").abs() <= 0.5)
                ).drop("_daily_ret_chk")

        return df


def _tushare_to_asset_id(ts_code: str) -> str:
    """Convert Tushare ts_code ('600036.SH') to cQuant asset_id ('SSE:600036')."""
    if "." not in ts_code:
        return ts_code
    symbol, suffix = ts_code.rsplit(".", 1)
    exchange_map = {"SH": "SSE", "SZ": "SZSE"}
    exchange = exchange_map.get(suffix.upper(), suffix)
    return f"{exchange}:{symbol}"


def _akshare_to_asset_id(symbol: str) -> str:
    """Convert AKShare symbol ('600036' or '000001') to cQuant asset_id.

    A-share codes: 6xx = SSE, 0xx/3xx = SZSE, 688 = SSE (STAR), 300 = SZSE (ChiNext).
    """
    if not symbol or not symbol.isdigit():
        return symbol
    prefix = symbol[:3]
    if prefix.startswith("6"):
        return f"SSE:{symbol}"
    return f"SZSE:{symbol}"
