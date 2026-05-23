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

    def rank_ic_decay(
        self,
        factors: pl.DataFrame,
        returns: pl.DataFrame,
        max_lag: int = 5,
    ) -> pl.DataFrame:
        """Compute IC at different forward lags to measure factor persistence.

        For each lag k from 1 to max_lag, computes the IC between factor
        values at date t and returns at the date k periods later.

        Returns a DataFrame with columns [lag, ic].
        """
        unique_dates = sorted(factors["trade_date"].unique().to_list())
        n_dates = len(unique_dates)
        date_to_idx = {d: i for i, d in enumerate(unique_dates)}
        corr = self._corr_fn()

        results: list[dict] = []
        for lag in range(1, max_lag + 1):
            if lag >= n_dates:
                break
            # Build date shift map: date_t -> date_{t+lag}
            date_shift = {
                d: unique_dates[date_to_idx[d] + lag]
                for d in unique_dates
                if date_to_idx[d] + lag < n_dates
            }
            if not date_shift:
                break

            # Shift factor dates forward by lag
            shifted = factors.with_columns(
                pl.col("trade_date")
                .map_elements(lambda d: date_shift.get(d), return_dtype=pl.Date)
                .alias("shifted_date")
            ).drop_nulls("shifted_date")

            # Join factors[trade_date] with returns[trade_date == shifted_date]
            joined = shifted.join(
                returns.rename({"trade_date": "shifted_date"}),
                on=["asset_id", "shifted_date"],
                how="inner",
            )
            if joined.is_empty() or len(joined) < 3:
                continue

            fv = joined[self.factor_col].to_numpy()
            ret = joined[self.return_col].to_numpy()
            r, _ = corr(fv, ret)
            if not np.isnan(r):
                results.append({"lag": lag, "ic": float(r)})

        if not results:
            return pl.DataFrame({"lag": pl.Series([], dtype=pl.Int32),
                                  "ic": pl.Series([], dtype=pl.Float64)})
        return pl.DataFrame(results).sort("lag")

    def factor_turnover(self, factors: pl.DataFrame, top_n: int = 100) -> float:
        """Average fraction of top-N assets that change between consecutive periods.

        0.0 = perfectly stable rankings. 1.0 = complete turnover each period.
        """
        sorted_dates = sorted(factors["trade_date"].unique().to_list())
        if len(sorted_dates) < 2:
            return 0.0

        prev_top: set[str] | None = None
        turnovers: list[float] = []

        for d in sorted_dates:
            today = (
                factors.filter(pl.col("trade_date") == d)
                .drop_nulls([self.factor_col])
                .sort(self.factor_col, descending=True)
                .head(top_n)
            )
            top_assets = set(today["asset_id"].to_list())

            if prev_top is not None and len(top_assets) > 0:
                overlap = len(top_assets & prev_top)
                turnover = 1.0 - overlap / len(top_assets)
                turnovers.append(turnover)

            prev_top = top_assets

        return float(np.mean(turnovers)) if turnovers else 0.0

    def quantile_returns(
        self,
        factors: pl.DataFrame,
        returns: pl.DataFrame,
        n_quantiles: int = 5,
    ) -> pl.DataFrame:
        """Compute mean return by factor quantile.

        Assets are sorted by factor value and divided into n_quantiles groups
        (1=lowest, n=highest). Returns mean return per quantile aggregated
        across all dates.

        Returns a DataFrame with columns [quantile, mean_return].
        """
        joined = self._join(factors, returns)

        rows: list[dict] = []
        for dt, group in joined.group_by("trade_date", maintain_order=True):
            n = len(group)
            if n < n_quantiles:
                continue
            sorted_group = group.sort(self.factor_col)
            q_size = n // n_quantiles
            for q in range(n_quantiles):
                start = q * q_size
                end = (q + 1) * q_size if q < n_quantiles - 1 else n
                slice_df = sorted_group.slice(start, end - start)
                mean_ret = slice_df[self.return_col].mean()
                if mean_ret is not None:
                    rows.append({"quantile": q + 1, "mean_return": float(mean_ret)})

        if not rows:
            return pl.DataFrame({
                "quantile": pl.Series([], dtype=pl.Int32),
                "mean_return": pl.Series([], dtype=pl.Float64),
            })

        df = pl.DataFrame(rows)
        return (
            df.group_by("quantile")
            .agg(pl.col("mean_return").mean())
            .sort("quantile")
        )

    def qlib_risk_analysis(self, returns: pl.Series) -> dict | None:
        """使用 Qlib 计算年化风险指标。

        调用 ``qlib.contrib.evaluate.risk_analysis()`` 计算年化收益、
        信息比率（夏普）和最大回撤，无需 ``qlib.init()``。

        Parameters
        ----------
        returns:
            每日收益率 Polars Series。

        Returns
        -------
        包含以下键的字典，或在 returns 为空时返回 ``None``：

        - ``annualized_return``: 年化收益率
        - ``information_ratio``: 信息比率（夏普，无风险=0）
        - ``max_drawdown``: 最大回撤（负值）
        - ``mean``: 日均收益
        - ``std``: 日收益标准差
        """
        if returns.is_empty():
            return None

        try:
            import pandas as pd
            from qlib.contrib.evaluate import risk_analysis

            pd_returns = pd.Series(returns.to_numpy(), name="returns")
            result_df = risk_analysis(pd_returns)

            return {
                "mean": float(result_df.loc["mean", "risk"]),
                "std": float(result_df.loc["std", "risk"]),
                "annualized_return": float(result_df.loc["annualized_return", "risk"]),
                "information_ratio": float(result_df.loc["information_ratio", "risk"]),
                "max_drawdown": float(result_df.loc["max_drawdown", "risk"]),
            }
        except ImportError:
            import logging
            logging.getLogger(__name__).warning("qlib 未安装，跳过 qlib_risk_analysis()")
            return None
