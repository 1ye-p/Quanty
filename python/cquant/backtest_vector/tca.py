"""cquant.backtest_vector.tca — Transaction Cost Analysis.

Provides detailed breakdown of trading costs:
- Commission costs
- Stamp duty costs
- Slippage costs
- Market impact estimation
- Spread cost estimation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class TCASummary:
    """Summary of transaction cost analysis."""
    total_turnover: float = 0.0
    total_commission: float = 0.0
    total_stamp_duty: float = 0.0
    total_slippage: float = 0.0
    total_cost: float = 0.0
    cost_per_trade: float = 0.0
    cost_as_pct_turnover: float = 0.0
    num_trades: int = 0
    avg_trade_size: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TCADetail:
    """Detailed TCA by asset or time period."""
    asset_id: str = ""
    trade_date: str = ""
    turnover: float = 0.0
    commission: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    total_cost: float = 0.0
    cost_pct: float = 0.0
    num_trades: int = 0


class TransactionCostAnalyzer:
    """Transaction Cost Analysis engine.

    Analyzes fills data to produce detailed cost breakdowns.

    Usage::

        analyzer = TransactionCostAnalyzer()
        summary = analyzer.analyze(fills_df)
        by_asset = analyzer.analyze_by_asset(fills_df)
        by_date = analyzer.analyze_by_date(fills_df)
    """

    def analyze(self, fills: pl.DataFrame) -> TCASummary:
        """Analyze total transaction costs from fills data.

        Args:
            fills: DataFrame with columns: trade_date, asset_id, side, qty, price,
                   notional, commission, stamp_duty, slippage, total_cost

        Returns:
            TCASummary with aggregated cost metrics
        """
        if fills.is_empty():
            return TCASummary()

        total_turnover = float(fills["notional"].sum())
        total_commission = float(fills["commission"].sum())
        total_stamp_duty = float(fills["stamp_duty"].sum())
        total_slippage = float(fills["slippage"].sum())
        total_cost = float(fills["total_cost"].sum())
        num_trades = len(fills)

        return TCASummary(
            total_turnover=total_turnover,
            total_commission=total_commission,
            total_stamp_duty=total_stamp_duty,
            total_slippage=total_slippage,
            total_cost=total_cost,
            cost_per_trade=total_cost / num_trades if num_trades > 0 else 0.0,
            cost_as_pct_turnover=total_cost / total_turnover * 100 if total_turnover > 0 else 0.0,
            num_trades=num_trades,
            avg_trade_size=total_turnover / num_trades if num_trades > 0 else 0.0,
        )

    def analyze_by_asset(self, fills: pl.DataFrame) -> list[TCADetail]:
        """Analyze costs grouped by asset.

        Args:
            fills: Fills DataFrame

        Returns:
            List of TCADetail per asset
        """
        if fills.is_empty():
            return []

        grouped = fills.group_by("asset_id").agg([
            pl.col("notional").sum().alias("turnover"),
            pl.col("commission").sum().alias("commission"),
            pl.col("stamp_duty").sum().alias("stamp_duty"),
            pl.col("slippage").sum().alias("slippage"),
            pl.col("total_cost").sum().alias("total_cost"),
            pl.col("qty").count().alias("num_trades"),
        ])

        details = []
        for row in grouped.iter_rows(named=True):
            turnover = float(row["turnover"])
            total_cost = float(row["total_cost"])
            details.append(TCADetail(
                asset_id=row["asset_id"],
                turnover=turnover,
                commission=float(row["commission"]),
                stamp_duty=float(row["stamp_duty"]),
                slippage=float(row["slippage"]),
                total_cost=total_cost,
                cost_pct=total_cost / turnover * 100 if turnover > 0 else 0.0,
                num_trades=int(row["num_trades"]),
            ))

        return sorted(details, key=lambda d: d.total_cost, reverse=True)

    def analyze_by_date(self, fills: pl.DataFrame) -> list[TCADetail]:
        """Analyze costs grouped by trade date.

        Args:
            fills: Fills DataFrame

        Returns:
            List of TCADetail per date
        """
        if fills.is_empty():
            return []

        grouped = fills.group_by("trade_date").agg([
            pl.col("notional").sum().alias("turnover"),
            pl.col("commission").sum().alias("commission"),
            pl.col("stamp_duty").sum().alias("stamp_duty"),
            pl.col("slippage").sum().alias("slippage"),
            pl.col("total_cost").sum().alias("total_cost"),
            pl.col("qty").count().alias("num_trades"),
        ])

        details = []
        for row in grouped.iter_rows(named=True):
            turnover = float(row["turnover"])
            total_cost = float(row["total_cost"])
            details.append(TCADetail(
                trade_date=str(row["trade_date"]),
                turnover=turnover,
                commission=float(row["commission"]),
                stamp_duty=float(row["stamp_duty"]),
                slippage=float(row["slippage"]),
                total_cost=total_cost,
                cost_pct=total_cost / turnover * 100 if turnover > 0 else 0.0,
                num_trades=int(row["num_trades"]),
            ))

        return sorted(details, key=lambda d: d.trade_date)

    def generate_report(self, fills: pl.DataFrame) -> str:
        """Generate a human-readable TCA report.

        Args:
            fills: Fills DataFrame

        Returns:
            Formatted report string
        """
        summary = self.analyze(fills)
        by_asset = self.analyze_by_asset(fills)

        lines = [
            "=== Transaction Cost Analysis Report ===",
            "",
            "Summary:",
            f"  Total Turnover:    {summary.total_turnover:>15,.2f}",
            f"  Total Commission:  {summary.total_commission:>15,.2f}",
            f"  Total Stamp Duty:  {summary.total_stamp_duty:>15,.2f}",
            f"  Total Slippage:    {summary.total_slippage:>15,.2f}",
            f"  Total Cost:        {summary.total_cost:>15,.2f}",
            f"  Cost / Trade:      {summary.cost_per_trade:>15,.2f}",
            f"  Cost % Turnover:   {summary.cost_as_pct_turnover:>14.4f}%",
            f"  Number of Trades:  {summary.num_trades:>15,}",
            f"  Avg Trade Size:    {summary.avg_trade_size:>15,.2f}",
            "",
            "Top 10 Assets by Cost:",
            f"  {'Asset':<20} {'Turnover':>15} {'Cost':>15} {'Cost%':>8} {'Trades':>8}",
            f"  {'-'*20} {'-'*15} {'-'*15} {'-'*8} {'-'*8}",
        ]

        for detail in by_asset[:10]:
            lines.append(
                f"  {detail.asset_id:<20} {detail.turnover:>15,.2f} "
                f"{detail.total_cost:>15,.2f} {detail.cost_pct:>7.4f}% {detail.num_trades:>8,}"
            )

        return "\n".join(lines)
