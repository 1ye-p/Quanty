"""Advanced risk analysis functions for backtest results.

Provides correlation analysis, factor exposure tracking, stress testing,
and risk contribution decomposition.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_correlation_matrix(
    price_df: pd.DataFrame,
    window: int = 60,
    method: str = "pearson",
) -> dict:
    """Compute rolling correlation matrix for asset returns.

    Args:
        price_df: DataFrame with columns ['trade_date', 'asset_id', 'close'].
        window: Rolling window size in trading days.
        method: Correlation method ('pearson', 'spearman', 'kendall').

    Returns:
        Dict with 'matrix' (asset x asset correlation), 'assets', 'window'.
    """
    # Pivot to wide format: rows=trade_date, cols=asset_id, values=close
    pivot = price_df.pivot_table(
        index="trade_date", columns="asset_id", values="close"
    ).sort_index()

    # Compute returns
    returns = pivot.pct_change().dropna(how="all")

    # Use last `window` days for correlation
    recent = returns.tail(window)
    if len(recent) < 2:
        return {"matrix": {}, "assets": [], "window": window}

    corr = recent.corr(method=method)

    # Convert to serializable format
    assets = corr.columns.tolist()
    matrix = {}
    for asset_a in assets:
        matrix[asset_a] = {}
        for asset_b in assets:
            val = corr.loc[asset_a, asset_b]
            matrix[asset_a][asset_b] = float(val) if not np.isnan(val) else None

    return {"matrix": matrix, "assets": assets, "window": window}


def compute_factor_exposures(
    price_df: pd.DataFrame,
    window: int = 20,
) -> dict:
    """Compute time-series of momentum and volatility factor exposures.

    Args:
        price_df: DataFrame with columns ['trade_date', 'asset_id', 'close'].
        window: Lookback window for factor computation.

    Returns:
        Dict with 'data' (list of {trade_date, momentum_20d, volatility_20d}).
    """
    pivot = price_df.pivot_table(
        index="trade_date", columns="asset_id", values="close"
    ).sort_index()

    returns = pivot.pct_change()

    # Cross-sectional momentum: average return over window
    momentum = returns.rolling(window).mean().mean(axis=1)

    # Cross-sectional volatility: average rolling std
    volatility = returns.rolling(window).std().mean(axis=1)

    # Combine into time series
    result = []
    for date in momentum.index:
        mom_val = momentum.loc[date]
        vol_val = volatility.loc[date]
        if not np.isnan(mom_val) and not np.isnan(vol_val):
            result.append({
                "trade_date": str(date),
                "momentum_20d": float(mom_val),
                "volatility_20d": float(vol_val),
            })

    return {"data": result, "window": window}


def run_stress_test(
    returns: np.ndarray,
    nav_series: np.ndarray | None = None,
) -> dict:
    """Run 6 preset stress scenarios on portfolio returns.

    Args:
        returns: Array of daily portfolio returns.
        nav_series: Optional NAV series for drawdown calculation.

    Returns:
        Dict with 'scenarios' (list of {name, impact, description}).
    """
    if len(returns) == 0:
        return {"scenarios": []}

    mean_ret = float(np.mean(returns))
    std_ret = float(np.std(returns))
    max_dd = 0.0

    if nav_series is not None and len(nav_series) > 0:
        peak = np.maximum.accumulate(nav_series)
        dd = (nav_series - peak) / peak
        max_dd = float(np.min(dd))

    scenarios = [
        {
            "name": "市场崩盘 (-20%)",
            "impact": -0.20,
            "description": "假设市场单日下跌20%，模拟极端行情",
        },
        {
            "name": "波动率飙升 (3x)",
            "impact": -3 * std_ret,
            "description": "波动率扩大至正常水平的3倍",
        },
        {
            "name": "流动性危机",
            "impact": -2 * std_ret - abs(mean_ret),
            "description": "流动性枯竭导致价差扩大和滑点增加",
        },
        {
            "name": "利率冲击 (+200bp)",
            "impact": -0.05,
            "description": "利率突然上升200个基点",
        },
        {
            "name": "汇率贬值 (-10%)",
            "impact": -0.10,
            "description": "本币贬值10%，影响外币资产",
        },
        {
            "name": "历史最大回撤",
            "impact": max_dd,
            "description": f"基于历史数据的最大回撤 ({max_dd*100:.1f}%)",
        },
    ]

    return {"scenarios": scenarios}


def compute_risk_contribution(
    weights: dict[str, float],
    price_df: pd.DataFrame,
    window: int = 60,
) -> dict:
    """Compute marginal risk contribution per asset.

    Args:
        weights: Dict of {asset_id: weight} (should sum to ~1).
        price_df: DataFrame with columns ['trade_date', 'asset_id', 'close'].
        window: Lookback window for covariance estimation.

    Returns:
        Dict with 'contributions' (list of {asset_id, weight, marginal_risk, pct_of_risk}).
    """
    assets = list(weights.keys())
    w = np.array([weights[a] for a in assets])

    # Pivot prices
    pivot = price_df.pivot_table(
        index="trade_date", columns="asset_id", values="close"
    ).sort_index()

    # Filter to available assets
    available = [a for a in assets if a in pivot.columns]
    if not available:
        return {"contributions": []}

    w_filtered = np.array([weights[a] for a in available])
    returns = pivot[available].pct_change().dropna().tail(window)

    if len(returns) < 2:
        return {"contributions": []}

    # Covariance matrix
    cov = returns.cov().values

    # Portfolio volatility
    port_var = w_filtered @ cov @ w_filtered
    port_vol = np.sqrt(port_var) if port_var > 0 else 0.0

    # Marginal contribution to risk
    mcr = cov @ w_filtered / port_vol if port_vol > 0 else np.zeros(len(available))

    # Component risk contribution
    crc = w_filtered * mcr

    # Percentage of total risk
    total_crc = np.sum(crc)
    pct = crc / total_crc if total_crc > 0 else np.zeros(len(available))

    contributions = []
    for i, asset in enumerate(available):
        contributions.append({
            "asset_id": asset,
            "weight": float(w_filtered[i]),
            "marginal_risk": float(mcr[i]),
            "risk_contribution": float(crc[i]),
            "pct_of_risk": float(pct[i]),
        })

    # Sort by pct_of_risk descending
    contributions.sort(key=lambda x: x["pct_of_risk"], reverse=True)

    return {
        "contributions": contributions,
        "portfolio_volatility": float(port_vol),
        "window": window,
    }
