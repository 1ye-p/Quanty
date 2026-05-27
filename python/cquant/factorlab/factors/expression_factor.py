"""ExpressionFactor — user-defined factor via Python expression."""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


# 受限命名空间中可用的安全函数
# NOTE: `sum` and `range` are intentionally excluded — `sum(range(N))` is an O(N)
# DoS vector. Use Polars aggregation functions (e.g. pl.col('x').sum()) instead.
_SAFE_BUILTINS = {
    "abs": abs, "max": max, "min": min, "round": round,
    "len": len,
    "int": int, "float": float, "str": str, "bool": bool,
    "True": True, "False": False, "None": None,
}

# Explicit allow-list: omit factorial/gamma/perm/comb which can cause CPU exhaustion
_MATH_NS = {
    k: getattr(math, k) for k in (
        "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
        "sinh", "cosh", "tanh",
        "exp", "log", "log2", "log10", "sqrt", "pow",
        "floor", "ceil", "trunc", "fabs",
        "isnan", "isinf", "isfinite",
        "pi", "e", "tau", "inf", "nan",
    )
}


def _build_polars_helpers(frame: pl.DataFrame) -> dict[str, Any]:
    """构建可在表达式中使用的 Polars 辅助函数。"""
    def ma(col: str, n: int) -> pl.Expr:
        """N 日滚动均值。"""
        return pl.col(col).rolling_mean(window_size=n)

    def std(col: str, n: int) -> pl.Expr:
        """N 日滚动标准差。"""
        return pl.col(col).rolling_std(window_size=n)

    def shift(col: str, n: int) -> pl.Expr:
        """滞后 N 期。"""
        return pl.col(col).shift(n)

    def roc(col: str, n: int) -> pl.Expr:
        """N 日变动率：(x - x_n) / x_n."""
        return (pl.col(col) - pl.col(col).shift(n)) / pl.col(col).shift(n)

    def rank(col: str) -> pl.Expr:
        """截面排名（1/N 到 1.0），按交易日截面归一化。每日独立排名。"""
        return (
            pl.col(col).rank().over("trade_date")
            / pl.col(col).count().over("trade_date")
        )

    def log(col: str) -> pl.Expr:
        """自然对数。"""
        return pl.col(col).log(base=math.e)

    def sign(col: str) -> pl.Expr:
        """符号函数，返回 -1 / 0 / 1。"""
        return pl.col(col).sign()

    def rolling_corr(col_a: str, col_b: str, n: int) -> pl.Expr:
        """N 日滚动相关系数。"""
        return pl.rolling_corr(pl.col(col_a), pl.col(col_b), window_size=n)

    # 直接暴露列访问
    cols = {c: pl.col(c) for c in frame.columns}

    return {
        "ma": ma, "std": std, "shift": shift, "roc": roc,
        "rank": rank, "log": log, "sign": sign, "rolling_corr": rolling_corr,
        "col": pl.col, "lit": pl.lit, "when": pl.when,
        **cols,
    }


class ExpressionFactor(Factor):
    """用户自定义的 Python/Polars 表达式因子。"""

    def __init__(self, name: str, expression: str, description: str = "") -> None:
        self._name = name
        self._expression = expression
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description or f"自定义因子: {self._expression[:50]}"

    @property
    def tags(self) -> list[str]:
        return ["custom"]

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        """在受限命名空间中求值表达式并返回 Series。"""
        ns = {
            **_SAFE_BUILTINS,
            **_MATH_NS,
            **_build_polars_helpers(frame),
        }

        # Guard against object model escapes even in direct instantiation
        if "__" in self._expression:
            raise ValueError(
                f"表达式不允许使用 '__': {self._expression}"
            )

        try:
            result = eval(self._expression, {"__builtins__": {}}, ns)  # noqa: S307
        except Exception as exc:
            raise ValueError(
                f"表达式求值失败 [{self._name}]: {type(exc).__name__}: {exc}\n"
                f"表达式: {self._expression}"
            ) from exc

        # 将 pl.Expr 物化为 Series
        if isinstance(result, pl.Expr):
            try:
                result = frame.select(result.alias("v"))["v"]
            except Exception as exc:
                raise ValueError(
                    f"表达式 Polars 求值失败 [{self._name}]: {exc}\n"
                    f"表达式: {self._expression}"
                ) from exc

        if not isinstance(result, pl.Series):
            raise TypeError(
                f"表达式必须返回 pl.Series 或 pl.Expr，实际返回: {type(result).__name__}"
            )

        if len(result) != len(frame):
            raise ValueError(
                f"返回 Series 长度 ({len(result)}) 与 DataFrame ({len(frame)}) 不匹配"
            )

        return result.alias(self._name)

    @classmethod
    def validate_expression(
        cls, expression: str, sample_frame: pl.DataFrame | None = None
    ) -> dict:
        """验证表达式语法和执行可行性，返回 {valid, error}。"""
        # 语法检查
        try:
            compile(expression, "<expression>", "eval")
        except SyntaxError as e:
            return {"valid": False, "error": f"语法错误: {e}"}

        # 危险模式检查
        forbidden = ["import ", "__", "open(", "exec(", "eval(", "os.", "sys."]
        for pat in forbidden:
            if pat in expression:
                return {"valid": False, "error": f"不允许使用: {pat}"}

        # 如果有样本数据则试运行
        if sample_frame is not None and not sample_frame.is_empty():
            try:
                factor = cls("__preview__", expression)
                factor.compute(sample_frame, None)  # type: ignore
            except Exception as exc:
                return {"valid": False, "error": str(exc)}

        return {"valid": True, "error": None}
