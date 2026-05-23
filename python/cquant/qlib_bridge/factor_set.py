"""cquant.qlib_bridge.factor_set — Qlib Alpha158/360 因子集桥接。

读取 Qlib 的因子表达式定义供参考。
cQuant 的 Polars 实现在 factorlab/factors/alpha158.py 中，
不直接调用 Qlib 表达式引擎。
"""
from __future__ import annotations

import logging

from cquant.qlib_bridge._compat import QLIB_AVAILABLE

logger = logging.getLogger(__name__)


class QlibFactorSet:
    """从 Qlib Alpha158 定义中提取因子信息。"""

    @staticmethod
    def alpha158_definitions() -> list[dict]:
        """读取 Alpha158 因子表达式定义列表。

        Returns
        -------
        list[dict]，每条包含 ``name`` 和 ``expression`` 字段。
        Qlib 不可用时返回空列表。
        """
        if not QLIB_AVAILABLE:
            logger.debug("Qlib 不可用，返回空的 Alpha158 定义列表")
            return []

        try:
            from qlib.contrib.data.handler import Alpha158DL

            conf = {
                "kbar": {},
                "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW", "VWAP"]},
                "rolling": {},
            }
            fields, names = Alpha158DL.get_feature_config(conf)
            return [{"name": n, "expression": f} for f, n in zip(fields, names)]
        except Exception as exc:
            logger.warning("读取 Alpha158 定义失败：%s", exc)
            return []

    @staticmethod
    def available_factor_names() -> list[str]:
        """返回 Alpha158 所有因子名称列表。"""
        return [d["name"] for d in QlibFactorSet.alpha158_definitions()]
