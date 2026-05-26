"""Alpha158 KBAR 因子 — 基于单日 OHLC 数据的 K 线形态因子。

来源：Microsoft Qlib Alpha158DL.get_feature_config() KBAR 组
参考：https://guorn.com/static/upload/file/3/134065454575605.pdf
"""
from __future__ import annotations

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class _KbarBase(Factor):
    @property
    def description(self) -> str:
        return (self.__class__.__doc__ or "").strip().split("\n")[0]

    @property
    def tags(self) -> list[str]:
        return ["alpha158", "kbar", "price"]


class KMID(_KbarBase):
    """K 线中间位置：(close - open) / open"""
    @property
    def name(self) -> str:
        return "KMID"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            (frame["close"] - frame["open"]) / frame["open"].clip(lower_bound=1e-12)
        ).alias(self.name)


class KLEN(_KbarBase):
    """K 线长度：(high - low) / open"""
    @property
    def name(self) -> str:
        return "KLEN"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            (frame["high"] - frame["low"]) / frame["open"].clip(lower_bound=1e-12)
        ).alias(self.name)


class KMID2(_KbarBase):
    """K 线中间位置（归一化）：(close - open) / (high - low + 1e-12)"""
    @property
    def name(self) -> str:
        return "KMID2"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            (frame["close"] - frame["open"]) /
            (frame["high"] - frame["low"] + 1e-12)
        ).alias(self.name)


class KUP(_KbarBase):
    """上影线长度：(high - max(open, close)) / open"""
    @property
    def name(self) -> str:
        return "KUP"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        upper_body = frame.select(
            pl.max_horizontal("open", "close").alias("_ub")
        )["_ub"]
        return (
            (frame["high"] - upper_body) / frame["open"].clip(lower_bound=1e-12)
        ).alias(self.name)


class KUP2(_KbarBase):
    """上影线长度（归一化）：(high - max(open, close)) / (high - low + 1e-12)"""
    @property
    def name(self) -> str:
        return "KUP2"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        upper_body = frame.select(
            pl.max_horizontal("open", "close").alias("_ub")
        )["_ub"]
        return (
            (frame["high"] - upper_body) /
            (frame["high"] - frame["low"] + 1e-12)
        ).alias(self.name)


class KLOW(_KbarBase):
    """下影线长度：(min(open, close) - low) / open"""
    @property
    def name(self) -> str:
        return "KLOW"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        lower_body = frame.select(
            pl.min_horizontal("open", "close").alias("_lb")
        )["_lb"]
        return (
            (lower_body - frame["low"]) / frame["open"].clip(lower_bound=1e-12)
        ).alias(self.name)


class KLOW2(_KbarBase):
    """下影线长度（归一化）：(min(open, close) - low) / (high - low + 1e-12)"""
    @property
    def name(self) -> str:
        return "KLOW2"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        lower_body = frame.select(
            pl.min_horizontal("open", "close").alias("_lb")
        )["_lb"]
        return (
            (lower_body - frame["low"]) /
            (frame["high"] - frame["low"] + 1e-12)
        ).alias(self.name)


class KSFT(_KbarBase):
    """K 线偏移量：(2 × close - high - low) / open"""
    @property
    def name(self) -> str:
        return "KSFT"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            (2 * frame["close"] - frame["high"] - frame["low"]) /
            frame["open"].clip(lower_bound=1e-12)
        ).alias(self.name)


class KSFT2(_KbarBase):
    """K 线偏移量（归一化）：(2 × close - high - low) / (high - low + 1e-12)"""
    @property
    def name(self) -> str:
        return "KSFT2"

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        return (
            (2 * frame["close"] - frame["high"] - frame["low"]) /
            (frame["high"] - frame["low"] + 1e-12)
        ).alias(self.name)


KBAR_FACTORS: list[Factor] = [
    KMID(), KLEN(), KMID2(),
    KUP(), KUP2(),
    KLOW(), KLOW2(),
    KSFT(), KSFT2(),
]
