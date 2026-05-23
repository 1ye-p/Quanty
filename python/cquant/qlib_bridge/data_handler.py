"""cquant.qlib_bridge.data_handler — DuckDB → Qlib 数据适配层。

CQuantDataHandler 封装 DuckDB 数据加载和格式转换。
外部只调用此类，不直接使用 qlib.DataHandlerLP。
所有输入输出均为 Polars DataFrame/Series。
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


class CQuantDataHandler:
    """将 cQuant DuckDB 数据适配为 Qlib DataHandlerLP。

    外部只调用此类，不直接使用 qlib.DataHandlerLP。
    所有输入输出均为 Polars DataFrame/Series。

    Usage::

        handler = CQuantDataHandler.from_catalog(
            catalog=catalog,
            dataset_version="tdx_bulk_v1",
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
        )
        features_df = handler.fetch_features()
        labels = handler.fetch_labels(horizon=5)
    """

    def __init__(
        self,
        prices_df: pl.DataFrame,
        factors_df: pl.DataFrame | None = None,
    ) -> None:
        self._prices_df = prices_df
        self._factors_df = factors_df

    @classmethod
    def from_catalog(
        cls,
        catalog: "Catalog",
        dataset_version: str,
        start: date,
        end: date,
        feature_set_version: str = "",
    ) -> "CQuantDataHandler":
        """从 DuckDB 加载价格（和可选因子）数据，构建 CQuantDataHandler。

        Parameters
        ----------
        catalog:
            已初始化的 DuckDB Catalog 连接。
        dataset_version:
            价格数据集版本标识（当前仅用于日志记录）。
        start, end:
            数据日期范围。
        feature_set_version:
            因子集版本 ID；为空时不加载因子数据。
        """
        prices_df = catalog.query(
            """
            SELECT asset_id, trade_date, open, high, low, close, volume
            FROM silver_prices_1d
            WHERE trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date, asset_id
            """,
            [start.isoformat(), end.isoformat()],
        )
        if prices_df.is_empty():
            logger.warning("CQuantDataHandler: 日期范围 %s~%s 无价格数据", start, end)
            return cls(prices_df=pl.DataFrame())

        factors_df: pl.DataFrame | None = None
        if feature_set_version:
            raw = catalog.query(
                """
                SELECT asset_id, trade_date, factor_name, value
                FROM gold_factor_values
                WHERE feature_set_version = ?
                  AND trade_date >= ? AND trade_date <= ?
                """,
                [feature_set_version, start.isoformat(), end.isoformat()],
            )
            if not raw.is_empty():
                factors_df = raw.pivot(
                    index=["asset_id", "trade_date"],
                    on="factor_name",
                    values="value",
                )

        logger.info(
            "CQuantDataHandler 加载完成：%d 行价格，因子=%s",
            len(prices_df),
            "有" if factors_df is not None else "无",
        )
        return cls(prices_df=prices_df, factors_df=factors_df)

    def fetch_features(self) -> pl.DataFrame:
        """返回特征 DataFrame（因子宽表）。

        如无因子数据，返回仅含 asset_id + trade_date 的空结构。
        """
        if self._factors_df is not None and not self._factors_df.is_empty():
            return self._factors_df.clone()
        return (
            self._prices_df.select(["asset_id", "trade_date"])
            if not self._prices_df.is_empty()
            else pl.DataFrame()
        )

    def fetch_labels(self, horizon: int = 5) -> pl.Series:
        """计算前瞻 horizon 天的收益率标签。

        Returns
        -------
        pl.Series，名称为 ``f"ret_{horizon}d"``，与 prices_df 行数相同。
        """
        if self._prices_df.is_empty():
            return pl.Series(name=f"ret_{horizon}d", values=[])

        return (
            self._prices_df.sort(["asset_id", "trade_date"])
            .with_columns(
                (
                    pl.col("close").shift(-horizon).over("asset_id") /
                    pl.col("close").clip(lower_bound=1e-12) - 1
                ).alias(f"ret_{horizon}d")
            )
        )[f"ret_{horizon}d"]
