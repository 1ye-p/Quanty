"""AKShare A股历史行情 MCP 工具。"""

from __future__ import annotations

import json
from datetime import datetime

try:
    import akshare as ak  # noqa: F401
except ImportError:
    ak = None  # type: ignore[assignment]


def get_stock_history(
    symbol: str,
    start_date: str,
    end_date: str,
    period: str = "daily",
    adjust: str = "hfq",
) -> str:
    """获取 A 股历史 OHLCV 行情数据。

    Args:
        symbol: A 股代码，6 位数字（如 '600036'，不含市场前缀）。
        start_date: 开始日期，格式 YYYYMMDD（如 '20240101'）。
        end_date: 结束日期，格式 YYYYMMDD（如 '20241231'）。
        period: 周期，'daily'（日）/ 'weekly'（周）/ 'monthly'（月），默认 daily。
        adjust: 复权方式，'hfq'（后复权）/ 'qfq'（前复权）/ ''（不复权），默认 hfq。

    Returns:
        JSON 字符串，包含 records 列表或 error 字段。
        每条记录：{date, open, high, low, close, volume, amount, pct_change}
    """
    # 校验输入
    symbol = symbol.strip()
    if not symbol.isdigit() or len(symbol) != 6:
        return json.dumps({"error": f"Invalid symbol '{symbol}'. Expected 6-digit A-share code."})

    try:
        datetime.strptime(start_date, "%Y%m%d")
        datetime.strptime(end_date, "%Y%m%d")
    except ValueError:
        return json.dumps({"error": "start_date and end_date must be YYYYMMDD format."})

    if period not in {"daily", "weekly", "monthly"}:
        return json.dumps({"error": f"period must be 'daily', 'weekly', or 'monthly'. Got '{period}'."})

    if ak is None:
        return json.dumps({"error": "akshare is not installed. Run: pip install akshare"})

    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except Exception as exc:
        return json.dumps({"error": f"AKShare fetch failed: {exc}"})

    if df is None or df.empty:
        return json.dumps({"error": f"No data returned for symbol={symbol} [{start_date}, {end_date}]."})

    # 标准化列名（AKShare 返回中文列名）
    col_map = {
        "日期": "date", "开盘": "open", "最高": "high", "收盘": "close",
        "最低": "low", "成交量": "volume", "成交额": "amount",
        "涨跌幅": "pct_change", "涨跌额": "change",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # 仅返回标准字段
    keep_cols = [c for c in ["date", "open", "high", "low", "close", "volume", "amount", "pct_change"] if c in df.columns]
    records = df[keep_cols].to_dict(orient="records")

    return json.dumps({
        "symbol": symbol,
        "period": period,
        "adjust": adjust,
        "count": len(records),
        "records": records,
    }, default=str, ensure_ascii=False)
