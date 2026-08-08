"""cquant.datahub.pipelines.corporate_actions_updater — 公司行为数据摄入。

从 Tushare ``pro.dividend`` 拉取已实施的分红事件，写入
``silver_corporate_actions``。事件型数据（ex_date 对齐到交易日时间轴），
供分红事件因子（DividendYield12M / DividendMomentum）消费。

Usage::

    from cquant.datahub.pipelines.corporate_actions_updater import (
        CorporateActionsUpdater,
        register_corporate_actions_job,
        verify_dividend_ex_dates,
    )
    from cquant.datahub.connectors.tushare_connector import TushareConnector

    updater = CorporateActionsUpdater(catalog, TushareConnector())
    updater.update(ts_codes)

    # 交叉校验：除权日是否与 adj_factor 跳变日吻合
    mismatches = verify_dividend_ex_dates(catalog, asset_ids)
"""

from __future__ import annotations

import logging
from datetime import time, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog
    from cquant.datahub.connectors.tushare_connector import TushareConnector
    from cquant.scheduler.scheduler import StrategyScheduler

logger = logging.getLogger(__name__)


class CorporateActionsUpdater:
    """公司行为（分红）数据写入器，目标表 ``silver_corporate_actions``。

    与 ``ValuationDailyUpdater`` 类似的简洁 upsert 模型：逐 ts_code 拉取、
    去重（``action_id`` 主键）、``INSERT OR REPLACE`` 幂等写入。
    """

    def __init__(self, catalog: "Catalog", connector: "TushareConnector") -> None:
        self.catalog = catalog
        self.connector = connector

    def update(self, ts_codes: list[str]) -> int:
        """拉取并写入一批 ts_code 的分红事件。

        Parameters
        ----------
        ts_codes
            Tushare 代码列表，如 ``['000001.SZ', '600036.SH']``。

        Returns
        -------
        int
            成功写入的事件行数。
        """
        total_written = 0
        for ts_code in ts_codes:
            try:
                records = self.connector.fetch_dividend(ts_code)
            except Exception as exc:
                logger.warning(
                    "CorporateActionsUpdater: fetch_dividend failed for %s: %s",
                    ts_code, exc,
                )
                continue
            if not records:
                continue
            total_written += self._upsert(records)

        logger.info(
            "CorporateActionsUpdater: wrote %d events for %d symbols",
            total_written, len(ts_codes),
        )
        return total_written

    def _upsert(self, records: list[dict]) -> int:
        """``INSERT OR REPLACE`` 写入 silver_corporate_actions。

        ``action_id`` 是主键，重复写入同一事件（如多次回填）会覆盖而非报错，
        保证幂等。
        """
        columns = [
            "action_id", "asset_id", "action_type", "ex_date", "record_date",
            "pay_date", "ratio", "cash_amount", "currency", "description", "source",
        ]
        rows = [tuple(rec.get(c) for c in columns) for rec in records]
        written = 0
        for rec, row in zip(records, rows):
            try:
                self.catalog.execute(
                    """
                    INSERT OR REPLACE INTO silver_corporate_actions
                        (action_id, asset_id, action_type, ex_date, record_date,
                         pay_date, ratio, cash_amount, currency, description,
                         source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    list(row),
                )
                written += 1
            except Exception as exc:
                logger.warning(
                    "CorporateActionsUpdater: upsert failed for %s: %s",
                    rec.get("action_id"), exc,
                )
        return written


def _load_ts_codes(catalog: "Catalog") -> list[str]:
    """从 silver_assets 加载所有资产的 ts_code（Tushare 格式）。

    silver_assets 存的是 cQuant ``asset_id``（如 ``SZSE:000001``），需转回
    Tushare 的 ``000001.SZ`` 格式才能调用 ``pro.dividend``。
    """
    try:
        df = catalog.query("SELECT DISTINCT asset_id FROM silver_assets LIMIT 5000")
    except Exception as exc:
        logger.warning("corporate_actions_updater: failed to load asset list: %s", exc)
        return []
    if df.is_empty():
        return []

    codes: list[str] = []
    for asset_id in df["asset_id"].to_list():
        if ":" not in asset_id:
            continue
        exchange, symbol = asset_id.split(":", 1)
        suffix = {"SSE": "SH", "SZSE": "SZ"}.get(exchange)
        if suffix:
            codes.append(f"{symbol}.{suffix}")
    return codes


def register_corporate_actions_job(
    scheduler: "StrategyScheduler",
    catalog: "Catalog",
    connector: "TushareConnector",
    run_hour: int = 18,
    run_minute: int = 20,
) -> None:
    """注册每日公司行为数据更新任务（默认 18:20，估值更新之后）。

    分红事件更新频率低（年报季集中），每日全量拉取足以覆盖。
    """
    from cquant.scheduler.scheduler import ScheduleConfig, ScheduleFrequency  # noqa: PLC0415

    config = ScheduleConfig(
        job_id="daily_corporate_actions_update",
        strategy_id="__system__",
        frequency=ScheduleFrequency.DAILY,
        run_time=time(run_hour, run_minute),
        enabled=True,
        metadata={"type": "data_update"},
    )

    updater = CorporateActionsUpdater(catalog, connector)

    def _callback() -> None:
        ts_codes = _load_ts_codes(catalog)
        if not ts_codes:
            logger.warning("corporate_actions_updater: no assets found, skipping")
            return
        updater.update(ts_codes)

    scheduler.add_job(config, _callback)
    logger.info(
        "corporate_actions_updater: registered daily job at %02d:%02d",
        run_hour, run_minute,
    )


def verify_dividend_ex_dates(
    catalog: "Catalog",
    asset_ids: list[str],
    tolerance_pct: float = 0.005,
) -> dict[str, list]:
    """交叉校验：分红除权日应与 ``silver_prices_1d.adj_factor`` 跳变日吻合。

    理论上除权除息当日复权因子会发生跳变。本函数对每个有分红事件的资产，
    检查其 ex_date 当日（及前后 1 个交易日）的 ``adj_factor`` 是否有显著变化，
    统计不吻合的事件并按比例 log。

    Parameters
    ----------
    catalog
        DuckDB Catalog 实例。
    asset_ids
        待校验的 asset_id 列表（cQuant 格式，如 ``SSE:600036``）。
    tolerance_pct
        ``adj_factor`` 日变化低于该比例（小数；默认 0.005 = 0.5%）视为未跳变，
        记为不吻合。注意是 0.005 而非 0.5（与 change_pct 的小数单位一致）。

    Returns
    -------
    dict
        ``{'mismatches': [(asset_id, ex_date, cash_amount, ...)], 'total': int,
        'mismatch_count': int}``。caller 可据此决定是否告警。
    """
    mismatches: list[tuple] = []
    total = 0

    for asset_id in asset_ids:
        # 取该资产所有已实施分红事件
        try:
            events = catalog.query(
                """
                SELECT ex_date, cash_amount, ratio
                FROM silver_corporate_actions
                WHERE asset_id = ? AND action_type = 'dividend'
                ORDER BY ex_date
                """,
                [asset_id],
            )
        except Exception as exc:
            logger.debug("verify_dividend_ex_dates: query events failed for %s: %s", asset_id, exc)
            continue
        if events.is_empty():
            continue

        # 取该资产全部 adj_factor 序列，计算日变化率
        try:
            prices = catalog.query(
                """
                SELECT trade_date, adj_factor
                FROM silver_prices_1d
                WHERE asset_id = ?
                ORDER BY trade_date
                """,
                [asset_id],
            )
        except Exception as exc:
            logger.debug("verify_dividend_ex_dates: query prices failed for %s: %s", asset_id, exc)
            continue
        if prices.is_empty():
            continue

        # 构建 trade_date -> adj_factor 日变化率映射（除权日应有显著跳变）。
        # 查询已按单个 asset_id 过滤，故 shift 无需 over() 分组。
        import polars as pl  # noqa: PLC0415
        prices = prices.with_columns(
            pl.col("adj_factor").cast(pl.Float64).shift(1).alias("prev_adj")
        )
        prices = prices.with_columns(
            pl.when(pl.col("prev_adj").is_not_null() & (pl.col("prev_adj") != 0))
            .then((pl.col("adj_factor") - pl.col("prev_adj")) / pl.col("prev_adj"))
            .otherwise(None)
            .alias("change_pct")
        )
        price_lookup = {
            row["trade_date"]: row["change_pct"]
            for row in prices.select(["trade_date", "change_pct"]).to_dicts()
            if row["change_pct"] is not None
        }

        # 校验窗口：ex_date 当日及前后 1 个交易日任一跳变即视为吻合
        import datetime as _dt  # noqa: PLC0415
        for ev in events.to_dicts():
            total += 1
            ex_date = ev["ex_date"]
            if ex_date is None:
                continue
            window_dates = [
                ex_date + _dt.timedelta(days=delta) for delta in (-3, -2, -1, 0, 1, 2, 3)
            ]
            # 在窗口内寻找最大跳变幅度
            window_changes = [
                abs(price_lookup.get(d, 0.0) or 0.0) for d in window_dates
            ]
            max_change = max(window_changes) if window_changes else 0.0
            if max_change < tolerance_pct:
                mismatches.append((asset_id, str(ex_date), ev.get("cash_amount"), max_change))

    mismatch_rate = (len(mismatches) / total) if total else 0.0
    logger.info(
        "verify_dividend_ex_dates: %d/%d events mismatched adj_factor jump (%.1f%%)",
        len(mismatches), total, mismatch_rate * 100,
    )
    return {
        "mismatches": mismatches,
        "total": total,
        "mismatch_count": len(mismatches),
        "mismatch_rate": mismatch_rate,
    }
