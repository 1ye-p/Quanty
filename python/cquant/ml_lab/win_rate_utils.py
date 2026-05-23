"""cquant.ml_lab.win_rate_utils — 从历史成交记录计算 Kelly 胜率。

将 BacktestResult.fills 中的成交记录按 FIFO 配对，
计算每只股票的历史胜率用于 KellySizer 的 win_rates 参数。
"""
from __future__ import annotations

import polars as pl


def compute_win_rates_from_fills(
    fills: pl.DataFrame,
    min_trades: int = 5,
) -> dict[str, float]:
    """从成交记录计算各资产的历史胜率。

    Parameters
    ----------
    fills:
        BacktestResult.fills DataFrame，包含列：
        [asset_id, side, qty, price, trade_date, total_cost]。
    min_trades:
        计入结果的最小配对成交笔数。

    Returns
    -------
    ``dict[asset_id, win_rate]``，win_rate 在 [0.0, 1.0] 之间。
    """
    if fills.is_empty() or "side" not in fills.columns:
        return {}

    required = {"asset_id", "side", "qty", "price"}
    if required - set(fills.columns):
        return {}

    result: dict[str, float] = {}

    for (asset_id,), group in fills.group_by("asset_id"):
        buys = (
            group.filter(pl.col("side") == "buy")
            .sort("trade_date")
            .select(["qty", "price"])
            .to_dicts()
        )
        sells = (
            group.filter(pl.col("side") == "sell")
            .sort("trade_date")
            .select(["qty", "price"])
            .to_dicts()
        )

        if not buys or not sells:
            continue

        buy_queue: list[tuple[float, float]] = [(b["qty"], b["price"]) for b in buys]
        wins = 0
        total_pairs = 0
        buy_idx = 0

        for sell in sells:
            sell_qty = sell["qty"]
            sell_price = sell["price"]
            remaining_sell = sell_qty

            while remaining_sell > 0 and buy_idx < len(buy_queue):
                buy_qty, buy_price = buy_queue[buy_idx]
                match_qty = min(remaining_sell, buy_qty)

                pnl = (sell_price - buy_price) * match_qty
                total_pairs += 1
                if pnl > 0:
                    wins += 1

                remaining_sell -= match_qty
                buy_queue[buy_idx] = (buy_qty - match_qty, buy_price)
                if buy_queue[buy_idx][0] <= 0:
                    buy_idx += 1

        if total_pairs >= min_trades:
            result[asset_id] = float(wins) / float(total_pairs)

    return result
