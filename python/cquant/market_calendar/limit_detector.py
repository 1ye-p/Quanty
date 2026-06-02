"""Limit up/down detection including yizi-board (一字板)."""

from __future__ import annotations

from cquant.core.enums import LimitStatus


def detect_limit(
    bar: dict,
    pre_close: float,
    limit_pct: float,
    tolerance: float = 0.99,
) -> LimitStatus:
    """Detect limit status from bar data.

    Args:
        bar: dict with keys open, high, low, close, volume
        pre_close: previous close price
        limit_pct: limit percentage (e.g. 0.10 for ±10%)
        tolerance: detection tolerance (default 0.99 to handle rounding)

    Returns:
        LimitStatus enum value
    """
    if pre_close <= 0 or limit_pct <= 0:
        return LimitStatus.NONE

    change_pct = (bar["close"] - pre_close) / pre_close
    threshold = limit_pct * tolerance

    is_yizi = bar["open"] == bar["close"] == bar["high"] == bar["low"]

    if change_pct >= threshold:
        return LimitStatus.YIZI_UP if is_yizi else LimitStatus.UP
    if change_pct <= -threshold:
        return LimitStatus.YIZI_DOWN if is_yizi else LimitStatus.DOWN
    return LimitStatus.NONE
