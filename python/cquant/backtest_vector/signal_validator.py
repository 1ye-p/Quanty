"""cquant.backtest_vector.signal_validator — SignalFrame 输入验证工具。

帮助调试自定义策略：检查信号 DataFrame 的 schema、数值合法性，
返回结构化的验证结果。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

_REQUIRED_COLUMNS = {"asset_id", "signal_date", "direction", "strength", "confidence"}
_VALID_DIRECTIONS = {"long", "short"}


@dataclass
class SignalValidationResult:
    """信号验证结果。"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_count: int = 0


def validate_signals(signals: pl.DataFrame) -> SignalValidationResult:
    """验证 SignalFrame 的 schema 和数值合法性。

    Parameters
    ----------
    signals:
        策略 generate_signals() 返回的 DataFrame。

    Returns
    -------
    SignalValidationResult，其中 ``is_valid=True`` 表示信号可被引擎安全消费。
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 空 DataFrame 始终合法（表示该日无信号）
    if signals.is_empty():
        return SignalValidationResult(is_valid=True, row_count=0)

    # 检查必要列
    missing = _REQUIRED_COLUMNS - set(signals.columns)
    if missing:
        errors.append(f"缺少必要列：{sorted(missing)}")
        return SignalValidationResult(is_valid=False, errors=errors, row_count=len(signals))

    # 检查 asset_id 非空
    empty_ids = signals.filter(
        pl.col("asset_id").is_null() | (pl.col("asset_id").str.len_chars() == 0)
    )
    if not empty_ids.is_empty():
        errors.append(f"asset_id 有 {len(empty_ids)} 行为空或 NULL")

    # 检查 direction 合法性
    invalid_dirs = signals.filter(~pl.col("direction").is_in(list(_VALID_DIRECTIONS)))
    if not invalid_dirs.is_empty():
        bad_dirs = invalid_dirs["direction"].unique().to_list()
        errors.append(
            f"direction 包含非法值 {bad_dirs}，仅允许 {sorted(_VALID_DIRECTIONS)}"
        )

    # 检查 strength 非负
    neg_strength = signals.filter(pl.col("strength") < 0)
    if not neg_strength.is_empty():
        errors.append(f"strength 有 {len(neg_strength)} 行为负值")

    # 检查 confidence 在 [0, 1]
    bad_conf = signals.filter(
        (pl.col("confidence") < 0) | (pl.col("confidence") > 1)
    )
    if not bad_conf.is_empty():
        warnings.append(f"confidence 有 {len(bad_conf)} 行超出 [0, 1] 范围")

    # 检查重复信号
    dup_count = len(signals) - signals.unique(subset=["asset_id", "signal_date"]).height
    if dup_count > 0:
        warnings.append(f"存在 {dup_count} 条 (asset_id, signal_date) 重复信号")

    return SignalValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        row_count=len(signals),
    )
