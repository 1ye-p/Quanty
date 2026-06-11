"""cquant.bt_analyzer.trade_analysis — Trade-level analysis.

Analyzes individual trades from a backtest for:
- Holding period distribution
- Win/loss streaks
- Profit factor
- Average win vs average loss

Usage::

    from cquant.bt_analyzer.trade_analysis import TradeAnalyzer

    analyzer = TradeAnalyzer()
    result = analyzer.analyze(trades_df)  # pl.DataFrame with trade data
    print(result.holding_period_stats)
    print(result.win_loss_stats)
    print(result.profit_factor)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class HoldingPeriodStats:
    """Holding period distribution statistics."""
    mean_days: float
    median_days: float
    std_days: float
    min_days: int
    max_days: int
    p25_days: float
    p75_days: float
    distribution: list[dict[str, Any]]  # [{bucket, count}, ...]


@dataclass
class WinLossStreak:
    """A streak of consecutive wins or losses."""
    type: str  # "win" or "loss"
    length: int
    start_date: str
    end_date: str
    total_pnl: float


@dataclass
class WinLossStats:
    """Win/loss statistics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_win_days: float
    avg_loss_days: float
    max_win_streak: int
    max_loss_streak: int
    win_streaks: list[WinLossStreak] = field(default_factory=list)
    loss_streaks: list[WinLossStreak] = field(default_factory=list)


@dataclass
class TradeAnalysisResult:
    """Full trade analysis result."""
    holding_period_stats: HoldingPeriodStats | None = None
    win_loss_stats: WinLossStats | None = None
    profit_factor: float = 0.0
    payoff_ratio: float = 0.0
    expectancy: float = 0.0
    total_trades: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to API-friendly dict."""
        result: dict[str, Any] = {
            "profit_factor": self.profit_factor,
            "payoff_ratio": self.payoff_ratio,
            "expectancy": self.expectancy,
            "total_trades": self.total_trades,
        }
        if self.holding_period_stats:
            result["holding_period_stats"] = {
                "mean_days": self.holding_period_stats.mean_days,
                "median_days": self.holding_period_stats.median_days,
                "std_days": self.holding_period_stats.std_days,
                "min_days": self.holding_period_stats.min_days,
                "max_days": self.holding_period_stats.max_days,
                "p25_days": self.holding_period_stats.p25_days,
                "p75_days": self.holding_period_stats.p75_days,
                "distribution": self.holding_period_stats.distribution,
            }
        if self.win_loss_stats:
            result["win_loss_stats"] = {
                "total_trades": self.win_loss_stats.total_trades,
                "winning_trades": self.win_loss_stats.winning_trades,
                "losing_trades": self.win_loss_stats.losing_trades,
                "win_rate": self.win_loss_stats.win_rate,
                "avg_win": self.win_loss_stats.avg_win,
                "avg_loss": self.win_loss_stats.avg_loss,
                "largest_win": self.win_loss_stats.largest_win,
                "largest_loss": self.win_loss_stats.largest_loss,
                "avg_win_days": self.win_loss_stats.avg_win_days,
                "avg_loss_days": self.win_loss_stats.avg_loss_days,
                "max_win_streak": self.win_loss_stats.max_win_streak,
                "max_loss_streak": self.win_loss_stats.max_loss_streak,
                "win_streaks": [
                    {"type": s.type, "length": s.length, "start_date": s.start_date,
                     "end_date": s.end_date, "total_pnl": s.total_pnl}
                    for s in self.win_loss_stats.win_streaks[:5]
                ],
                "loss_streaks": [
                    {"type": s.type, "length": s.length, "start_date": s.start_date,
                     "end_date": s.end_date, "total_pnl": s.total_pnl}
                    for s in self.win_loss_stats.loss_streaks[:5]
                ],
            }
        return result


class TradeAnalyzer:
    """Analyze individual trades from a backtest.

    Expects a DataFrame with columns:
    - ``trade_date``: date of the trade (str, YYYY-MM-DD)
    - ``asset_id``: asset identifier
    - ``side``: "buy" or "sell"
    - ``price``: trade price
    - ``qty``: quantity traded
    - ``notional``: trade notional value
    """

    def analyze(
        self,
        trades_df: pl.DataFrame,
        date_col: str = "trade_date",
        asset_col: str = "asset_id",
        side_col: str = "side",
        price_col: str = "price",
        qty_col: str = "qty",
        notional_col: str = "notional",
    ) -> TradeAnalysisResult:
        """Run trade-level analysis.

        Parameters
        ----------
        trades_df : pl.DataFrame
            Raw trade/fill data from a backtest.

        Returns
        -------
        TradeAnalysisResult
        """
        if trades_df.is_empty():
            return TradeAnalysisResult(total_trades=0)

        # --- Match buy/sell pairs per asset to compute P&L per round-trip ---
        trades = trades_df.sort([asset_col, date_col])
        round_trips = self._compute_round_trips(
            trades, date_col, asset_col, side_col, price_col, qty_col, notional_col,
        )

        if not round_trips:
            return TradeAnalysisResult(total_trades=0)

        rt_df = pl.DataFrame(round_trips)
        total_trades = len(rt_df)

        # --- Profit factor ---
        gross_profit = rt_df.filter(pl.col("pnl") > 0)["pnl"].sum()
        gross_loss = abs(rt_df.filter(pl.col("pnl") < 0)["pnl"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # --- Payoff ratio ---
        wins = rt_df.filter(pl.col("pnl") > 0)
        losses = rt_df.filter(pl.col("pnl") < 0)
        avg_win = wins["pnl"].mean() if len(wins) > 0 else 0.0
        avg_loss = abs(losses["pnl"].mean()) if len(losses) > 0 else 0.0
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

        # --- Expectancy ---
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        loss_rate = 1 - win_rate
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        # --- Holding period stats ---
        holding_periods = rt_df["holding_days"].to_list()
        hp_stats = self._compute_holding_period_stats(holding_periods)

        # --- Win/loss stats ---
        wl_stats = self._compute_win_loss_stats(rt_df, total_trades, wins, losses)

        return TradeAnalysisResult(
            holding_period_stats=hp_stats,
            win_loss_stats=wl_stats,
            profit_factor=round(profit_factor, 4),
            payoff_ratio=round(payoff_ratio, 4),
            expectancy=round(expectancy, 6),
            total_trades=total_trades,
        )

    def _compute_round_trips(
        self,
        trades: pl.DataFrame,
        date_col: str,
        asset_col: str,
        side_col: str,
        price_col: str,
        qty_col: str,
        notional_col: str,
    ) -> list[dict[str, Any]]:
        """Match buy/sell pairs into round-trip trades."""
        round_trips = []

        for asset_id, group in trades.group_by(asset_col):
            if isinstance(asset_id, tuple):
                asset_id = asset_id[0]

            buys: list[dict[str, Any]] = []
            for row in group.iter_rows(named=True):
                side = row[side_col]
                if side == "buy":
                    buys.append(row)
                elif side == "sell" and buys:
                    buy = buys.pop(0)
                    sell_price = row[price_col]
                    buy_price = buy[price_col]
                    qty = min(buy[qty_col], row[qty_col])
                    pnl = (sell_price - buy_price) * qty

                    buy_date = buy[date_col]
                    sell_date = row[date_col]
                    # Compute holding days (rough)
                    try:
                        bd = _parse_date(str(buy_date))
                        sd = _parse_date(str(sell_date))
                        holding_days = max(1, (sd - bd).days)
                    except Exception:
                        holding_days = 1

                    round_trips.append({
                        "asset_id": asset_id,
                        "buy_date": str(buy_date),
                        "sell_date": str(sell_date),
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "qty": qty,
                        "pnl": round(pnl, 4),
                        "pnl_pct": round((sell_price / buy_price - 1) * 100, 4) if buy_price > 0 else 0.0,
                        "holding_days": holding_days,
                    })

        return round_trips

    def _compute_holding_period_stats(
        self, holding_days: list[int]
    ) -> HoldingPeriodStats:
        """Compute holding period distribution."""
        if not holding_days:
            return HoldingPeriodStats(
                mean_days=0, median_days=0, std_days=0,
                min_days=0, max_days=0, p25_days=0, p75_days=0,
                distribution=[],
            )

        n = len(holding_days)
        sorted_days = sorted(holding_days)
        mean_d = sum(holding_days) / n
        median_d = sorted_days[n // 2]
        std_d = math.sqrt(sum((d - mean_d) ** 2 for d in holding_days) / max(1, n - 1))

        # Distribution buckets
        buckets = [1, 2, 3, 5, 10, 20, 50, 100]
        distribution = []
        for i, upper in enumerate(buckets):
            lower = buckets[i - 1] + 1 if i > 0 else 0
            count = sum(1 for d in holding_days if lower < d <= upper)
            distribution.append({"bucket": f"{lower+1}-{upper}d", "count": count})
        # Overflow
        count_gt = sum(1 for d in holding_days if d > buckets[-1])
        if count_gt > 0:
            distribution.append({"bucket": f">{buckets[-1]}d", "count": count_gt})

        return HoldingPeriodStats(
            mean_days=round(mean_d, 2),
            median_days=median_d,
            std_days=round(std_d, 2),
            min_days=sorted_days[0],
            max_days=sorted_days[-1],
            p25_days=sorted_days[n // 4],
            p75_days=sorted_days[3 * n // 4],
            distribution=distribution,
        )

    def _compute_win_loss_stats(
        self,
        rt_df: pl.DataFrame,
        total_trades: int,
        wins: pl.DataFrame,
        losses: pl.DataFrame,
    ) -> WinLossStats:
        """Compute win/loss streaks and statistics."""
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

        avg_win = wins["pnl"].mean() if len(wins) > 0 else 0.0
        avg_loss = losses["pnl"].mean() if len(losses) > 0 else 0.0
        largest_win = wins["pnl"].max() if len(wins) > 0 else 0.0
        largest_loss = losses["pnl"].min() if len(losses) > 0 else 0.0
        avg_win_days = wins["holding_days"].mean() if len(wins) > 0 else 0.0
        avg_loss_days = losses["holding_days"].mean() if len(losses) > 0 else 0.0

        # Compute streaks
        sorted_rt = rt_df.sort("sell_date")
        win_streaks: list[WinLossStreak] = []
        loss_streaks: list[WinLossStreak] = []

        current_type = None
        current_length = 0
        current_start = ""
        current_pnl = 0.0
        prev_sell_date = ""

        for row in sorted_rt.iter_rows(named=True):
            is_win = row["pnl"] > 0
            trade_type = "win" if is_win else "loss"

            if trade_type == current_type:
                current_length += 1
                current_pnl += row["pnl"]
            else:
                # Save previous streak
                if current_type and current_length > 0:
                    streak = WinLossStreak(
                        type=current_type,
                        length=current_length,
                        start_date=current_start,
                        end_date=prev_sell_date,
                        total_pnl=round(current_pnl, 4),
                    )
                    if current_type == "win":
                        win_streaks.append(streak)
                    else:
                        loss_streaks.append(streak)

                current_type = trade_type
                current_length = 1
                current_start = row["buy_date"]
                current_pnl = row["pnl"]

            prev_sell_date = row["sell_date"]

        # Final streak
        if current_type and current_length > 0:
            streak = WinLossStreak(
                type=current_type,
                length=current_length,
                start_date=current_start,
                end_date=sorted_rt.tail(1)["sell_date"][0],
                total_pnl=round(current_pnl, 4),
            )
            if current_type == "win":
                win_streaks.append(streak)
            else:
                loss_streaks.append(streak)

        # Local aliases for the closure
        _win_streaks = win_streaks
        _loss_streaks = loss_streaks

        max_win_streak = max((s.length for s in _win_streaks), default=0)
        max_loss_streak = max((s.length for s in _loss_streaks), default=0)

        # Sort by length descending
        _win_streaks.sort(key=lambda s: s.length, reverse=True)
        _loss_streaks.sort(key=lambda s: s.length, reverse=True)

        return WinLossStats(
            total_trades=total_trades,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=round(win_rate, 4),
            avg_win=round(avg_win, 4),
            avg_loss=round(avg_loss, 4),
            largest_win=round(largest_win, 4),
            largest_loss=round(largest_loss, 4),
            avg_win_days=round(avg_win_days, 2),
            avg_loss_days=round(avg_loss_days, 2),
            max_win_streak=max_win_streak,
            max_loss_streak=max_loss_streak,
            win_streaks=_win_streaks,
            loss_streaks=_loss_streaks,
        )


def _parse_date(date_str: str):
    """Parse a date string to a date object."""
    from datetime import datetime
    cleaned = str(date_str)[:10].replace("/", "-")
    return datetime.strptime(cleaned, "%Y-%m-%d").date()
