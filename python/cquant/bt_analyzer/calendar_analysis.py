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
class HolidayPreDayEffect:
    """Effect statistics for N trading days before a holiday."""
    n: int
    mean_return: float
    std_return: float
    win_rate: float
    t_stat: float
    count: int


@dataclass
class HolidayEffect:
    """Holiday effect analysis for one holiday type."""
    holiday: str
    pre_days: list[HolidayPreDayEffect] = field(default_factory=list)


@dataclass
class CalendarAnalysisResult:
    """Full calendar analysis result."""
    month_effects: list[MonthEffect] = field(default_factory=list)
    weekday_effects: list[WeekdayEffect] = field(default_factory=list)
    month_end_effect: MonthEndEffect | None = None
    holiday_effects: list[HolidayEffect] = field(default_factory=list)
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
            "holiday_effects": [
                {
                    "holiday": h.holiday,
                    "pre_days": [
                        {
                            "n": pd.n,
                            "mean_return": pd.mean_return,
                            "std_return": pd.std_return,
                            "win_rate": pd.win_rate,
                            "t_stat": pd.t_stat,
                            "count": pd.count,
                        }
                        for pd in h.pre_days
                    ],
                }
                for h in self.holiday_effects
            ],
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

# Holiday detection ranges: (display_name, start_month, start_day, end_month, end_day)
# We scan the CNCalendar holiday set to find consecutive non-trading days within
# these windows. The first day of each cluster is the "holiday start" we use for
# pre-holiday effect analysis.
_HOLIDAY_WINDOWS: list[tuple[str, int, int, int, int]] = [
    ("春节", 1, 20, 2, 15),    # Spring Festival: late Jan to mid Feb
    ("国庆", 9, 25, 10, 10),   # National Day: late Sep to early Oct
    ("元旦", 12, 25, 1, 5),    # New Year: late Dec to early Jan (cross-year)
]


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

        # --- Holiday effect ---
        holiday_effects = self._compute_holiday_effects(df)

        return CalendarAnalysisResult(
            month_effects=month_effects,
            weekday_effects=weekday_effects,
            month_end_effect=month_end_effect,
            holiday_effects=holiday_effects,
            total_observations=total,
        )

    def _compute_holiday_effects(self, df: pl.DataFrame) -> list[HolidayEffect]:
        """Compute pre-holiday return effects for CN A-share holidays.

        For each holiday (Spring Festival, National Day, New Year):
        - Find the first trading day after the holiday break (the "reopening" day)
        - Look back N=1,3,5 trading days before the holiday break
        - Compute mean return, win rate, and t-stat for those pre-holiday days

        Uses the CNCalendar to identify holiday dates from the built-in set.
        """
        from datetime import date, timedelta

        try:
            from cquant.market_calendar.calendars.cn import CNCalendar
            cal = CNCalendar()
        except ImportError:
            logger.debug("CNCalendar not available, skipping holiday effects")
            return []

        # Build the set of trading dates present in the returns data
        trading_dates_in_data: set[date] = set()
        for row in df.select("dt").iter_rows():
            d = row[0]
            if isinstance(d, date):
                trading_dates_in_data.add(d)

        if not trading_dates_in_data:
            return []

        # Sorted list of trading dates from the data for prev-day lookup
        sorted_trading_dates = sorted(trading_dates_in_data)

        # For each holiday, find the "reopening" dates (first trading day after each
        # holiday break) and then look backwards to find pre-holiday trading days.
        holiday_effects: list[HolidayEffect] = []

        for holiday_name, win_start_m, win_start_d, win_end_m, win_end_d in _HOLIDAY_WINDOWS:
            # Find all years covered by the data
            min_year = min(d.year for d in sorted_trading_dates)
            max_year = max(d.year for d in sorted_trading_dates)

            pre_day_returns: dict[int, list[float]] = {1: [], 3: [], 5: []}

            for year in range(min_year, max_year + 1):
                # Build the window date range for this year
                try:
                    if holiday_name == "元旦":
                        # Cross-year: Dec 25 year-1 to Jan 5 year
                        win_start = date(year, win_start_m, win_start_d)
                        win_end = date(year + 1, win_end_m, win_end_d)
                    else:
                        win_start = date(year, win_start_m, win_start_d)
                        win_end = date(year, win_end_m, win_end_d)
                except ValueError:
                    continue

                # Find all non-trading days (holidays) within this window
                # that are in the CNCalendar holiday set
                holiday_cluster: list[date] = []
                current = win_start
                while current <= win_end:
                    if not cal.is_trading_day(current):
                        holiday_cluster.append(current)
                    current += timedelta(days=1)

                if not holiday_cluster:
                    continue

                # The last day of the holiday cluster is the day before reopening
                # Find the reopening date (first trading day after the cluster)
                last_holiday = holiday_cluster[-1]
                # Walk forward to find the first trading day (reopening)
                reopening = last_holiday + timedelta(days=1)
                while reopening <= win_end + timedelta(days=5):
                    if cal.is_trading_day(reopening) and reopening in trading_dates_in_data:
                        break
                    reopening += timedelta(days=1)
                else:
                    continue

                # Now look backwards from the first day of the holiday cluster
                # to find the N trading days before it
                first_holiday = holiday_cluster[0]
                # Find the trading day immediately before the holiday cluster
                prev_day = first_holiday - timedelta(days=1)
                while prev_day >= first_holiday - timedelta(days=10):
                    if prev_day in trading_dates_in_data:
                        break
                    prev_day -= timedelta(days=1)
                else:
                    continue

                # prev_day is the last trading day before the holiday
                # Find its index in sorted_trading_dates
                import bisect
                idx = bisect.bisect_left(sorted_trading_dates, prev_day)
                if idx >= len(sorted_trading_dates) or sorted_trading_dates[idx] != prev_day:
                    continue

                # Collect returns for N=1,3,5 trading days before the holiday
                for n in [1, 3, 5]:
                    start_idx = max(0, idx - n + 1)
                    for i in range(start_idx, idx + 1):
                        td = sorted_trading_dates[i]
                        # Look up the return for this date from df
                        ret_rows = df.filter(pl.col("dt") == td).select("ret").to_list()
                        if ret_rows:
                            pre_day_returns[n].append(ret_rows[0][0])

            # Build HolidayPreDayEffect for each N
            pre_days: list[HolidayPreDayEffect] = []
            for n in [1, 3, 5]:
                rets = pre_day_returns[n]
                if not rets:
                    pre_days.append(HolidayPreDayEffect(
                        n=n, mean_return=0.0, std_return=0.0,
                        win_rate=0.0, t_stat=0.0, count=0,
                    ))
                    continue

                mean_r = sum(rets) / len(rets)
                if len(rets) > 1:
                    var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
                    std_r = var ** 0.5
                else:
                    std_r = 0.0

                wins = sum(1 for r in rets if r > 0)
                wr = wins / len(rets) if rets else 0.0

                # t-stat: test if mean return is significantly different from 0
                se = std_r / (len(rets) ** 0.5) if std_r > 0 and len(rets) > 0 else 0.0
                t = mean_r / se if se > 0 else 0.0

                pre_days.append(HolidayPreDayEffect(
                    n=n,
                    mean_return=round(mean_r, 6),
                    std_return=round(std_r, 6),
                    win_rate=round(wr, 4),
                    t_stat=round(t, 4),
                    count=len(rets),
                ))

            holiday_effects.append(HolidayEffect(
                holiday=holiday_name,
                pre_days=pre_days,
            ))

        return holiday_effects


def _norm_cdf(x: float) -> float:
    """Approximate standard normal CDF using the error function."""
    import math
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
