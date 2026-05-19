"""cquant.backtest_vector.metrics — Standard backtest performance metrics.

All metrics are computed from a returns Series (daily or at bar frequency).
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
import polars as pl


class BacktestMetrics(NamedTuple):
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

    # Beta (optional, requires benchmark)
    beta = None
    if benchmark_returns is not None:
        bm = benchmark_returns.to_numpy()
        if len(bm) == n:
            cov = np.cov(r, bm)
            bm_var = cov[1, 1]
            if bm_var > 1e-12:
                beta = float(cov[0, 1] / bm_var)

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
    )
