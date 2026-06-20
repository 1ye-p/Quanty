"""cquant.portfolio_opt — Portfolio optimization.

Provides:
- MeanVarianceOptimizer: classic Markowitz optimization
- RiskParityOptimizer: equal risk contribution
- BlackLittermanOptimizer: equilibrium + views optimization
- PortfolioOptimizer ABC: base interface
- ConstraintConfig: structured constraint configuration
"""

from cquant.portfolio_opt.black_litterman import BlackLittermanOptimizer
from cquant.portfolio_opt.constraints import (
    ConstraintConfig,
    FactorExposureLimit,
    SectorLimit,
)
from cquant.portfolio_opt.covariance import CovarianceEstimator
from cquant.portfolio_opt.mean_variance import MeanVarianceOptimizer
from cquant.portfolio_opt.risk_parity import RiskParityOptimizer

__all__ = [
    "BlackLittermanOptimizer",
    "ConstraintConfig",
    "CovarianceEstimator",
    "FactorExposureLimit",
    "MeanVarianceOptimizer",
    "RiskParityOptimizer",
    "SectorLimit",
]
