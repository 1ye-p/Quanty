"""Black-Litterman position sizer."""
from __future__ import annotations

import logging

import numpy as np
import polars as pl
from scipy.optimize import minimize

from cquant.core.types import SignalFrame, TargetWeights
from cquant.riskguard.models import SizingContext
from cquant.riskguard.sizers.base import PositionSizer

logger = logging.getLogger(__name__)


class BlackLittermanSizer(PositionSizer):
    """Black-Litterman model for combining market equilibrium with investor views.

    Parameters:
        tau: Scaling factor for prior uncertainty (default 0.05).
        views: List of view dicts, each with:
            - "asset": asset_id
            - "relative_to": asset_id (relative view) or None (absolute)
            - "expected_excess": expected excess return of the view
        risk_aversion: Market risk aversion parameter (default 2.5).
    """

    def __init__(
        self,
        tau: float = 0.05,
        views: list[dict] | None = None,
        risk_aversion: float = 2.5,
    ) -> None:
        self._tau = tau
        self._views = views or []
        self._risk_aversion = risk_aversion

    @property
    def name(self) -> str:
        return "black_litterman"

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

        # Get market-cap weights (equilibrium prior)
        cap_weights = ctx.constraints.get("market_cap_weights", {})
        if not cap_weights:
            logger.warning("BlackLittermanSizer: no market_cap_weights; falling back to equal weight.")
            return _bl_equal_weight(assets, ctx.as_of_date, self.name)

        w_mkt = np.array([cap_weights.get(a, 1.0 / n) for a in assets])
        w_mkt = w_mkt / w_mkt.sum()  # normalize

        # Get covariance matrix
        if ctx.return_covariance is None:
            logger.warning("BlackLittermanSizer: no covariance; falling back to equal weight.")
            return _bl_equal_weight(assets, ctx.as_of_date, self.name)

        try:
            cov_df = ctx.return_covariance.filter(pl.col("asset_id").is_in(assets))
            cov_cols = [a for a in assets if a in cov_df.columns]
            cov_df = cov_df.sort("asset_id")
            sigma = cov_df.select(cov_cols).to_numpy()

            # Equilibrium returns: pi = delta * Sigma * w_mkt
            pi = self._risk_aversion * sigma @ w_mkt

            if not self._views:
                # No views -> return market weights
                weights = {assets[i]: float(w_mkt[i]) for i in range(n)}
                return TargetWeights(
                    strategy_id="",
                    rebalance_date=ctx.as_of_date,
                    weights=weights,
                    sizer_name=self.name,
                )

            # Build P (pick matrix) and Q (view returns) from views
            k = len(self._views)
            P = np.zeros((k, n))
            Q = np.zeros(k)
            asset_idx = {a: i for i, a in enumerate(assets)}

            for v_idx, view in enumerate(self._views):
                asset = view["asset"]
                if asset not in asset_idx:
                    continue
                ai = asset_idx[asset]
                Q[v_idx] = view["expected_excess"]
                P[v_idx, ai] = 1.0
                rel = view.get("relative_to")
                if rel and rel in asset_idx:
                    P[v_idx, asset_idx[rel]] = -1.0

            # Omega = diagonal uncertainty (proportional to prior variance)
            omega = np.diag(np.diag(P @ (self._tau * sigma) @ P.T))

            # Posterior: mu_BL = [(tau*Sigma)^-1 + P'Omega^-1 P]^-1 [(tau*Sigma)^-1 pi + P'Omega^-1 Q]
            tau_sigma_inv = np.linalg.inv(self._tau * sigma)
            omega_inv = np.linalg.inv(omega)
            M = tau_sigma_inv + P.T @ omega_inv @ P
            M_inv = np.linalg.inv(M)
            mu_bl = M_inv @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)

            # Optimize with posterior returns
            def neg_obj(w):
                return -(mu_bl @ w - self._risk_aversion / 2 * w @ sigma @ w)

            constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
            bounds = [(0.0, 1.0)] * n
            res = minimize(neg_obj, w_mkt, method="SLSQP", bounds=bounds, constraints=constraints)

            w_opt = res.x
            weights = {assets[i]: float(w_opt[i]) for i in range(n) if abs(w_opt[i]) > 1e-6}

        except Exception as exc:
            logger.warning("BlackLittermanSizer: computation failed (%s); falling back to equal weight.", exc)
            return _bl_equal_weight(assets, ctx.as_of_date, self.name)

        return TargetWeights(
            strategy_id="",
            rebalance_date=ctx.as_of_date,
            weights=weights,
            sizer_name=self.name,
        )


def _bl_equal_weight(assets: list[str], as_of_date, sizer_name: str) -> TargetWeights:
    n = len(assets)
    return TargetWeights(
        strategy_id="",
        rebalance_date=as_of_date,
        weights={a: 1.0 / n for a in assets} if n else {},
        sizer_name=sizer_name,
    )
