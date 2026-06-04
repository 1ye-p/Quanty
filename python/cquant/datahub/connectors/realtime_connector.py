"""cquant.datahub.connectors.realtime_connector — Real-time A-share quote feed.

Fetches live quotes via AKShare's East Money interface.
Provides both one-shot and polling modes for Paper Trading and monitoring.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    """Real-time quote for a single symbol."""
    asset_id: str
    symbol: str
    price: float
    open: float
    high: float
    low: float
    close: float  # Same as price for real-time
    prev_close: float
    volume: int
    amount: float
    bid1: float
    ask1: float
    bid1_vol: int
    ask1_vol: int
    change: float
    change_pct: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "symbol": self.symbol,
            "price": self.price,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "prev_close": self.prev_close,
            "volume": self.volume,
            "amount": self.amount,
            "bid1": self.bid1,
            "ask1": self.ask1,
            "bid1_vol": self.bid1_vol,
            "ask1_vol": self.ask1_vol,
            "change": self.change,
            "change_pct": self.change_pct,
            "timestamp": self.timestamp.isoformat(),
        }


class QuoteFeed:
    """Real-time A-share quote feed via AKShare.

    Usage::

        feed = QuoteFeed()
        quotes = feed.get_quotes(["600036", "000001"])
        for symbol, quote in quotes.items():
            print(f"{symbol}: {quote.price} ({quote.change_pct:+.2f}%)")

        # Polling mode
        feed.subscribe(["600036"], callback=my_callback, interval=5)
    """

    def __init__(self, catalog: Any = None) -> None:
        self._catalog = catalog
        self._polling = False
        self._poll_thread: threading.Thread | None = None

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Fetch real-time quotes for given symbols.

        Args:
            symbols: List of stock codes (e.g. ["600036", "000001"])

        Returns:
            Dict of symbol -> Quote
        """
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError("akshare is not installed. Run: pip install akshare")

        try:
            df_pd = ak.stock_zh_a_spot_em()
        except Exception as exc:
            logger.error("Failed to fetch real-time quotes: %s", exc)
            return {}

        # Build lookup by code
        quotes: dict[str, Quote] = {}
        for _, row in df_pd.iterrows():
            code = str(row.get("代码", ""))
            if code not in symbols:
                continue

            try:
                quote = self._parse_row(code, row)
                quotes[code] = quote
            except Exception as exc:
                logger.warning("Failed to parse quote for %s: %s", code, exc)

        return quotes

    def get_all_quotes(self, limit: int = 50) -> dict[str, Quote]:
        """Fetch real-time quotes for all A-share stocks.

        Args:
            limit: Max number of quotes to return

        Returns:
            Dict of symbol -> Quote
        """
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError("akshare is not installed. Run: pip install akshare")

        try:
            df_pd = ak.stock_zh_a_spot_em()
        except Exception as exc:
            logger.error("Failed to fetch all quotes: %s", exc)
            return {}

        quotes: dict[str, Quote] = {}
        for _, row in df_pd.head(limit).iterrows():
            code = str(row.get("代码", ""))
            try:
                quotes[code] = self._parse_row(code, row)
            except Exception:
                continue

        return quotes

    def subscribe(
        self,
        symbols: list[str],
        callback: Callable[[dict[str, Quote]], None],
        interval: float = 3.0,
    ) -> None:
        """Start polling for real-time quotes.

        Args:
            symbols: Symbols to watch
            callback: Called on each poll with updated quotes
            interval: Poll interval in seconds
        """
        if self._polling:
            logger.warning("Already polling, stop first")
            return

        self._polling = True

        def _poll_loop():
            while self._polling:
                try:
                    quotes = self.get_quotes(symbols)
                    if quotes:
                        callback(quotes)
                except Exception as exc:
                    logger.error("Poll error: %s", exc)
                time.sleep(interval)

        self._poll_thread = threading.Thread(target=_poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info("Started quote polling for %s (interval=%.1fs)", symbols, interval)

    def stop(self) -> None:
        """Stop polling."""
        self._polling = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
            self._poll_thread = None

    def persist_quotes(self, quotes: dict[str, Quote]) -> None:
        """Write quotes to silver_prices_realtime table in DuckDB.

        Args:
            quotes: Dict of symbol -> Quote
        """
        if not self._catalog:
            return

        try:
            rows = [q.to_dict() for q in quotes.values()]
            if not rows:
                return

            df = pl.DataFrame(rows)

            self._catalog.execute("""
                CREATE TABLE IF NOT EXISTS silver_prices_realtime (
                    asset_id VARCHAR,
                    symbol VARCHAR,
                    price DOUBLE,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    prev_close DOUBLE,
                    volume BIGINT,
                    amount DOUBLE,
                    bid1 DOUBLE,
                    ask1 DOUBLE,
                    bid1_vol BIGINT,
                    ask1_vol BIGINT,
                    change DOUBLE,
                    change_pct DOUBLE,
                    timestamp TIMESTAMP
                )
            """)

            self._catalog.execute(
                "INSERT INTO silver_prices_realtime SELECT * FROM df",
            )
            logger.debug("Persisted %d quotes", len(rows))
        except Exception as exc:
            logger.error("Failed to persist quotes: %s", exc)

    def _parse_row(self, code: str, row: Any) -> Quote:
        """Parse a DataFrame row into a Quote."""
        def _safe_float(val: Any, default: float = 0.0) -> float:
            try:
                return float(val) if val is not None and str(val) != "-" else default
            except (ValueError, TypeError):
                return default

        def _safe_int(val: Any, default: int = 0) -> int:
            try:
                return int(float(val)) if val is not None and str(val) != "-" else default
            except (ValueError, TypeError):
                return default

        price = _safe_float(row.get("最新价"))
        prev_close = _safe_float(row.get("昨收"))
        exchange = "SSE" if code.startswith("6") else "SZSE"

        return Quote(
            asset_id=f"{exchange}:{code}",
            symbol=code,
            price=price,
            open=_safe_float(row.get("今开")),
            high=_safe_float(row.get("最高")),
            low=_safe_float(row.get("最低")),
            close=price,
            prev_close=prev_close,
            volume=_safe_int(row.get("成交量")),
            amount=_safe_float(row.get("成交额")),
            bid1=_safe_float(row.get("买一价")),
            ask1=_safe_float(row.get("卖一价")),
            bid1_vol=_safe_int(row.get("买一量")),
            ask1_vol=_safe_int(row.get("卖一量")),
            change=_safe_float(row.get("涨跌额")),
            change_pct=_safe_float(row.get("涨跌幅")),
        )


class RealtimeQuoteConnector:
    """Adapter that wraps QuoteFeed for use with the CLI and API.

    This is NOT a DataConnector subclass (different interface for real-time vs historical).
    """

    def __init__(self, catalog: Any = None) -> None:
        self._feed = QuoteFeed(catalog=catalog)

    @property
    def feed(self) -> QuoteFeed:
        return self._feed

    def get_quote(self, symbol: str) -> Quote | None:
        """Get single quote."""
        quotes = self._feed.get_quotes([symbol])
        return quotes.get(symbol)

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get multiple quotes."""
        return self._feed.get_quotes(symbols)

    def get_market_snapshot(self, limit: int = 20) -> dict[str, Quote]:
        """Get market-wide snapshot."""
        return self._feed.get_all_quotes(limit=limit)
