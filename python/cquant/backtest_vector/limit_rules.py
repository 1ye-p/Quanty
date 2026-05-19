"""A-share daily price limit rules by board type."""
from __future__ import annotations

from enum import Enum


class BoardType(Enum):
    MAIN = "main"           # 主板: ±10%, ST ±5%
    CHINEXT = "chinext"     # 创业板: ±20%
    STAR = "star"           # 科创板: ±20%
    BSE = "bse"             # 北交所: ±30%


def detect_board(asset_id: str) -> BoardType:
    """Detect board type from asset_id prefix.

    Conventions:
      - SH600xxx, SH601xxx, SH603xxx, SH605xxx → Main (SSE)
      - SH688xxx → STAR
      - SZ000xxx, SZ001xxx, SZ002xxx, SZ003xxx → Main (SZSE)
      - SZ300xxx, SZ301xxx → ChiNext
      - BJ4xxxxx, BJ8xxxxx → BSE
    """
    if not asset_id or len(asset_id) < 7:
        return BoardType.MAIN

    exchange = asset_id[:2]
    num = asset_id[2:]  # e.g., "600000" for SH600000

    if exchange == "SH":
        if num.startswith("688"):
            return BoardType.STAR
        return BoardType.MAIN
    elif exchange == "SZ":
        if num.startswith("3"):
            return BoardType.CHINEXT
        return BoardType.MAIN
    elif exchange == "BJ":
        return BoardType.BSE
    return BoardType.MAIN


def get_limit_pct(asset_id: str, is_st: bool = False) -> float:
    """Return the daily price limit percentage as a decimal."""
    if is_st:
        return 0.05
    board = detect_board(asset_id)
    return {
        BoardType.MAIN: 0.10,
        BoardType.CHINEXT: 0.20,
        BoardType.STAR: 0.20,
        BoardType.BSE: 0.30,
    }[board]


def is_at_limit_up(close: float, prev_close: float, asset_id: str, is_st: bool = False) -> bool:
    """Check if price is at the upper limit."""
    if prev_close <= 0 or close <= 0:
        return False
    limit_pct = get_limit_pct(asset_id, is_st)
    if limit_pct == 0.0:
        return False
    return close >= prev_close * (1 + limit_pct - 0.005)


def is_at_limit_down(close: float, prev_close: float, asset_id: str, is_st: bool = False) -> bool:
    """Check if price is at the lower limit."""
    if prev_close <= 0 or close <= 0:
        return False
    limit_pct = get_limit_pct(asset_id, is_st)
    if limit_pct == 0.0:
        return False
    return close <= prev_close * (1 - limit_pct + 0.005)
