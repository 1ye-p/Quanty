"""cquant.bt_analyzer.multiple_testing — Multiple-testing corrections.

Supported methods:
- Bonferroni: most conservative; corrects each p-value by n_trials
- BHY (Benjamini-Hochberg-Yekutieli): controls FDR under arbitrary dependence
- Bailey-Lopez: finance-specific; uses E[max SR | n_trials] as the effective H0

Reference: Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio".
"""

from __future__ import annotations

import math
from typing import Any

from cquant.bt_analyzer.sharpe import SharpeMetrics


class MultipleTestingCorrector:
    """Apply standard and finance-specific multiple-testing corrections."""

    @classmethod
    def correct(
        cls,
        p_values: list[float],
        alpha: float = 0.05,
        n_trials: int = 1,
    ) -> dict[str, dict[str, Any]]:
        """Return all three corrections for *p_values*.

        Returns a dict with keys 'bonferroni', 'bhy', 'bailey_lopez',
        each containing corrected_pvalues, accepted, any_significant.
        """
        clipped = [min(max(float(p), 0.0), 1.0) for p in p_values]
        m = max(n_trials, len(clipped), 1)
        return {
            "bonferroni": cls._bonferroni(clipped, alpha, m),
            "bhy": cls._bhy(clipped, alpha, m),
            "bailey_lopez": cls._bailey_lopez(clipped, alpha, m),
        }

    @staticmethod
    def _bonferroni(p_values: list[float], alpha: float, n: int) -> dict[str, Any]:
        corrected = [min(p * n, 1.0) for p in p_values]
        accepted = [p <= alpha for p in corrected]
        return {
            "corrected_pvalues": corrected,
            "accepted": accepted,
            "any_significant": any(accepted),
            "adjusted_alpha": alpha / n,
        }

    @staticmethod
    def _bhy(p_values: list[float], alpha: float, n: int) -> dict[str, Any]:
        """Benjamini-Hochberg-Yekutieli FDR control under arbitrary dependence."""
        if not p_values:
            return {"corrected_pvalues": [], "accepted": [], "any_significant": False, "adjusted_alpha": alpha}

        # c(m) = sum(1/i for i in 1..n) — dependency correction factor
        harmonic = sum(1.0 / i for i in range(1, n + 1))

        # Sort ascending, compute adjusted p-values, then restore order
        order = sorted(range(len(p_values)), key=lambda i: p_values[i])
        adjusted: list[float] = [0.0] * len(p_values)
        running_min = 1.0
        for rank in range(len(order), 0, -1):
            orig = order[rank - 1]
            candidate = min(1.0, p_values[orig] * n * harmonic / rank)
            running_min = min(running_min, candidate)
            adjusted[rank - 1] = running_min

        corrected = [0.0] * len(p_values)
        for sorted_i, orig_i in enumerate(order):
            corrected[orig_i] = adjusted[sorted_i]

        accepted = [p <= alpha for p in corrected]
        return {
            "corrected_pvalues": corrected,
            "accepted": accepted,
            "any_significant": any(accepted),
            "adjusted_alpha": alpha / harmonic,
        }

    @staticmethod
    def _bailey_lopez(p_values: list[float], alpha: float, n: int) -> dict[str, Any]:
        """Finance-specific correction using the Bonferroni-Sidak approach."""
        corrected = [1.0 - (1.0 - p) ** n for p in p_values]
        accepted = [p <= alpha for p in corrected]
        return {
            "corrected_pvalues": corrected,
            "accepted": accepted,
            "any_significant": any(accepted),
            "adjusted_alpha": 1.0 - math.pow(1.0 - alpha, 1.0 / max(n, 1)),
            "expected_max_sharpe": SharpeMetrics.expected_max_sharpe(n),
        }
