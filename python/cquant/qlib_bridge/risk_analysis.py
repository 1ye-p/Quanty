"""cquant.qlib_bridge.risk_analysis — Qlib risk analysis bridge wrapper.

Provides ``qlib_risk_analysis()`` as a bridge function so that callers
do not need to import ``qlib.contrib.evaluate`` directly.
"""
from __future__ import annotations

import logging

import numpy as np

from cquant.qlib_bridge._compat import QLIB_AVAILABLE

logger = logging.getLogger(__name__)


def qlib_risk_analysis(returns_array: np.ndarray) -> dict | None:
    """Compute annualized risk metrics using Qlib's ``risk_analysis``.

    This is a bridge wrapper around ``qlib.contrib.evaluate.risk_analysis``
    so that callers can route through the bridge instead of importing
    Qlib directly.

    Parameters
    ----------
    returns_array:
        Daily return values as a numpy array.

    Returns
    -------
    dict or None
        Dictionary with keys ``mean``, ``std``, ``annualized_return``,
        ``information_ratio``, ``max_drawdown``, or ``None`` if Qlib
        is not available or *returns_array* is empty.
    """
    if len(returns_array) == 0:
        return None

    if not QLIB_AVAILABLE:
        logger.warning("qlib_risk_analysis: qlib not available, returning None")
        return None

    try:
        import pandas as pd
        from qlib.contrib.evaluate import risk_analysis

        pd_returns = pd.Series(returns_array, name="returns")
        result_df = risk_analysis(pd_returns)

        return {
            "mean": float(result_df.loc["mean", "risk"]),
            "std": float(result_df.loc["std", "risk"]),
            "annualized_return": float(result_df.loc["annualized_return", "risk"]),
            "information_ratio": float(result_df.loc["information_ratio", "risk"]),
            "max_drawdown": float(result_df.loc["max_drawdown", "risk"]),
        }
    except ImportError:
        logger.warning("qlib_risk_analysis: qlib not importable, returning None")
        return None
