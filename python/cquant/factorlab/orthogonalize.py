"""因子正交化（cross-sectional residual orthogonalization）。

对每个 timestamp 截面，把非 base 因子对 base 因子做 OLS 回归取残差，
残差即正交化后的因子值（已去除 base 因子线性信息）。原始列保留不变，
新增 ``<原名>_orth`` 列，原始/正交化两套可切换。
"""

from __future__ import annotations

import logging

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)


def orthogonalize(
    factors: pl.DataFrame,
    base: list[str],
    timestamp_col: str = "trade_date",
) -> pl.DataFrame:
    """对非 base 因子做截面残差正交化。

    在每个 ``timestamp_col`` 截面内，对每个非 base 因子列，用 base 因子列做 OLS
    回归（截距 + base），取残差作为正交化值，写入新列 ``<原名>_orth``。
    原始列保留，便于在原始/正交化之间切换。

    缺失值不参与回归。若某截面内 base 因子全为常数或缺失（回归矩阵秩亏），
    该截面内残差 = 原值（无法正交化）。

    Args:
        factors: 长表因子 DataFrame，必须包含 ``timestamp_col`` 及各因子数值列。
        base: 作为基准的因子列名列表（不参与正交化）。
        timestamp_col: 截面分组列名，默认 ``trade_date``。

    Returns:
        在 ``factors`` 基础上追加 ``<非base因子>_orth`` 列的 DataFrame。
        行顺序与输入一致。
    """
    if timestamp_col not in factors.columns:
        raise ValueError(f"timestamp_col {timestamp_col!r} not found in DataFrame columns")

    # 校验 base 列存在；不存在则视为无法正交化，直接返回原表
    missing_base = [c for c in base if c not in factors.columns]
    if missing_base:
        raise ValueError(f"base factor columns not found: {missing_base}")

    # 非 base 因子列 = 数值列，排除 timestamp_col 与 base
    factor_cols = [
        c
        for c in factors.columns
        if c != timestamp_col and c not in base and factors.schema[c] in pl.NUMERIC_DTYPES
    ]

    # 没有 target 因子，无需正交化
    if not factor_cols:
        return factors.clone()

    # 仅保留计算所需列，按截面分组逐列算残差，最后 join 回原表。
    # 用全局行号做 join key，避免 timestamp 非唯一导致 fan-out。
    subset_cols = [timestamp_col, *base, *factor_cols]
    work = factors.select([c for c in subset_cols if c in factors.columns]).with_row_index(
        "_orth_row",
    )

    orth_frames: list[pl.DataFrame] = []
    for (ts,), group in work.group_by([timestamp_col], maintain_order=True):
        # base 矩阵（含截距项）；对 NaN/inf 做掩码
        base_vals = {b: group[b].to_numpy() for b in base}
        n = group.height

        orth_cols: dict[str, np.ndarray] = {}
        for fcol in factor_cols:
            y = np.asarray(group[fcol].to_numpy(), dtype=np.float64)
            # 缺失值掩码（NaN 或 inf）
            finite_y = np.isfinite(y)
            orth = np.full(n, np.nan, dtype=np.float64)

            # 构建回归矩阵 X = [1, base1, base2, ...]
            x_cols = [np.ones(n)]
            finite_x = np.ones(n, dtype=bool)
            for b in base:
                xv = base_vals[b].astype(np.float64, copy=False)
                x_cols.append(xv)
                finite_x &= np.isfinite(xv)

            valid = finite_y & finite_x

            # base 全缺失或常数（X 秩亏）→ 残差 = 原值
            if valid.sum() < 2:
                orth[:] = y
                orth_cols[fcol] = orth
                continue

            X = np.column_stack(x_cols)[valid]
            yv = y[valid]

            # base 列全常数时 X 退化；lstsq 在秩亏时仍给最小范数解，
            # 但若 base 列无变化（方差 0），残差 ≈ 0，意义不大 → 回退原值。
            base_block = X[:, 1:] if len(base) > 0 else np.empty((X.shape[0], 0))
            if base_block.shape[1] > 0 and np.allclose(base_block.std(axis=0), 0.0):
                orth[:] = y
                orth_cols[fcol] = orth
                continue

            try:
                coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
                resid = yv - X @ coef
            except np.linalg.LinAlgError:
                orth[:] = y
                orth_cols[fcol] = orth
                continue

            orth[valid] = resid
            # 非法位置（缺失）保留原值，便于下游识别
            orth[~finite_y] = y[~finite_y]
            orth_cols[fcol] = orth

        orth_df = pl.DataFrame(
            {"_orth_row": group["_orth_row"], **{f"{c}_orth": orth_cols[c] for c in factor_cols}},
        )
        orth_frames.append(orth_df)

    orth_all = pl.concat(orth_frames, how="vertical")
    result = factors.with_row_index("_orth_row").join(orth_all, on="_orth_row", how="left")
    return result.drop("_orth_row")
