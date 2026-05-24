"""cquant.backtest_vector.metrics — Standard backtest performance metrics.

All metrics are computed from a returns Series (daily or at bar frequency).
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
import polars as pl


class BacktestMetrics(NamedTuple):
    """Standard backtest performance metrics.

    WARNING: New fields with defaults were added after the initial release.
    Do NOT unpack positionally (e.g., `a, b, c, ... = compute_metrics(...)`).
    Use attribute access instead: `m = compute_metrics(...); m.sharpe_ratio`.
    """
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    var_95: float
    cvar_95: float
    beta: float | None
    total_trades: int
    trading_days: int
    # Active management metrics (require benchmark_returns)
    information_ratio: float | None = None
    tracking_error: float | None = None
    alpha: float | None = None
    omega_ratio: float | None = None
    tail_ratio: float | None = None


def compute_metrics(
    returns: pl.Series,
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = 252,
    benchmark_returns: pl.Series | None = None,
    total_fills: int | None = None,
) -> BacktestMetrics:
    """Compute standard metrics from a daily returns Series.

    Parameters
    ----------
    returns : pl.Series
        Daily (or bar-frequency) returns.
    risk_free_rate : float
        Annualized risk-free rate.
    trading_days_per_year : int
        Trading days per year for annualization.
    benchmark_returns : pl.Series | None
        Optional benchmark returns for beta calculation.
    total_fills : int | None
        Explicit fill count; if None, defaults to len(returns).
    """
    if returns.is_empty():
        return BacktestMetrics(
            total_return=0.0, annualized_return=0.0, annualized_volatility=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0,
            max_drawdown=0.0, calmar_ratio=0.0,
            win_rate=0.0, profit_factor=0.0,
            var_95=0.0, cvar_95=0.0, beta=None,
            total_trades=0, trading_days=0,
            omega_ratio=None, tail_ratio=None,
        )

    r = returns.to_numpy()
    n = len(r)
    daily_rf = risk_free_rate / trading_days_per_year

    # Total return
    total_return = float((1 + r).prod() - 1)

    # Annualized return (CAGR)
    years = n / trading_days_per_year
    annualized_return = float((1 + total_return) ** (1 / years) - 1) if years > 0 else 0.0

    # Annualized volatility
    vol = float(r.std(ddof=1)) * math.sqrt(trading_days_per_year) if n > 1 else 0.0

    # Sharpe ratio
    excess = r.mean() - daily_rf
    sharpe = float(excess / (r.std(ddof=1) + 1e-12)) * math.sqrt(trading_days_per_year)

    # Sortino ratio
    downside_returns = np.minimum(r - daily_rf, 0.0)
    downside_dev = np.sqrt(np.mean(downside_returns ** 2))
    sortino_ratio = float(np.mean(excess) / (downside_dev + 1e-12) * np.sqrt(trading_days_per_year))

    # Maximum drawdown
    cumulative = (1 + r).cumprod()
    rolling_max = np.maximum.accumulate(cumulative)
    drawdowns = cumulative / rolling_max - 1
    max_drawdown = float(drawdowns.min())

    # Calmar ratio
    calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

    # Win rate and profit factor
    wins = r[r > 0]
    losses = r[r < 0]
    win_rate = len(wins) / n if n > 0 else 0.0
    profit_factor = (wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf")

    # VaR and CVaR (95%)
    sorted_returns = np.sort(r)
    var_idx = int(np.floor(0.05 * n))
    var_95 = float(sorted_returns[var_idx]) if var_idx < n else float(sorted_returns[-1])
    cvar_95 = float(np.mean(sorted_returns[: var_idx + 1])) if var_idx > 0 else var_95

    # Omega Ratio = 期望超额收益 / 期望超额亏损（相对 daily_rf）
    above_threshold = np.maximum(r - daily_rf, 0.0)
    below_threshold = np.maximum(daily_rf - r, 0.0)
    omega_ratio: float | None = float(np.mean(above_threshold) / (np.mean(below_threshold) + 1e-12))

    # Tail Ratio = P95(收益率) / |P5(收益率)|
    p95 = float(np.percentile(r, 95))
    p5 = float(np.percentile(r, 5))
    tail_ratio: float | None = p95 / abs(p5) if abs(p5) > 1e-12 else None

    # Beta (optional, requires benchmark)
    beta = None
    if benchmark_returns is not None:
        bm = benchmark_returns.to_numpy()
        if len(bm) == n:
            cov = np.cov(r, bm)
            bm_var = cov[1, 1]
            if bm_var > 1e-12:
                beta = float(cov[0, 1] / bm_var)

    # Active management metrics (only when benchmark is provided)
    information_ratio = None
    tracking_error = None
    alpha = None

    if benchmark_returns is not None:
        bm = benchmark_returns.to_numpy()
        if len(bm) == n and n > 1:
            active_returns = r - bm
            te = float(np.std(active_returns, ddof=1)) * math.sqrt(trading_days_per_year)
            tracking_error = te

            bm_total = float((1 + bm).prod() - 1)
            bm_annualized = (
                float((1 + bm_total) ** (1 / years) - 1) if years > 0 else 0.0
            )
            active_return = annualized_return - bm_annualized
            information_ratio = active_return / te if te > 1e-12 else None

            if beta is not None:
                rf_annual = risk_free_rate
                alpha = annualized_return - rf_annual - beta * (bm_annualized - rf_annual)

    return BacktestMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=vol,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_drawdown,
        calmar_ratio=calmar,
        win_rate=win_rate,
        profit_factor=profit_factor,
        var_95=var_95,
        cvar_95=cvar_95,
        beta=beta,
        total_trades=total_fills if total_fills is not None else n,
        trading_days=n,
        information_ratio=information_ratio,
        tracking_error=tracking_error,
        alpha=alpha,
        omega_ratio=omega_ratio,
        tail_ratio=tail_ratio,
    )


def compute_portfolio_turnover(positions: "pl.DataFrame") -> float:
    """计算组合平均单边换手率。

    turnover = sum(|weight_i(t) - weight_i(t-1)|) / 2，对所有再平衡日取均值。
    返回介于 [0, 1] 的浮点数。
    """
    import polars as pl

    if positions.is_empty() or "target_weight" not in positions.columns:
        return 0.0

    sorted_dates = sorted(positions["trade_date"].unique().to_list())
    if len(sorted_dates) < 2:
        return 0.0

    turnovers: list[float] = []
    for i in range(1, len(sorted_dates)):
        prev_date = sorted_dates[i - 1]
        curr_date = sorted_dates[i]

        prev = positions.filter(pl.col("trade_date") == prev_date).select(
            ["asset_id", pl.col("target_weight").alias("w_prev")]
        )
        curr = positions.filter(pl.col("trade_date") == curr_date).select(
            ["asset_id", pl.col("target_weight").alias("w_curr")]
        )

        merged = prev.join(curr, on="asset_id", how="full", coalesce=True).fill_null(0.0)
        daily_turnover = float((merged["w_curr"] - merged["w_prev"]).abs().sum()) / 2.0
        turnovers.append(daily_turnover)

    return float(sum(turnovers) / len(turnovers)) if turnovers else 0.0


def compute_hhi(positions: "pl.DataFrame") -> float:
    """计算最后一个再平衡日的 Herfindahl-Hirschman Index（持仓集中度）。

    HHI = sum(w_i^2)，范围 [1/N, 1]。越接近 1 越集中。
    """
    import polars as pl

    if positions.is_empty() or "target_weight" not in positions.columns:
        return 0.0

    last_date = positions["trade_date"].max()
    last_positions = positions.filter(pl.col("trade_date") == last_date)
    weights = last_positions["target_weight"].to_numpy()
    return float((weights ** 2).sum())
