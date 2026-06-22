"""Statistical significance tests for comparing backtest strategies.

Provides three methods:
- PSR difference test (Jobson & Korkie 1981)
- Bootstrap test for Sharpe ratio difference
- Model Confidence Set (MCS) to identify statistically best strategies
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def psr_difference(returns_a: np.ndarray, returns_b: np.ndarray) -> dict:
    """Test if Sharpe ratio difference is significant (Jobson & Korkie 1981).

    Args:
        returns_a: Daily returns for strategy A.
        returns_b: Daily returns for strategy B.

    Returns:
        Dict with sharpe_a, sharpe_b, diff, z_stat, p_value, significant.
    """
    n = len(returns_a)
    if n < 2 or len(returns_b) < 2:
        return {
            "sharpe_a": 0.0,
            "sharpe_b": 0.0,
            "diff": 0.0,
            "z_stat": 0.0,
            "p_value": 1.0,
            "significant": False,
        }

    std_a = np.std(returns_a, ddof=1)
    std_b = np.std(returns_b, ddof=1)
    sr_a = np.mean(returns_a) / std_a * np.sqrt(252) if std_a > 0 else 0.0
    sr_b = np.mean(returns_b) / std_b * np.sqrt(252) if std_b > 0 else 0.0
    diff = sr_a - sr_b

    # Standard error of difference (simplified)
    corr = np.corrcoef(returns_a, returns_b)[0, 1]
    se = np.sqrt((2 - 2 * corr) / n)
    z = diff / se if se > 0 else 0.0
    p_value = float(2 * (1 - stats.norm.cdf(abs(z))))

    return {
        "sharpe_a": float(sr_a),
        "sharpe_b": float(sr_b),
        "diff": float(diff),
        "z_stat": float(z),
        "p_value": p_value,
        "significant": p_value < 0.05,
    }


def bootstrap_test(
    returns_a: np.ndarray,
    returns_b: np.ndarray,
    n_bootstrap: int = 10000,
    seed: int | None = None,
) -> dict:
    """Bootstrap test for Sharpe ratio difference.

    Args:
        returns_a: Daily returns for strategy A.
        returns_b: Daily returns for strategy B.
        n_bootstrap: Number of bootstrap iterations.
        seed: Random seed for reproducibility.

    Returns:
        Dict with diff_mean, ci_lower, ci_upper, p_value, significant.
    """
    rng = np.random.default_rng(seed)

    std_a = np.std(returns_a, ddof=1)
    std_b = np.std(returns_b, ddof=1)
    sr_a = np.mean(returns_a) / std_a * np.sqrt(252) if std_a > 0 else 0.0
    sr_b = np.mean(returns_b) / std_b * np.sqrt(252) if std_b > 0 else 0.0
    observed_diff = sr_a - sr_b

    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx_a = rng.integers(0, len(returns_a), size=len(returns_a))
        idx_b = rng.integers(0, len(returns_b), size=len(returns_b))
        r_a = returns_a[idx_a]
        r_b = returns_b[idx_b]
        s_a = np.mean(r_a) / np.std(r_a) * np.sqrt(252) if np.std(r_a) > 0 else 0.0
        s_b = np.mean(r_b) / np.std(r_b) * np.sqrt(252) if np.std(r_b) > 0 else 0.0
        diffs[i] = s_a - s_b

    ci_lower = float(np.percentile(diffs, 2.5))
    ci_upper = float(np.percentile(diffs, 97.5))
    p_value = float(np.mean(diffs <= 0)) if observed_diff > 0 else float(np.mean(diffs >= 0))

    return {
        "diff_mean": float(np.mean(diffs)),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "p_value": p_value,
        "significant": ci_lower > 0 or ci_upper < 0,
    }


def mcs_test(
    returns_list: list[np.ndarray],
    confidence: float = 0.95,
) -> dict:
    """Model Confidence Set — identify statistically best strategies.

    Simplified MCS: compare all pairs against the best (highest Sharpe)
    and include strategies whose Sharpe is not significantly different.

    Args:
        returns_list: List of daily returns arrays, one per strategy.
        confidence: Confidence level (default 0.95).

    Returns:
        Dict with confidence and results list (per-strategy ranking).
    """
    sharpes = []
    for r in returns_list:
        std = np.std(r, ddof=1)
        sr = np.mean(r) / std * np.sqrt(252) if std > 0 else 0.0
        sharpes.append(float(sr))

    best_idx = int(np.argmax(sharpes))

    results = []
    for i, sr in enumerate(sharpes):
        if i == best_idx:
            results.append({
                "index": i,
                "sharpe": sr,
                "in_confidence_set": True,
                "p_value": 0.0,
            })
        else:
            test = psr_difference(returns_list[best_idx], returns_list[i])
            results.append({
                "index": i,
                "sharpe": sr,
                "in_confidence_set": test["p_value"] > (1 - confidence),
                "p_value": test["p_value"],
            })

    return {"confidence": confidence, "results": results}
