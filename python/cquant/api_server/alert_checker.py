"""alert_checker — 告警规则检查引擎。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

RULE_TYPES = {
    "data_stale":     "数据缺失超过 N 天",
    "factor_ic_low":  "因子 IC 绝对值持续低于阈值",
    "pnl_drawdown":   "策略 P&L 回撤超过阈值",
    "risk_breach":    "风控策略拦截交易",
}


_alert_tables_ensured = False


def _ensure_tables(catalog) -> None:
    global _alert_tables_ensured
    if _alert_tables_ensured:
        return
    try:
        catalog.execute("""
            CREATE TABLE IF NOT EXISTS meta_alert_rules (
                rule_id      VARCHAR PRIMARY KEY,
                rule_type    VARCHAR NOT NULL,
                params_json  VARCHAR NOT NULL,
                enabled      BOOLEAN DEFAULT TRUE,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        catalog.execute("""
            CREATE TABLE IF NOT EXISTS meta_alert_history (
                alert_id     VARCHAR PRIMARY KEY,
                rule_id      VARCHAR NOT NULL,
                rule_type    VARCHAR NOT NULL,
                severity     VARCHAR DEFAULT 'warning',
                message      VARCHAR NOT NULL,
                triggered_at TIMESTAMP NOT NULL,
                read         BOOLEAN DEFAULT FALSE
            )
        """)
        _alert_tables_ensured = True
    except Exception as exc:
        logger.debug("_ensure_tables: %s", exc)


def _save_alert(catalog, rule_id: str, rule_type: str, message: str, severity: str = "warning") -> None:
    alert_id = f"al_{uuid.uuid4().hex[:10]}"
    catalog.execute(
        "INSERT INTO meta_alert_history (alert_id, rule_id, rule_type, severity, message, triggered_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [alert_id, rule_id, rule_type, severity, message,
         datetime.now(tz=timezone.utc).isoformat()],
    )


def check_data_stale(catalog, rule_id: str, params: dict) -> bool:
    """检查数据是否超过 N 天未更新。"""
    max_days = int(params.get("max_days", 2))
    try:
        df = catalog.query(
            "SELECT MAX(trade_date) as d FROM silver_prices_1d"
        )
        if df.is_empty() or df["d"][0] is None:
            _save_alert(catalog, rule_id, "data_stale", "无可用行情数据", severity="warning")
            return True
        from datetime import date
        days = (date.today() - df["d"][0]).days
        if days > max_days:
            _save_alert(catalog, rule_id, "data_stale",
                        f"行情数据已 {days} 天未更新（最新：{df['d'][0]}，阈值：{max_days}天）",
                        severity="warning")
            return True
    except Exception as e:
        logger.warning("check_data_stale failed: %s", e)
    return False


def check_factor_ic_low(catalog, rule_id: str, params: dict) -> bool:
    """检查因子 IC 是否持续低于阈值。"""
    factor_name = params.get("factor_name", "")
    threshold = float(params.get("threshold", 0.02))
    window_days = int(params.get("window_days", 20))
    if not factor_name:
        return False
    try:
        df = catalog.query(
            "SELECT mean_ic FROM gold_factor_ic_summary "
            "WHERE factor_name = ? "
            "  AND computed_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 DAY') "
            "ORDER BY computed_at DESC LIMIT 1",
            [factor_name, window_days],
        )
        if df.is_empty():
            return False
        ic = float(df["mean_ic"][0])
        if abs(ic) < threshold:
            _save_alert(catalog, rule_id, "factor_ic_low",
                        f"因子 {factor_name} IC 绝对值 {abs(ic):.4f} 低于阈值 {threshold}（近{window_days}日）",
                        severity="warning")
            return True
    except Exception as e:
        logger.warning("check_factor_ic_low failed: %s", e)
    return False


def check_pnl_drawdown(catalog, rule_id: str, params: dict) -> bool:
    """检查策略最大回撤是否超过阈值。"""
    strategy_id = params.get("strategy_id", "")
    threshold_pct = float(params.get("threshold_pct", 10.0)) / 100
    if not strategy_id:
        return False
    try:
        # Anchor to the single most recently completed run to avoid mixing history
        df = catalog.query(
            "SELECT MAX(ABS(rs.drawdown)) as max_dd "
            "FROM gold_risk_snapshots rs "
            "WHERE rs.run_id = ("
            "  SELECT run_id FROM gold_backtest_runs "
            "  WHERE strategy_id = ? AND status = 'completed' "
            "  ORDER BY completed_at DESC LIMIT 1"
            ")",
            [strategy_id],
        )
        if df.is_empty() or df["max_dd"][0] is None:
            return False
        max_dd = float(df["max_dd"][0])  # ABS already applied in SQL
        if max_dd > threshold_pct:
            severity = "critical" if max_dd > 0.10 else "warning"
            _save_alert(catalog, rule_id, "pnl_drawdown",
                        f"策略 {strategy_id} 最大回撤 {max_dd*100:.2f}% 超过阈值 {threshold_pct*100:.2f}%",
                        severity=severity)
            return True
    except Exception as e:
        logger.warning("check_pnl_drawdown failed: %s", e)
    return False


CHECKERS = {
    "data_stale":    check_data_stale,
    "factor_ic_low": check_factor_ic_low,
    "pnl_drawdown":  check_pnl_drawdown,
}


def run_all_checks(catalog) -> int:
    """运行所有启用的告警规则，返回触发数量。"""
    _ensure_tables(catalog)
    rules_df = catalog.query(
        "SELECT rule_id, rule_type, params_json FROM meta_alert_rules WHERE enabled = TRUE"
    )
    if rules_df.is_empty():
        return 0

    triggered = 0
    for row in rules_df.to_dicts():
        try:
            params = json.loads(row["params_json"])
            checker = CHECKERS.get(row["rule_type"])
            if checker and checker(catalog, row["rule_id"], params):
                triggered += 1
        except Exception as e:
            logger.warning("Alert check failed for %s: %s", row["rule_id"], e)
    return triggered
