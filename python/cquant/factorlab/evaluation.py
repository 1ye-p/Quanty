"""Factor evaluation framework — IC, IC IR, and summary metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl
from scipy.stats import pearsonr, spearmanr


@dataclass
class FactorEvaluator:
    """Compute Information Coefficient (IC) and derived metrics for a factor.

    Parameters
    ----------
    factor_col:
        Column name holding factor values in the *factors* DataFrame.
    return_col:
        Column name holding forward returns in the *returns* DataFrame.
    method:
        ``"rank"`` (default) uses Spearman rank correlation;
        ``"pearson"`` uses Pearson correlation.
    """

    factor_col: str
    return_col: str
    method: str = "rank"
    factor_name: str = field(default="")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _corr_fn(self):
        if self.method == "rank":
            return spearmanr
        elif self.method == "pearson":
            return pearsonr
        else:
            raise ValueError(f"Unknown method '{self.method}'; use 'rank' or 'pearson'")

    def _join(
        self, factors: pl.DataFrame, returns: pl.DataFrame
    ) -> pl.DataFrame:
        return factors.join(
            returns, on=["asset_id", "trade_date"], how="inner"
        )

    def _ic_per_date(self, joined: pl.DataFrame) -> list[dict]:
        corr = self._corr_fn()
        results: list[dict] = []
        for dt, group in joined.group_by("trade_date", maintain_order=True):
            fv = group[self.factor_col].to_numpy()
            ret = group[self.return_col].to_numpy()
            if len(fv) < 3:
                continue
            r, _ = corr(fv, ret)
            if np.isnan(r):
                continue
            results.append({"trade_date": dt, "ic": float(r)})
        return results

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def ic_series(self, factors: pl.DataFrame, returns: pl.DataFrame) -> pl.DataFrame:
        """Compute per-date IC.

        Returns a DataFrame with columns ``[trade_date, ic]``.
        Dates with fewer than 3 observations are skipped.
        """
        joined = self._join(factors, returns)
        rows = self._ic_per_date(joined)
        return pl.DataFrame(rows).sort("trade_date")

    def mean_ic(self, factors: pl.DataFrame, returns: pl.DataFrame) -> float:
        """Mean IC across all evaluated dates."""
        return float(self.ic_series(factors, returns)["ic"].mean())

    def ic_ir(self, factors: pl.DataFrame, returns: pl.DataFrame) -> float:
        """IC Information Ratio: mean(IC) / std(IC)."""
        ic = self.ic_series(factors, returns)["ic"].to_numpy()
        if len(ic) < 2 or np.std(ic) == 0:
            return float("nan")
        return float(np.mean(ic) / np.std(ic))

    def ic_positive_pct(
        self, factors: pl.DataFrame, returns: pl.DataFrame
    ) -> float:
        """Percentage of dates where IC > 0."""
        ic = self.ic_series(factors, returns)["ic"].to_numpy()
        if len(ic) == 0:
            return 0.0
        return float(np.mean(ic > 0) * 100)

    def summary(self, factors: pl.DataFrame, returns: pl.DataFrame) -> dict:
        """Return a summary dict with all evaluation metrics."""
        ic = self.ic_series(factors, returns)["ic"].to_numpy()
        dates_evaluated = len(ic)
        mean = float(np.mean(ic)) if dates_evaluated else 0.0
        std = float(np.std(ic)) if dates_evaluated >= 2 else 0.0
        ic_ir = mean / std if std != 0 else float("nan")
        ic_pos = (
            float(np.mean(ic > 0) * 100)
            if dates_evaluated
            else 0.0
        )
        return {
            "factor_name": self.factor_name or self.factor_col,
            "method": self.method,
            "mean_ic": mean,
            "ic_ir": ic_ir,
            "ic_positive_pct": ic_pos,
            "dates_evaluated": dates_evaluated,
        }
