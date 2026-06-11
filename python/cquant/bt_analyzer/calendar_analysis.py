"""cquant.bt_analyzer.calendar_analysis — Calendar effect analysis.

Analyzes portfolio returns for calendar-based patterns:
- Month-of-year effect (January effect, Santa rally, etc.)
- Day-of-week effect
- Month-end / month-start effect

Usage::

    from cquant.bt_analyzer.calendar_analysis import CalendarAnalyzer

    analyzer = CalendarAnalyzer()
    result = analyzer.analyze(returns_series)  # pd.Series indexed by date
    print(result.month_effect)
    print(result.weekday_effect)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class MonthEffect:
    """Per-month return statistics."""
    month: int
    label: str
    mean_return: float
    std_return: float
    win_rate: float
    count: int


@dataclass
class WeekdayEffect:
    """Per-weekday return statistics."""
    weekday: int  # 0=Monday ... 4=Friday
    label: str
    mean_return: float
    std_return: float
    win_rate: float
    count: int


@dataclass
class MonthEndEffect:
    """Month-end vs non-month-end return comparison."""
    month_end_mean: float
    month_end_std: float
    month_end_count: int
    non_month_end_mean: float
    non_month_end_std: float
    non_month_end_count: int
    t_statistic: float
    p_value: float


@dataclass
class CalendarAnalysisResult:
    """Full calendar analysis result."""
    month_effects: list[MonthEffect] = field(default_factory=list)
    weekday_effects: list[WeekdayEffect] = field(default_factory=list)
    month_end_effect: MonthEndEffect | None = None
    total_observations: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to API-friendly dict."""
        return {
            "month_effects": [
                {
                    "month": m.month,
                    "label": m.label,
                    "mean_return": m.mean_return,
                    "std_return": m.std_return,
                    "win_rate": m.win_rate,
                    "count": m.count,
                }
                for m in self.month_effects
            ],
            "weekday_effects": [
                {
                    "weekday": w.weekday,
                    "label": w.label,
                    "mean_return": w.mean_return,
                    "std_return": w.std_return,
                    "win_rate": w.win_rate,
                    "count": w.count,
                }
                for w in self.weekday_effects
            ],
            "month_end_effect": {
                "month_end_mean": self.month_end_effect.month_end_mean,
                "month_end_std": self.month_end_effect.month_end_std,
                "month_end_count": self.month_end_effect.month_end_count,
                "non_month_end_mean": self.month_end_effect.non_month_end_mean,
                "non_month_end_std": self.month_end_effect.non_month_end_std,
                "non_month_end_count": self.month_end_effect.non_month_end_count,
                "t_statistic": self.month_end_effect.t_statistic,
                "p_value": self.month_end_effect.p_value,
            }
            if self.month_end_effect
            else None,
            "total_observations": self.total_observations,
        }


MONTH_LABELS = {
    1: "一月", 2: "二月", 3: "三月", 4: "四月",
    5: "五月", 6: "六月", 7: "七月", 8: "八月",
    9: "九月", 10: "十月", 11: "十一月", 12: "十二月",
}

WEEKDAY_LABELS = {
    0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五",
}


class CalendarAnalyzer:
    """Analyze calendar effects in portfolio returns.

    Parameters
    ----------
    returns : pl.DataFrame | None
        DataFrame with columns ``trade_date`` (str/datetime) and ``returns`` (float).
        If None, ``analyze()`` must be called with explicit data.
    """

    def analyze(
        self,
        returns_df: pl.DataFrame,
        date_col: str = "trade_date",
        return_col: str = "returns",
    ) -> CalendarAnalysisResult:
        """Run calendar analysis on a returns DataFrame.

        Parameters
        ----------
        returns_df : pl.DataFrame
            Must contain ``date_col`` and ``return_col``.
        date_col : str
            Name of the date column.
        return_col : str
            Name of the return column.

        Returns
        -------
        CalendarAnalysisResult
        """
        df = returns_df.select([
            pl.col(date_col).cast(pl.Utf8).alias("date_str"),
            pl.col(return_col).alias("ret"),
        ]).drop_nulls()

        # Parse dates
        df = df.with_columns(
            pl.col("date_str").str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("dt"),
        ).drop_nulls(subset=["dt"])

        df = df.with_columns([
            pl.col("dt").dt.month().alias("month"),
            pl.col("dt").dt.weekday().alias("weekday"),  # 0=Mon in Polars
        ])

        total = len(df)

        # --- Month effect ---
        month_stats = (
            df.group_by("month")
            .agg([
                pl.col("ret").mean().alias("mean_return"),
                pl.col("ret").std().alias("std_return"),
                (pl.col("ret") > 0).mean().alias("win_rate"),
                pl.col("ret").count().alias("count"),
            ])
            .sort("month")
        )

        month_effects = []
        for row in month_stats.iter_rows(named=True):
            month_effects.append(MonthEffect(
                month=row["month"],
                label=MONTH_LABELS.get(row["month"], f"M{row['month']}"),
                mean_return=round(row["mean_return"], 6),
                std_return=round(row["std_return"], 6),
                win_rate=round(row["win_rate"], 4),
                count=row["count"],
            ))

        # --- Weekday effect ---
        weekday_stats = (
            df.group_by("weekday")
            .agg([
                pl.col("ret").mean().alias("mean_return"),
                pl.col("ret").std().alias("std_return"),
                (pl.col("ret") > 0).mean().alias("win_rate"),
                pl.col("ret").count().alias("count"),
            ])
            .sort("weekday")
        )

        weekday_effects = []
        for row in weekday_stats.iter_rows(named=True):
            wd = row["weekday"]
            weekday_effects.append(WeekdayEffect(
                weekday=wd,
                label=WEEKDAY_LABELS.get(wd, f"W{wd}"),
                mean_return=round(row["mean_return"], 6),
                std_return=round(row["std_return"], 6),
                win_rate=round(row["win_rate"], 4),
                count=row["count"],
            ))

        # --- Month-end effect ---
        # Month-end: last 3 trading days of each month
        df_sorted = df.sort("dt")
        df_sorted = df_sorted.with_columns(
            pl.col("dt").dt.month().alias("m"),
            pl.col("dt").dt.year().alias("y"),
        )

        # For each year-month, mark last 3 rows as month-end
        month_end_flags = []
        for (y, m), group in df_sorted.group_by(["y", "m"]):
            n = len(group)
            for i, row in enumerate(group.iter_rows(named=True)):
                month_end_flags.append({
                    "date_str": row["date_str"],
                    "is_month_end": i >= max(0, n - 3),
                })

        if month_end_flags:
            me_df = pl.DataFrame(month_end_flags)
            df_with_me = df_sorted.join(me_df, on="date_str", how="left")
            df_with_me = df_with_me.with_columns(
                pl.col("is_month_end").fill_null(False),
            )

            me_group = df_with_me.group_by("is_month_end").agg([
                pl.col("ret").mean().alias("mean_ret"),
                pl.col("ret").std().alias("std_ret"),
                pl.col("ret").count().alias("cnt"),
            ])

            me_row = None
            non_me_row = None
            for row in me_group.iter_rows(named=True):
                if row["is_month_end"]:
                    me_row = row
                else:
                    non_me_row = row

            if me_row and non_me_row:
                # Simple t-stat approximation
                import math
                pooled_se = math.sqrt(
                    (me_row["std_ret"] ** 2 / me_row["cnt"])
                    + (non_me_row["std_ret"] ** 2 / non_me_row["cnt"])
                )
                t_stat = (
                    (me_row["mean_ret"] - non_me_row["mean_ret"]) / pooled_se
                    if pooled_se > 0
                    else 0.0
                )
                # Approximate p-value (two-tailed, normal approx)
                p_value = 2 * (1 - _norm_cdf(abs(t_stat)))

                month_end_effect = MonthEndEffect(
                    month_end_mean=round(me_row["mean_ret"], 6),
                    month_end_std=round(me_row["std_ret"], 6),
                    month_end_count=me_row["cnt"],
                    non_month_end_mean=round(non_me_row["mean_ret"], 6),
                    non_month_end_std=round(non_me_row["std_ret"], 6),
                    non_month_end_count=non_me_row["cnt"],
                    t_statistic=round(t_stat, 4),
                    p_value=round(p_value, 4),
                )
            else:
                month_end_effect = None
        else:
            month_end_effect = None

        return CalendarAnalysisResult(
            month_effects=month_effects,
            weekday_effects=weekday_effects,
            month_end_effect=month_end_effect,
            total_observations=total,
        )


def _norm_cdf(x: float) -> float:
    """Approximate standard normal CDF using the error function."""
    import math
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
