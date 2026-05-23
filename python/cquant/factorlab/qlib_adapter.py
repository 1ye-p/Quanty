"""cquant.factorlab.qlib_adapter — DuckDB → Qlib 数据适配层。

将 DuckDB silver/gold 层数据转换为 Qlib MultiIndex 格式，
使 cQuant 能调用 Qlib 的 ML 模型、因子评估和风险分析工具。

Qlib 期望的格式：
- pandas DataFrame，索引为 (datetime, instrument) MultiIndex
- 价格列名：$open, $high, $low, $close, $volume
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


class DuckDBToQlibAdapter:
    """将 DuckDB 中的价格和因子数据转换为 Qlib 兼容格式。

    Usage::

        adapter = DuckDBToQlibAdapter(catalog)
        prices_df = adapter.load_prices(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
    """

    def __init__(self, catalog: "Catalog") -> None:
        self._catalog = catalog

    def load_prices(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        instruments: list[str] | None = None,
    ) -> pd.DataFrame:
        """从 silver_prices_1d 加载价格数据，转换为 Qlib MultiIndex 格式。

        Returns
        -------
        pandas DataFrame，MultiIndex (datetime, instrument)，
        列名为 ``$open``, ``$high``, ``$low``, ``$close``, ``$volume``。
        """
        import polars as pl

        conditions = []
        params = []
        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date.isoformat())

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT asset_id, trade_date, open, high, low, close, volume
            FROM silver_prices_1d
            {where_clause}
            ORDER BY trade_date, asset_id
        """
        polars_df = self._catalog.query(sql, params if params else None)

        if polars_df.is_empty():
            return pd.DataFrame()

        if instruments:
            polars_df = polars_df.filter(pl.col("asset_id").is_in(instruments))
            if polars_df.is_empty():
                return pd.DataFrame()

        pdf = polars_df.to_pandas()
        pdf["trade_date"] = pd.to_datetime(pdf["trade_date"])
        pdf = pdf.rename(columns={
            "asset_id": "instrument",
            "trade_date": "datetime",
            "open": "$open",
            "high": "$high",
            "low": "$low",
            "close": "$close",
            "volume": "$volume",
        })
        pdf = pdf.set_index(["datetime", "instrument"]).sort_index()
        return pdf

    def load_factors(
        self,
        feature_set_version: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """从 gold_factor_values 加载因子数据，转换为 Qlib MultiIndex 格式（宽表）。

        Returns
        -------
        pandas DataFrame，MultiIndex (datetime, instrument)，每因子一列。
        """
        import polars as pl

        conditions = ["feature_set_version = ?"]
        params: list = [feature_set_version]
        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date.isoformat())

        where_clause = "WHERE " + " AND ".join(conditions)
        sql = f"""
            SELECT asset_id, trade_date, factor_name, value
            FROM gold_factor_values
            {where_clause}
            ORDER BY trade_date, asset_id
        """
        polars_df = self._catalog.query(sql, params)

        if polars_df.is_empty():
            return pd.DataFrame()

        wide = polars_df.pivot(
            index=["asset_id", "trade_date"],
            on="factor_name",
            values="value",
        )

        pdf = wide.to_pandas()
        pdf["trade_date"] = pd.to_datetime(pdf["trade_date"])
        pdf = pdf.rename(columns={"asset_id": "instrument", "trade_date": "datetime"})
        pdf = pdf.set_index(["datetime", "instrument"]).sort_index()
        return pdf
