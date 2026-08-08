"""分红事件因子：基于 silver_corporate_actions 的事件型聚合。

与 ``ValuationFactor`` / ``FundamentalFactor`` 不同，分红是事件型数据
（一行一次分红事件，而非逐日），因此无法用简单的 trade_date join。
这些因子从 ``ctx.extra['corporate_actions']``（materialize.py 的
``_load_corporate_actions`` 加载）读取，按 trade_date 回看窗口聚合：

- ``DividendYield12M``：过去 12 个月每股现金分红之和 / 当前股价（年化股息率）
- ``DividendMomentum``：分红金额同比变化（trailing 12M / previous 12M - 1）

事件因子对每个 (asset_id, trade_date) 行，聚合 ``ex_date`` 落在回看窗口内的
所有分红事件。回看窗口以 trade_date 为右端点，天然 PIT。
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext


class _DividendEventFactor(Factor):
    """分红事件因子基类：加载并按窗口聚合 silver_corporate_actions。

    子类需实现 ``_aggregate``，输入为某资产在回看窗口内的分红事件 DataFrame
    （含 ``cash_amount`` / ``ratio`` / ``ex_date``），输出该行对应的因子值
    （float 或 None）。
    """

    # 回看窗口长度（天）；DividendYield12M 需 365，Momentum 需 730（两年）
    _window_days: int = 365

    @property
    def tags(self) -> list[str]:
        return ["fundamental", "value", "dividend"]

    def _load_events(self, ctx: FactorContext) -> pl.DataFrame:
        """从 ctx.extra 取已实施分红事件，返回清洗后的 DataFrame。

        保证 ``ex_date`` 为 ``pl.Date``、``cash_amount`` 为 ``pl.Float64``。
        """
        ca = ctx.extra.get("corporate_actions")
        if ca is None or ca.is_empty():
            return pl.DataFrame()
        if "ex_date" not in ca.columns or "cash_amount" not in ca.columns:
            return pl.DataFrame()

        ca = ca.filter(pl.col("ex_date").is_not_null())
        if ca.is_empty():
            return pl.DataFrame()

        # 统一类型
        if ca["ex_date"].dtype != pl.Date:
            if ca["ex_date"].dtype == pl.Utf8:
                ca = ca.with_columns(pl.col("ex_date").str.to_date())
            else:
                ca = ca.with_columns(pl.col("ex_date").cast(pl.Date))
        if ca["cash_amount"].dtype != pl.Float64:
            ca = ca.with_columns(pl.col("cash_amount").cast(pl.Float64))
        return ca

    def compute(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.Series:
        events = self._load_events(ctx)
        if events.is_empty():
            return pl.Series(name=self.name, values=[None] * len(frame), dtype=pl.Float64)

        if "trade_date" not in frame.columns or "asset_id" not in frame.columns:
            return pl.Series(name=self.name, values=[None] * len(frame), dtype=pl.Float64)

        # 确保 frame.trade_date 为 Date
        td = frame["trade_date"]
        if td.dtype != pl.Date:
            if td.dtype == pl.Utf8:
                td = td.str.to_date()
            else:
                td = td.cast(pl.Date)

        values: list[float | None] = []
        window = timedelta(days=self._window_days)

        # 按 asset_id 分组事件，避免对每行全表扫描
        # group_by 返回元组 key ('SZSE:000001',)，取第一个元素
        events_by_asset: dict[str, pl.DataFrame] = {}
        for key, sub in events.group_by("asset_id"):
            asset_key = key[0] if isinstance(key, tuple) else key
            events_by_asset[str(asset_key)] = sub.sort("ex_date")

        trade_dates = td.to_list()
        asset_ids = frame["asset_id"].to_list()
        closes = frame["close"].to_list() if "close" in frame.columns else [None] * len(frame)

        for i in range(len(frame)):
            td_i = trade_dates[i]
            aid = asset_ids[i]
            if td_i is None or aid is None:
                values.append(None)
                continue
            sub = events_by_asset.get(aid)
            if sub is None or sub.is_empty():
                values.append(None)
                continue
            # 回看窗口内的分红事件
            window_start = td_i - window
            in_window = sub.filter(
                (pl.col("ex_date") <= td_i) & (pl.col("ex_date") > window_start)
            )
            close_i = closes[i]
            val = self._aggregate(in_window, close_i, td_i, sub, window)
            values.append(val)

        return pl.Series(name=self.name, values=values, dtype=pl.Float64)

    def _aggregate(
        self,
        in_window: pl.DataFrame,
        close: float | None,
        trade_date,
        all_events: pl.DataFrame,
        window: timedelta,
    ) -> float | None:
        """子类实现：从窗口内事件计算因子值。"""
        raise NotImplementedError


class DividendYield12M(_DividendEventFactor):
    """过去 12 个月现金分红率（年化股息率 = 累计每股现金分红 / 当前股价）。

    窗口 365 天，聚合窗口内所有已实施分红的 ``cash_amount`` 之和，除以当前
    ``close``。无分红或无股价时返回 None。
    """

    _window_days = 365

    @property
    def name(self) -> str:
        return "dividend_yield_12m"

    @property
    def description(self) -> str:
        return "过去 12 个月累计每股现金分红 / 当前股价（年化股息率）"

    @property
    def lookback_days(self) -> int:
        return 400  # 365 天窗口 + 缓冲

    def _aggregate(self, in_window, close, trade_date, all_events, window):
        if in_window.is_empty() or close is None or close == 0:
            return None
        total_cash = in_window["cash_amount"].sum()
        if total_cash is None:
            return None
        return float(total_cash) / float(close)


class DividendMomentum(_DividendEventFactor):
    """分红增长（同比）：trailing 12M 累计分红 / previous 12M 累计分红 - 1。

    需 730 天窗口：[t-730, t-365] 为上一年、(t-365, t] 为本年。
    两年都需有分红事件，否则返回 None（避免除零或单年噪音）。
    """

    _window_days = 730

    @property
    def name(self) -> str:
        return "dividend_momentum"

    @property
    def description(self) -> str:
        return "分红金额同比变化（trailing 12M / previous 12M - 1）"

    @property
    def lookback_days(self) -> int:
        return 765  # 730 天窗口 + 缓冲

    def _aggregate(self, in_window, close, trade_date, all_events, window):
        # in_window 是 [t-730, t]，需拆成本年 (t-365, t] 与上年 [t-730, t-365]
        from datetime import timedelta as _td
        half = _td(days=365)
        cur_start = trade_date - half
        prev_start = trade_date - window

        if in_window.is_empty():
            return None
        cur_cash = in_window.filter(
            (pl.col("ex_date") <= trade_date) & (pl.col("ex_date") > cur_start)
        )["cash_amount"].sum()
        prev_cash = in_window.filter(
            (pl.col("ex_date") <= cur_start) & (pl.col("ex_date") > prev_start)
        )["cash_amount"].sum()

        if cur_cash is None or prev_cash is None or prev_cash == 0:
            return None
        return float(cur_cash) / float(prev_cash) - 1.0


DIVIDEND_FACTORS = [DividendYield12M(), DividendMomentum()]
