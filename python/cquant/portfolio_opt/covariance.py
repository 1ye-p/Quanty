"""cquant.portfolio_opt.covariance — Asset return covariance estimators."""
from __future__ import annotations

import logging
from datetime import date
from typing import Literal

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

CovMatrix = dict[str, dict[str, float]]


class CovarianceEstimator:
    """Estimate annualized asset return covariance matrix from daily price data.

    Parameters
    ----------
    method:
        ``"historical"`` — sample covariance over a rolling window.
        ``"ewma"`` — exponentially weighted moving average covariance.
        ``"ledoit_wolf"`` — Ledoit-Wolf shrinkage estimator (scikit-learn).
    window:
        Maximum number of trading days of history to use.
    halflife:
        EWMA halflife in trading days (only used when method="ewma").
    min_periods:
        Minimum data points required. Falls back to diagonal matrix if fewer.
    trading_days_per_year:
        Annualization factor (default 252).
    """

    def __init__(
        self,
        method: Literal["historical", "ewma", "ledoit_wolf"] = "historical",
        window: int = 252,
        halflife: int = 63,
        min_periods: int = 20,
        trading_days_per_year: int = 252,
    ) -> None:
        if method not in ("historical", "ewma", "ledoit_wolf"):
            raise ValueError(f"Unknown method '{method}'. Use 'historical', 'ewma', or 'ledoit_wolf'.")
        self.method = method
        self.window = window
        self.halflife = halflife
        self.min_periods = min_periods
        self.trading_days_per_year = trading_days_per_year

    def estimate(
        self,
        prices: pl.DataFrame,
        as_of_date: date | None = None,
    ) -> CovMatrix:
        """Compute annualized covariance matrix from OHLCV price data.

        Parameters
        ----------
        prices:
            DataFrame with columns ``[asset_id, trade_date, close]``.
        as_of_date:
            If set, only data up to (and including) this date is used.

        Returns
        -------
        Nested dict ``{asset_id: {asset_id: cov_value}}`` — annualized daily return covariance.
        """
        df = prices.select(["asset_id", "trade_date", "close"])
        if as_of_date is not None:
            df = df.filter(pl.col("trade_date") <= as_of_date)

        # Limit to rolling window
        unique_dates = sorted(df["trade_date"].unique().to_list())
        if len(unique_dates) > self.window:
            cutoff = unique_dates[-self.window]
            df = df.filter(pl.col("trade_date") >= cutoff)

        # Compute log returns per asset
        df = (
            df.sort(["asset_id", "trade_date"])
            .with_columns(
                pl.col("close").log().diff().over("asset_id").alias("log_ret")
            )
            .drop_nulls("log_ret")
        )

        if df.is_empty():
            return {}

        # Pivot to wide format: rows = dates, cols = assets
        wide = df.pivot(
            index="trade_date", on="asset_id", values="log_ret"
        ).sort("trade_date")

        assets = [c for c in wide.columns if c != "trade_date"]
        if not assets:
            return {}

        ret_matrix = wide.select(assets).to_numpy()
        n_obs, n_assets = ret_matrix.shape

        if n_obs < self.min_periods:
            logger.warning(
                "Only %d observations (min_periods=%d); returning diagonal covariance",
                n_obs, self.min_periods,
            )
            avg_var = float(np.nanvar(ret_matrix, axis=0).mean()) if n_obs > 1 else 0.04 / 252
            cov_matrix = np.diag(np.full(n_assets, avg_var))
        elif self.method == "historical":
            cov_matrix = np.cov(ret_matrix, rowvar=False, ddof=1)
        elif self.method == "ewma":
            import pandas as pd
            df_pd = pd.DataFrame(ret_matrix, columns=assets)
            ewm_cov = df_pd.ewm(halflife=self.halflife, min_periods=max(1, self.min_periods)).cov()
            last_idx = ewm_cov.index.get_level_values(0).max()
            cov_matrix = ewm_cov.loc[last_idx].values
        else:  # ledoit_wolf
            from sklearn.covariance import LedoitWolf
            lw = LedoitWolf()
            lw.fit(ret_matrix)
            cov_matrix = lw.covariance_

        if np.ndim(cov_matrix) == 0:
            cov_matrix = np.array([[float(cov_matrix)]])

        # Annualize
        cov_matrix = cov_matrix * self.trading_days_per_year

        return {
            a: {b: float(cov_matrix[i, j]) for j, b in enumerate(assets)}
            for i, a in enumerate(assets)
        }
