"""cquant.qlib_bridge.evaluator — Qlib 因子评估工具的 cQuant 封装。

接口与 FactorEvaluator 保持一致（均接受 Polars），可互换使用。
使用 qlib_or_fallback 确保 Qlib 不可用时自动降级到 scipy 实现。
"""
from __future__ import annotations

import logging

import polars as pl

from cquant.qlib_bridge._compat import qlib_or_fallback

logger = logging.getLogger(__name__)


class QlibEvaluator:
    """Qlib 因子评估工具的 cQuant 封装。

    接口与 FactorEvaluator 保持一致，可互换使用。
    当 Qlib 可用时委托给 Qlib；否则自动降级到 cQuant 的 scipy 实现。
    """

    def risk_analysis(
        self,
        returns: pl.Series,
        benchmark: pl.Series | None = None,
    ) -> dict:
        """计算年化风险指标。

        Parameters
        ----------
        returns:
            每日收益率 Polars Series。
        benchmark:
            可选基准收益率（保留接口，当前版本不使用）。

        Returns
        -------
        dict，包含：annualized_return, information_ratio, max_drawdown, mean, std。
        returns 为空时返回空字典。
        """
        if returns.is_empty():
            return {}

        def _qlib_impl() -> dict:
            import pandas as pd
            from qlib.contrib.evaluate import risk_analysis

            pd_r = pd.Series(returns.to_numpy(), name="returns")
            result = risk_analysis(pd_r)
            return {
                "mean": float(result.loc["mean", "risk"]),
                "std": float(result.loc["std", "risk"]),
                "annualized_return": float(result.loc["annualized_return", "risk"]),
                "information_ratio": float(result.loc["information_ratio", "risk"]),
                "max_drawdown": float(result.loc["max_drawdown", "risk"]),
            }

        def _native_impl() -> dict:
            import math
            import numpy as np

            r = returns.to_numpy()
            n = len(r)
            total = float((1 + r).prod() - 1)
            years = n / 252
            ann_ret = float((1 + total) ** (1 / years) - 1) if years > 0 else 0.0
            vol = float(r.std(ddof=1)) * math.sqrt(252) if n > 1 else 0.0
            sharpe = ann_ret / vol if vol > 1e-12 else 0.0
            cumulative = (1 + r).cumprod()
            rolling_max = np.maximum.accumulate(cumulative)
            max_dd = float((cumulative / rolling_max - 1).min())
            return {
                "mean": float(r.mean()),
                "std": float(r.std(ddof=1)) if n > 1 else 0.0,
                "annualized_return": ann_ret,
                "information_ratio": sharpe,
                "max_drawdown": max_dd,
            }

        return qlib_or_fallback(_qlib_impl, _native_impl)

    def ic_analysis(
        self,
        factor: pl.Series,
        forward_returns: pl.Series,
        method: str = "rank",
    ) -> dict:
        """计算单截面 IC（Information Coefficient）。

        Parameters
        ----------
        factor:
            因子值 Series。
        forward_returns:
            前瞻收益率 Series（与 factor 等长）。
        method:
            ``"rank"``（Spearman）或 ``"pearson"``。

        Returns
        -------
        dict，包含：ic（相关系数）, p_value（显著性 p 值）。
        """
        if factor.is_empty() or forward_returns.is_empty():
            return {"ic": float("nan"), "p_value": 1.0}

        def _compute() -> dict:
            from scipy.stats import pearsonr, spearmanr

            f = factor.to_numpy()
            r = forward_returns.to_numpy()
            corr_fn = spearmanr if method == "rank" else pearsonr
            ic, p = corr_fn(f, r)
            return {"ic": float(ic), "p_value": float(p)}

        return qlib_or_fallback(_compute, _compute)
