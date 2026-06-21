"""Advanced risk analysis functions for backtest results.

Provides correlation analysis, factor exposure tracking, stress testing,
and risk contribution decomposition.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

HISTORICAL_SCENARIOS: list[dict] = [
    {
        "name": "2015 A股股灾",
        "start_date": "2015-06-12",
        "end_date": "2015-07-08",
        "benchmark_impact": -0.43,
        "description": "杠杆牛市崩盘，沪指从5178跌至3507",
    },
    {
        "name": "2016 熔断危机",
        "start_date": "2016-01-04",
        "end_date": "2016-01-07",
        "benchmark_impact": -0.12,
        "description": "熔断机制实施后连续跌停",
    },
    {
        "name": "2018 贸易战",
        "start_date": "2018-01-29",
        "end_date": "2018-10-19",
        "benchmark_impact": -0.30,
        "description": "中美贸易摩擦，沪指持续下跌",
    },
    {
        "name": "2020 COVID",
        "start_date": "2020-01-20",
        "end_date": "2020-03-23",
        "benchmark_impact": -0.16,
        "description": "新冠疫情全球爆发",
    },
    {
        "name": "2022 俄乌冲突",
        "start_date": "2022-02-24",
        "end_date": "2022-04-27",
        "benchmark_impact": -0.20,
        "description": "俄乌战争引发全球避险",
    },
]


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
    mom_key = f"momentum_{window}d"
    vol_key = f"volatility_{window}d"
    result = []
    for date in momentum.index:
        mom_val = momentum.loc[date]
        vol_val = volatility.loc[date]
        if not np.isnan(mom_val) and not np.isnan(vol_val):
            result.append({
                "trade_date": str(date),
                mom_key: float(mom_val),
                vol_key: float(vol_val),
            })

    return {"data": result, "window": window, "keys": [mom_key, vol_key]}


def _compute_period_stats(
    returns: np.ndarray,
    nav_series: np.ndarray | None,
    mask: np.ndarray,
) -> dict:
    """Compute strategy return, max drawdown, and vol for a subset of returns.

    Args:
        returns: Full array of daily returns.
        nav_series: Full NAV series (same length as returns) or None.
        mask: Boolean array selecting the sub-period.

    Returns:
        Dict with 'strategy_return', 'max_drawdown', 'volatility'.
    """
    period_returns = returns[mask]
    if len(period_returns) == 0:
        return {"strategy_return": None, "max_drawdown": None, "volatility": None}

    cum = float(np.prod(1 + period_returns) - 1)
    vol = float(np.std(period_returns)) if len(period_returns) > 1 else 0.0

    # Max drawdown from NAV if available, otherwise from cumulative returns
    max_dd = 0.0
    if nav_series is not None and len(nav_series) > 0:
        period_nav = nav_series[mask]
        if len(period_nav) > 0:
            peak = np.maximum.accumulate(period_nav)
            dd = (period_nav - peak) / peak
            max_dd = float(np.min(dd))
    else:
        period_nav = np.cumprod(1 + period_returns)
        peak = np.maximum.accumulate(period_nav)
        dd = (period_nav - peak) / peak
        max_dd = float(np.min(dd))

    return {"strategy_return": cum, "max_drawdown": max_dd, "volatility": vol}


def run_stress_test(
    returns: np.ndarray,
    nav_series: np.ndarray | None = None,
    trade_dates: np.ndarray | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> dict:
    """Run stress scenarios on portfolio returns.

    Includes 6 synthetic scenarios plus A-share historical crisis periods.
    When trade_dates is provided, historical scenarios compute actual strategy
    performance during each crisis window and compare with the benchmark.

    Args:
        returns: Array of daily portfolio returns.
        nav_series: Optional NAV series for drawdown calculation.
        trade_dates: Optional array of date strings (YYYY-MM-DD) aligned with returns.
        custom_start: Optional start date (YYYY-MM-DD) for a custom stress window.
        custom_end: Optional end date (YYYY-MM-DD) for a custom stress window.

    Returns:
        Dict with 'scenarios' (list of synthetic scenarios) and
        'historical' (list of historical scenario results with strategy vs benchmark).
    """
    if len(returns) == 0:
        return {"scenarios": [], "historical": []}

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

    # Historical scenarios require date-indexed returns
    historical: list[dict] = []
    if trade_dates is not None and len(trade_dates) == len(returns):
        parsed_dates = np.array(
            [datetime.strptime(str(d)[:10], "%Y-%m-%d") for d in trade_dates]
        )

        for scenario in HISTORICAL_SCENARIOS:
            start = datetime.strptime(scenario["start_date"], "%Y-%m-%d")
            end = datetime.strptime(scenario["end_date"], "%Y-%m-%d")
            mask = (parsed_dates >= start) & (parsed_dates <= end)

            stats = _compute_period_stats(returns, nav_series, mask)
            strategy_ret = stats["strategy_return"]
            benchmark_ret = scenario["benchmark_impact"]

            historical.append({
                "name": scenario["name"],
                "start_date": scenario["start_date"],
                "end_date": scenario["end_date"],
                "description": scenario["description"],
                "strategy_return": strategy_ret,
                "benchmark_return": benchmark_ret,
                "excess_return": (
                    round(strategy_ret - benchmark_ret, 6)
                    if strategy_ret is not None
                    else None
                ),
                "max_drawdown": stats["max_drawdown"],
                "volatility": stats["volatility"],
                "trading_days": int(mask.sum()),
            })

    # Custom date range scenario
    if custom_start and custom_end and trade_dates is not None and len(trade_dates) == len(returns):
        parsed_dates = np.array(
            [datetime.strptime(str(d)[:10], "%Y-%m-%d") for d in trade_dates]
        )
        start = datetime.strptime(custom_start, "%Y-%m-%d")
        end = datetime.strptime(custom_end, "%Y-%m-%d")
        mask = (parsed_dates >= start) & (parsed_dates <= end)

        stats = _compute_period_stats(returns, nav_series, mask)
        historical.append({
            "name": f"自定义区间 {custom_start} ~ {custom_end}",
            "start_date": custom_start,
            "end_date": custom_end,
            "description": "用户自定义压力测试区间",
            "strategy_return": stats["strategy_return"],
            "benchmark_return": None,
            "excess_return": None,
            "max_drawdown": stats["max_drawdown"],
            "volatility": stats["volatility"],
            "trading_days": int(mask.sum()),
        })

    return {"scenarios": scenarios, "historical": historical}


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
