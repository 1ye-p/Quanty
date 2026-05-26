"""Cross-sectional factor scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import polars as pl
import duckdb


@dataclass
class FactorWeight:
    """单因子权重配置。"""
    factor_name: str
    weight: float = 1.0
    direction: Literal["long", "short"] = "long"


@dataclass
class ScoringConfig:
    """截面打分配置。"""
    name: str
    factors: list[FactorWeight]
    neutralize: list[str] = field(default_factory=list)
    winsorize: tuple[float, float] = (0.01, 0.99)
    fill_null: Literal["median", "mean", "zero"] = "median"


class CrossSectionScorer:
    """截面打分器。"""

    def __init__(self, catalog: duckdb.DuckDBPyConnection):
        self.catalog = catalog

    def score(
        self,
        config: ScoringConfig,
        feature_set_version: str,
        start_date: str,
        end_date: str,
    ) -> pl.DataFrame:
        """
        执行截面打分。

        Returns: pl.DataFrame with columns [trade_date, asset_id, score, rank]
        """
        factors_df = self._load_factors(config, feature_set_version, start_date, end_date)
        if factors_df.is_empty():
            return pl.DataFrame({"trade_date": [], "asset_id": [], "score": [], "rank": []})

        scored = self._normalize_cross_section(factors_df, config)
        scored = self._weighted_sum(scored, config.factors)
        scored = scored.with_columns(
            pl.col("score").over("trade_date").rank(descending=True).alias("rank")
        )
        return scored.select(["trade_date", "asset_id", "score", "rank"])

    def _load_factors(
        self, config: ScoringConfig, feature_set_version: str, start_date: str, end_date: str
    ) -> pl.DataFrame:
        """从 gold_factor_values 加载指定因子，pivot 为宽表。"""
        factor_names = [fw.factor_name for fw in config.factors]
        in_ph = ",".join(["?" for _ in factor_names])
        params = [feature_set_version] + factor_names + [start_date, end_date]
        df = self.catalog.query(
            f"SELECT asset_id, trade_date, factor_name, value "
            f"FROM gold_factor_values "
            f"WHERE feature_set_version = ? AND factor_name IN ({in_ph}) "
            f"AND trade_date >= ? AND trade_date <= ?",
            params,
        )
        if df.is_empty():
            return df
        return df.pivot(
            index=["asset_id", "trade_date"],
            columns="factor_name",
            values="value",
        )

    def _normalize_cross_section(self, df: pl.DataFrame, config: ScoringConfig) -> pl.DataFrame:
        """截面标准化：winsorize + fill_null + zscore。"""
        factor_cols = [fw.factor_name for fw in config.factors]
        factor_cols = [c for c in factor_cols if c in df.columns]
        if not factor_cols:
            return df

        lo, hi = config.winsorize
        for col in factor_cols:
            q_lo = pl.col(col).quantile(lo).over("trade_date")
            q_hi = pl.col(col).quantile(hi).over("trade_date")
            df = df.with_columns(
                pl.when(pl.col(col) < q_lo)
                .then(q_lo)
                .when(pl.col(col) > q_hi)
                .then(q_hi)
                .otherwise(pl.col(col))
                .alias(col)
            )

        if config.fill_null == "median":
            for col in factor_cols:
                median_val = pl.col(col).median().over("trade_date")
                df = df.with_columns(pl.col(col).fill_null(median_val))
        elif config.fill_null == "mean":
            for col in factor_cols:
                mean_val = pl.col(col).mean().over("trade_date")
                df = df.with_columns(pl.col(col).fill_null(mean_val))
        else:
            df = df.with_columns([pl.col(c).fill_null(0.0) for c in factor_cols])

        for col in factor_cols:
            mean_val = pl.col(col).mean().over("trade_date")
            std_val = pl.col(col).std().over("trade_date")
            df = df.with_columns(
                ((pl.col(col) - mean_val) / std_val).alias(col)
            )

        return df

    def _weighted_sum(self, df: pl.DataFrame, factors: list[FactorWeight]) -> pl.DataFrame:
        """加权求和得到综合得分。"""
        expr = None
        for fw in factors:
            if fw.factor_name not in df.columns:
                continue
            sign = -1.0 if fw.direction == "short" else 1.0
            term = pl.col(fw.factor_name) * fw.weight * sign
            expr = term if expr is None else expr + term
        if expr is None:
            df = df.with_columns(pl.lit(0.0).alias("score"))
        else:
            df = df.with_columns(expr.alias("score"))
        return df
