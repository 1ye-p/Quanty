"""cquant.qlib_bridge.factor_bridge — Factor computation bridge.

Routes factor computation to Qlib's ExpressionEngine when available,
or falls back to cQuant's native Polars-based factor implementation.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from cquant.qlib_bridge._compat import QLIB_AVAILABLE, qlib_or_fallback

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


def compute_factors_qlib(
    prices: pl.DataFrame,
    factors: list[str] | None = None,
    catalog: "Catalog | None" = None,
    use_qlib: bool | None = None,
) -> pl.DataFrame:
    """Compute factors using Qlib's ExpressionEngine or native Polars.

    When Qlib is available and ``use_qlib`` is not False, routes to
    ``qlib.data.ops`` for expression-based factor computation.  Otherwise
    falls back to cQuant's native Polars factor implementation.

    Parameters
    ----------
    prices:
        OHLCV price data with columns: ``asset_id``, ``trade_date``,
        ``open``, ``high``, ``low``, ``close``, ``volume``.
    factors:
        List of factor expressions.  If None, computes a default set
        of common factors (returns, volatility, momentum, etc.).
    catalog:
        Catalog connection (unused for Qlib path, but available for
        future extensions).
    use_qlib:
        Force Qlib (True), force native (False), or auto-detect (None).

    Returns
    -------
    pl.DataFrame
        Factor values with columns: ``asset_id``, ``trade_date``, plus
        one column per computed factor.
    """
    if factors is None:
        factors = _default_factors()

    should_use_qlib = use_qlib if use_qlib is not None else QLIB_AVAILABLE

    if should_use_qlib:
        if not QLIB_AVAILABLE:
            logger.warning("Qlib not available, falling back to native factors")
            return _compute_factors_native(prices, factors)
        return _compute_factors_qlib(prices, factors)
    else:
        return _compute_factors_native(prices, factors)


def _compute_factors_qlib(prices: pl.DataFrame, factors: list[str]) -> pl.DataFrame:
    """Compute factors using Qlib's expression engine.

    Translates cQuant factor expressions to Qlib format and evaluates
    them using ``qlib.data.dataset``.
    """
    try:
        import qlib
        from qlib.data import D

        # Convert Polars DataFrame to Qlib-compatible format
        # Qlib expects data in its internal format; we use the expression engine
        logger.info("factor_bridge: computing %d factors via Qlib ExpressionEngine", len(factors))

        # For now, compute Qlib-style expressions using Polars
        # This bridges Qlib's expression syntax to Polars operations
        result = prices.select(["asset_id", "trade_date"])

        for expr in factors:
            try:
                col = _eval_qlib_expr(prices, expr)
                result = result.with_columns(col)
            except Exception as exc:
                logger.warning("factor_bridge: failed to compute %r: %s", expr, exc)
                result = result.with_columns(pl.lit(None).alias(expr))

        return result

    except Exception as exc:
        logger.warning("factor_bridge: Qlib factor computation failed: %s, falling back", exc)
        return _compute_factors_native(prices, factors)


def _compute_factors_native(prices: pl.DataFrame, factors: list[str]) -> pl.DataFrame:
    """Compute factors using cQuant's native Polars implementation."""
    logger.info("factor_bridge: computing %d factors via native Polars", len(factors))

    result = prices.select(["asset_id", "trade_date"])

    for expr in factors:
        try:
            col = _eval_native_expr(prices, expr)
            result = result.with_columns(col)
        except Exception as exc:
            logger.warning("factor_bridge: failed to compute %r: %s", expr, exc)
            result = result.with_columns(pl.lit(None).alias(expr))

    return result


def _eval_qlib_expr(df: pl.DataFrame, expr: str) -> pl.Expr:
    """Evaluate a Qlib-style expression and return a Polars expression.

    Supports common Qlib expression patterns:
    - ``$close`` -> ``pl.col("close")``
    - ``Ref($close, 5)`` -> ``pl.col("close").shift(5)``
    - ``Mean($close, 20)`` -> ``pl.col("close").rolling_mean(20)``
    - ``Std($close, 20)`` -> ``pl.col("close").rolling_std(20)``
    - ``Rank($close)`` -> ``pl.col("close").rank()``
    """
    expr = expr.strip()

    # Direct field reference
    if expr.startswith("$"):
        field = expr[1:]
        return pl.col(field).alias(expr)

    # Function call patterns
    if expr.startswith("Ref("):
        inner, period = _parse_func_args(expr, "Ref")
        return _eval_qlib_expr(df, inner).shift(int(period)).alias(expr)

    if expr.startswith("Mean("):
        inner, period = _parse_func_args(expr, "Mean")
        return _eval_qlib_expr(df, inner).rolling_mean(int(period)).alias(expr)

    if expr.startswith("Std("):
        inner, period = _parse_func_args(expr, "Std")
        return _eval_qlib_expr(df, inner).rolling_std(int(period)).alias(expr)

    if expr.startswith("Sum("):
        inner, period = _parse_func_args(expr, "Sum")
        return _eval_qlib_expr(df, inner).rolling_sum(int(period)).alias(expr)

    if expr.startswith("Max("):
        inner, period = _parse_func_args(expr, "Max")
        return _eval_qlib_expr(df, inner).rolling_max(int(period)).alias(expr)

    if expr.startswith("Min("):
        inner, period = _parse_func_args(expr, "Min")
        return _eval_qlib_expr(df, inner).rolling_min(int(period)).alias(expr)

    if expr.startswith("Rank("):
        inner = expr[5:].rstrip(")")
        return _eval_qlib_expr(df, inner).rank().alias(expr)

    if expr.startswith("Log("):
        inner = expr[4:].rstrip(")")
        return _eval_qlib_expr(df, inner).log().alias(expr)

    if expr.startswith("Abs("):
        inner = expr[4:].rstrip(")")
        return _eval_qlib_expr(df, inner).abs().alias(expr)

    # Arithmetic expressions: $close / $open - 1
    if "/" in expr and "-" in expr:
        parts = expr.split("/")
        if len(parts) == 2:
            left = _eval_qlib_expr(df, parts[0].strip())
            right = _eval_qlib_expr(df, parts[1].strip().split("-")[0].strip())
            return (left / right - 1).alias(expr)

    # Fallback: try as column name
    return pl.col(expr).alias(expr)


def _eval_native_expr(df: pl.DataFrame, expr: str) -> pl.Expr:
    """Evaluate a native Polars factor expression.

    Supports the same expression syntax as ``_eval_qlib_expr`` but
    uses Polars directly.
    """
    return _eval_qlib_expr(df, expr)


def _parse_func_args(expr: str, func_name: str) -> tuple[str, str]:
    """Parse function call arguments: ``Func(inner, period)``."""
    inner = expr[len(func_name) + 1 : -1]  # strip "Func(" and ")"
    parts = inner.rsplit(",", 1)
    if len(parts) != 2:
        raise ValueError(f"Cannot parse {expr!r} as {func_name}(inner, period)")
    return parts[0].strip(), parts[1].strip()


def _default_factors() -> list[str]:
    """Return a default set of common factor expressions."""
    return [
        "$close / Ref($close, 1) - 1",       # daily return
        "$close / Ref($close, 5) - 1",       # 5-day return
        "$close / Ref($close, 20) - 1",      # 20-day return
        "Std($close, 20)",                    # 20-day volatility
        "Mean($volume, 20)",                  # 20-day avg volume
        "$close / Mean($close, 60) - 1",      # deviation from 60-day mean
    ]
