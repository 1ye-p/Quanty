"""cquant.bt_analyzer.sharpe — Probabilistic and Deflated Sharpe Ratio metrics.

Reference: Bailey & Lopez de Prado (2012), "The Sharpe Ratio Efficient Frontier".

PSR(SR*) = Φ( √(T-1) · (SR - SR*) / √(1 - γ₃·SR + (γ₄-1)/4 · SR²) )

where:
  - SR  = observed annualized Sharpe ratio
  - SR* = benchmark Sharpe ratio
  - T   = effective number of independent observations (autocorrelation-adjusted)
  - γ₃  = skewness of returns
  - γ₄  = excess kurtosis of returns

DSR deflates SR* upward by E[max SR | n_trials] to account for selection bias.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import polars as pl

from cquant.backtest_vector.metrics import compute_metrics

_EPS = 1e-12
_NORMAL = NormalDist()
_EULER_GAMMA = 0.5772156649015329


class SharpeMetrics:
    """Compute PSR and DSR from a portfolio returns series."""

    @classmethod
    def probabilistic_sharpe_ratio(
        cls,
        returns: pl.Series,
        benchmark_sharpe: float = 0.0,
        trading_days_per_year: int = 252,
    ) -> float:
        """Return P(true SR > benchmark_sharpe) adjusted for higher moments."""
        values = cls._clean(returns)
        if len(values) < 2:
            return 0.0

        observed_sr = compute_metrics(
            pl.Series("portfolio_return", values),
            trading_days_per_year=trading_days_per_year,
        ).sharpe_ratio
        skew = cls._skewness(values)
        kurt = cls._kurtosis(values)
        t_eff = cls._effective_t(values)

        denom = 1.0 - skew * observed_sr + ((kurt - 1.0) / 4.0) * (observed_sr ** 2)
        denom = max(denom, _EPS)
        z = math.sqrt(max(t_eff - 1.0, 1.0)) * (observed_sr - benchmark_sharpe) / math.sqrt(denom)
        return float(_NORMAL.cdf(z))

    @classmethod
    def deflated_sharpe_ratio(
        cls,
        returns: pl.Series,
        benchmark_sharpe: float = 0.0,
        n_trials: int = 1,
        trading_days_per_year: int = 252,
    ) -> float:
        """PSR with benchmark inflated by E[max SR | n_trials] to penalize overfitting."""
        adjusted_benchmark = max(benchmark_sharpe, cls.expected_max_sharpe(n_trials))
        return cls.probabilistic_sharpe_ratio(
            returns,
            benchmark_sharpe=adjusted_benchmark,
            trading_days_per_year=trading_days_per_year,
        )

    @staticmethod
    def expected_max_sharpe(n_trials: int) -> float:
        """E[max SR] across n_trials independent strategies (Bailey-Lopez formula)."""
        if n_trials <= 1:
            return 0.0
        n = float(max(n_trials, 2))
        t1 = _NORMAL.inv_cdf(1.0 - 1.0 / n)
        t2 = _NORMAL.inv_cdf(1.0 - 1.0 / (n * math.e))
        return float((1.0 - _EULER_GAMMA) * t1 + _EULER_GAMMA * t2)

    @staticmethod
    def _clean(returns: pl.Series) -> list[float]:
        return [float(v) for v in returns.fill_null(0.0).to_list() if math.isfinite(float(v))]

    @staticmethod
    def _effective_t(values: list[float]) -> float:
        """Autocorrelation-adjusted effective sample size."""
        if len(values) < 3:
            return float(len(values))
        x, y = values[:-1], values[1:]
        mx, my = sum(x) / len(x), sum(y) / len(y)
        cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
        vx = sum((a - mx) ** 2 for a in x)
        vy = sum((b - my) ** 2 for b in y)
        rho = max(min(cov / math.sqrt(max(vx * vy, _EPS)), 0.99), -0.99)
        eff = len(values) * (1.0 - rho) / (1.0 + rho)
        return float(max(2.0, min(eff, float(len(values)))))

    @staticmethod
    def _skewness(values: list[float]) -> float:
        n = len(values)
        if n < 3:
            return 0.0
        m = sum(values) / n
        c = [v - m for v in values]
        m2 = sum(v ** 2 for v in c) / n
        if m2 <= _EPS:
            return 0.0
        m3 = sum(v ** 3 for v in c) / n
        return float(m3 / (m2 ** 1.5))

    @staticmethod
    def _kurtosis(values: list[float]) -> float:
        n = len(values)
        if n < 4:
            return 3.0
        m = sum(values) / n
        c = [v - m for v in values]
        m2 = sum(v ** 2 for v in c) / n
        if m2 <= _EPS:
            return 3.0
        m4 = sum(v ** 4 for v in c) / n
        return float(m4 / (m2 ** 2))
