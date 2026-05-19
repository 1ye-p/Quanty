"""Mean-Variance Optimization (MVO) position sizer."""
from __future__ import annotations

import logging

import numpy as np
import polars as pl
from scipy.optimize import minimize

from cquant.core.types import SignalFrame, TargetWeights
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.base import PositionSizer

logger = logging.getLogger(__name__)


class MVOSizer(PositionSizer):
    """Classic Markowitz mean-variance optimization.

    Maximizes Sharpe ratio (return / risk) subject to long-only constraint
    and full investment (weights sum to 1).

    Falls back to equal weight if expected_returns or return_covariance
    is not available in SizingContext.
    """

    def __init__(self, risk_aversion: float = 1.0, max_weight: float = 1.0) -> None:
        self._risk_aversion = risk_aversion
        self._max_weight = max_weight

    @property
    def name(self) -> str:
        return "mvo"

    def target_weights(self, signals: SignalFrame, ctx: SizingContext) -> TargetWeights:
        if signals.is_empty():
            return TargetWeights(
                strategy_id="",
                rebalance_date=ctx.as_of_date,
                weights={},
                sizer_name=self.name,
            )

        active = signals.filter(pl.col("strength").abs() > 1e-9)
        if active.is_empty():
            return TargetWeights(
                strategy_id="",
                rebalance_date=ctx.as_of_date,
                weights={},
                sizer_name=self.name,
            )

        assets = active["asset_id"].to_list()
        n = len(assets)

        # Check if we have the required data
        if ctx.expected_returns is None or ctx.return_covariance is None:
            logger.warning(
                "MVOSizer: missing expected_returns or covariance; falling back to equal weight."
            )
            return _equal_weight_fallback(assets, ctx.as_of_date, self.name)

        try:
            er_df = ctx.expected_returns.filter(pl.col("asset_id").is_in(assets))
            mu = er_df.sort("asset_id")["expected_return"].to_numpy()

            # Build covariance matrix from DataFrame
            cov_df = ctx.return_covariance.filter(pl.col("asset_id").is_in(assets))
            cov_cols = [a for a in assets if a in cov_df.columns]
            if len(cov_cols) < n:
                logger.warning(
                    "MVOSizer: incomplete covariance matrix; falling back to equal weight."
                )
                return _equal_weight_fallback(assets, ctx.as_of_date, self.name)

            cov_df = cov_df.sort("asset_id")
            cov_matrix = cov_df.select(cov_cols).to_numpy()

            # Ensure positive semi-definite
            eigvals = np.linalg.eigvalsh(cov_matrix)
            if np.any(eigvals < -1e-10):
                cov_matrix = cov_matrix + np.eye(n) * (abs(min(eigvals)) + 1e-6)

            # Optimize: maximize mu'w - (risk_aversion/2) * w'Sigma w
            # subject to: sum(w) = 1, 0 <= w_i <= max_weight
            def neg_objective(w):
                ret = mu @ w
                risk = w @ cov_matrix @ w
                return -(ret - self._risk_aversion / 2 * risk)

            constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
            bounds = [(0.0, self._max_weight)] * n
            w0 = np.ones(n) / n

            result = minimize(
                neg_objective, w0, method="SLSQP", bounds=bounds, constraints=constraints
            )
            if not result.success:
                logger.warning(
                    "MVOSizer: optimization did not converge (%s); using result anyway.",
                    result.message,
                )

            weights_arr = result.x
            weights = {
                assets[i]: float(weights_arr[i]) for i in range(n) if abs(weights_arr[i]) > 1e-6
            }

        except Exception as exc:
            logger.warning(
                "MVOSizer: optimization failed (%s); falling back to equal weight.", exc
            )
            return _equal_weight_fallback(assets, ctx.as_of_date, self.name)

        return TargetWeights(
            strategy_id="",
            rebalance_date=ctx.as_of_date,
            weights=weights,
            sizer_name=self.name,
        )


def _equal_weight_fallback(assets: list[str], as_of_date, sizer_name: str) -> TargetWeights:
    n = len(assets)
    return TargetWeights(
        strategy_id="",
        rebalance_date=as_of_date,
        weights={a: 1.0 / n for a in assets} if n else {},
        sizer_name=sizer_name,
    )
