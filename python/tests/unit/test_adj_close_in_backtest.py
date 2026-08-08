"""Adjusted-close / OHLC correctness tests for the backtest price helper.

Covers :func:`cquant.backtest_vector.prices.adjusted_ohlc_sql` — the single
canonical SQL fragment shared by the backtest path and factor materialization
path so the two always agree on the adjustment convention.

8 tests:
  1. Ex-dividend NAV continuity: adjusted close stays continuous across the
     ex-div date even though raw close drops and adj_factor changes.
  2. OHLC consistent scaling: when raw close == high (limit-up), the adjusted
     close == adjusted high (uniform scaling across OHLC).
  3. adj_factor == 1 identity: adjusted OHLC equals raw OHLC.
  4. NULL adj_close fallback: COALESCE(adj_close, close * adj_factor) falls
     back to close × adj_factor when adj_close is NULL.
  5. volume/amount are NOT adjusted (kept raw).
  6. Dividend-stock adjusted return exceeds raw-close return.
  7. Factor momentum (ret_20d) computed on adjusted prices has no ex-div jump
     — validated by checking the adjusted close is smooth across the ex-div day.
  8. raw_close = adjusted close / adj_factor approximates the raw close
     (the inverse mapping the fill_simulator relies on).

All tests use an in-memory DuckDB (no real data files).
"""
from __future__ import annotations

import duckdb
import pytest

from cquant.backtest_vector.prices import adjusted_ohlc_sql


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _con() -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB connection with a minimal silver_prices_1d table."""
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE silver_prices_1d (
            asset_id      VARCHAR,
            trade_date    DATE,
            open          DOUBLE,
            high          DOUBLE,
            low           DOUBLE,
            close         DOUBLE,
            volume        DOUBLE,
            amount        DOUBLE,
            adj_factor    DOUBLE DEFAULT 1,
            adj_close     DOUBLE,
            is_suspended  BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (asset_id, trade_date)
        )
        """
    )
    return con


def _insert(con, rows):
    """Insert synthetic rows into silver_prices_1d.

    Each row is a dict with keys: asset_id, trade_date, open, high, low,
    close, volume, amount, adj_factor, adj_close (optional), is_suspended (optional).
    """
    for r in rows:
        con.execute(
            """
            INSERT INTO silver_prices_1d
                (asset_id, trade_date, open, high, low, close,
                 volume, amount, adj_factor, adj_close, is_suspended)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                r["asset_id"],
                r["trade_date"],
                r["open"],
                r["high"],
                r["low"],
                r["close"],
                r["volume"],
                r["amount"],
                r.get("adj_factor", 1.0),
                r.get("adj_close"),
                r.get("is_suspended", False),
            ],
        )


def _adj(con):
    """Execute adjusted_ohlc_sql() and return rows ordered by trade_date."""
    return con.execute(
        adjusted_ohlc_sql(table="silver_prices_1d") + " ORDER BY trade_date"
    ).fetchall()


# ---------------------------------------------------------------------------
# Test 1 — Ex-dividend NAV continuity
# ---------------------------------------------------------------------------

class TestExDividendNoNavDrop:
    """On the ex-dividend day the raw close drops and adj_factor rises, but the
    fully-adjusted close must remain continuous (no NAV jump)."""

    def test_ex_dividend_no_nav_drop(self):
        con = _con()
        # 5% cash dividend. Pre-ex-div: raw close=10.00, adj_factor=1.10
        # → adjusted close = 11.00. Ex-div: raw close drops to 9.50 (≈ 10 − 0.50);
        # the same real value maps to 9.50 × 1.1578947 ≈ 11.00 after the factor
        # rises. We deliberately leave adj_close NULL on the ex-div day so the
        # fallback path (close × adj_factor) is the one that produces continuity.
        _insert(con, [
            {"asset_id": "SSE:600036", "trade_date": "2024-06-10",
             "open": 10.00, "high": 10.10, "low": 9.95, "close": 10.00,
             "volume": 1e6, "amount": 1e7, "adj_factor": 1.10,
             "adj_close": 11.00},
            {"asset_id": "SSE:600036", "trade_date": "2024-06-11",
             "open": 9.50, "high": 9.55, "low": 9.45, "close": 9.50,
             "volume": 1e6, "amount": 9.5e6, "adj_factor": 11.00 / 9.50,
             "adj_close": None},
        ])

        rows = _adj(con)
        # Column order: asset_id(0), trade_date(1), open(2), high(3), low(4),
        # close(5), volume(6), amount(7), adj_factor(8).
        adj_close_pre = rows[0][5]
        adj_close_post = rows[1][5]  # NULL → fallback 9.50 × (11.00/9.50) = 11.00

        # Raw close dropped 5% — adjusted close must NOT.
        assert abs(adj_close_pre - adj_close_post) < 1e-3
        assert adj_close_pre == pytest.approx(11.00)
        assert adj_close_post == pytest.approx(11.00)


# ---------------------------------------------------------------------------
# Test 2 — OHLC consistent scaling
# ---------------------------------------------------------------------------

class TestOhlcConsistentScaling:
    """When raw close == high (limit-up), adjusted close must == adjusted high —
    proving the same adj_factor is applied uniformly across OHLC."""

    def test_ohlc_consistent_scaling(self):
        con = _con()
        _insert(con, [
            {"asset_id": "SZSE:000001", "trade_date": "2024-03-01",
             "open": 10.0, "high": 11.0, "low": 9.9, "close": 11.0,
             "volume": 5e5, "amount": 5.5e6, "adj_factor": 1.2,
             "adj_close": 13.2},
        ])

        rows = _adj(con)
        _, _, adj_open, adj_high, adj_low, adj_close = rows[0][:6]

        # Uniform scaling: raw close == raw high (11.0) → adj close == adj high.
        assert abs(adj_close - adj_high) < 1e-9
        # Spot-check the factor applies to all four bars.
        assert abs(adj_open - 10.0 * 1.2) < 1e-9
        assert abs(adj_low - 9.9 * 1.2) < 1e-9
        assert abs(adj_high - 11.0 * 1.2) < 1e-9


# ---------------------------------------------------------------------------
# Test 3 — adj_factor == 1 identity
# ---------------------------------------------------------------------------

class TestNoAdjFactorUnchanged:
    """With adj_factor == 1 the adjusted OHLC must equal the raw OHLC."""

    def test_no_adj_factor_unchanged(self):
        con = _con()
        _insert(con, [
            {"asset_id": "SSE:600519", "trade_date": "2024-01-02",
             "open": 1680.0, "high": 1700.0, "low": 1675.0, "close": 1695.0,
             "volume": 3e4, "amount": 5e7, "adj_factor": 1.0, "adj_close": None},
        ])

        rows = _adj(con)
        _, _, adj_open, adj_high, adj_low, adj_close = rows[0][:6]

        assert adj_open == pytest.approx(1680.0)
        assert adj_high == pytest.approx(1700.0)
        assert adj_low == pytest.approx(1675.0)
        # adj_close NULL → fallback close * 1.0 == close.
        assert adj_close == pytest.approx(1695.0)


# ---------------------------------------------------------------------------
# Test 4 — NULL adj_close fallback
# ---------------------------------------------------------------------------

class TestAdjCloseNullFallback:
    """When adj_close is NULL, close must fall back to close × adj_factor."""

    def test_adj_close_null_fallback(self):
        con = _con()
        _insert(con, [
            {"asset_id": "SSE:600036", "trade_date": "2024-04-01",
             "open": 12.0, "high": 12.5, "low": 11.8, "close": 12.2,
             "volume": 1e6, "amount": 1.22e7, "adj_factor": 1.5, "adj_close": None},
            {"asset_id": "SSE:600036", "trade_date": "2024-04-02",
             "open": 12.1, "high": 12.6, "low": 11.9, "close": 12.3,
             "volume": 1e6, "amount": 1.23e7, "adj_factor": 1.5, "adj_close": 18.45},
        ])

        rows = _adj(con)
        # Day 1: NULL → fallback 12.2 * 1.5 == 18.3.
        assert rows[0][5] == pytest.approx(12.2 * 1.5)
        # Day 2: adj_close present → COALESCE returns adj_close directly (18.45),
        # NOT 12.3 * 1.5 == 18.45 (coincidentally equal here, so use a distinct
        # value to prove COALESCE prefers adj_close).
        assert rows[1][5] == pytest.approx(18.45)

    def test_adj_close_preferred_when_present(self):
        """COALESCE must prefer adj_close even when it differs from close*adj_factor."""
        con = _con()
        _insert(con, [
            {"asset_id": "SSE:600000", "trade_date": "2024-05-01",
             "open": 8.0, "high": 8.2, "low": 7.9, "close": 8.1,
             "volume": 2e6, "amount": 1.6e7, "adj_factor": 1.3,
             "adj_close": 99.9},  # deliberately distinct
        ])
        rows = _adj(con)
        assert rows[0][5] == pytest.approx(99.9)


# ---------------------------------------------------------------------------
# Test 5 — volume / amount not adjusted
# ---------------------------------------------------------------------------

class TestVolumeAmountNotAdjusted:
    """volume and amount must be returned raw (not multiplied by adj_factor)."""

    def test_volume_amount_not_adjusted(self):
        con = _con()
        _insert(con, [
            {"asset_id": "SSE:600036", "trade_date": "2024-02-01",
             "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.1,
             "volume": 1234567.0, "amount": 12457126.7, "adj_factor": 2.5,
             "adj_close": 25.25},
        ])

        rows = _adj(con)
        _, _, _, _, _, _, volume, amount = rows[0][:8]
        assert volume == pytest.approx(1234567.0)
        assert amount == pytest.approx(12457126.7)


# ---------------------------------------------------------------------------
# Test 6 — Dividend stock higher adjusted return
# ---------------------------------------------------------------------------

class TestDividendStockHigherReturn:
    """For a dividend-paying stock (adj_factor > 1), the adjusted-close return
    over a period must exceed the raw-close return (dividends add to total return)."""

    def test_dividend_stock_higher_return(self):
        con = _con()
        # The stock paid a dividend mid-window, so the adjustment factor rises
        # across the period. The starting price is back-adjusted by a smaller
        # factor than the ending price → adjusted return strictly exceeds the
        # raw-close return (the dividend is folded into the price series).
        _insert(con, [
            {"asset_id": "SSE:600036", "trade_date": "2024-01-02",
             "open": 10.00, "high": 10.05, "low": 9.95, "close": 10.00,
             "volume": 1e6, "amount": 1e7, "adj_factor": 1.10,
             "adj_close": None},  # → 10.00 × 1.10 = 11.00
            {"asset_id": "SSE:600036", "trade_date": "2024-06-28",
             "open": 10.05, "high": 10.15, "low": 10.00, "close": 10.10,
             "volume": 1e6, "amount": 1.01e7, "adj_factor": 1.20,
             "adj_close": None},  # → 10.10 × 1.20 = 12.12
        ])

        rows = _adj(con)
        adj0, adj1 = rows[0][5], rows[1][5]
        adj_ret = adj1 / adj0 - 1.0  # 12.12 / 11.00 − 1 ≈ 10.18%

        # Raw return from the raw close values (1%).
        raw_ret = 10.10 / 10.00 - 1.0

        assert adj_ret > raw_ret
        assert adj_ret == pytest.approx(12.12 / 11.00 - 1.0)


# ---------------------------------------------------------------------------
# Test 7 — Factor momentum: no ex-div jump (adjusted close smooth)
# ---------------------------------------------------------------------------

class TestFactorMomentumNoExDivJump:
    """A momentum factor (ret_20d) computed on adjusted prices must not see a
    spurious jump on the ex-dividend day. We assert the precondition the factor
    relies on: the adjusted close is smooth across the ex-div boundary, so a
    20-day return window straddling the ex-div day is well-defined."""

    def test_factor_momentum_no_ex_div_jump(self):
        con = _con()
        # 5 trading days; ex-div on day 3. Raw close drops 0.50 on the ex-div
        # day but adj_factor rises so the adjusted close stays ≈ 11.00.
        _insert(con, [
            {"asset_id": "SSE:600036", "trade_date": "2024-06-03",
             "open": 10.0, "high": 10.1, "low": 9.9, "close": 10.0,
             "volume": 1e6, "amount": 1e7, "adj_factor": 1.10, "adj_close": 11.00},
            {"asset_id": "SSE:600036", "trade_date": "2024-06-04",
             "open": 10.0, "high": 10.1, "low": 9.9, "close": 10.0,
             "volume": 1e6, "amount": 1e7, "adj_factor": 1.10, "adj_close": 11.00},
            {"asset_id": "SSE:600036", "trade_date": "2024-06-05",  # ex-div day
             "open": 9.5, "high": 9.6, "low": 9.4, "close": 9.5,
             "volume": 1e6, "amount": 9.5e6, "adj_factor": 1.1578947,
             "adj_close": 11.00},
            {"asset_id": "SSE:600036", "trade_date": "2024-06-06",
             "open": 9.5, "high": 9.6, "low": 9.4, "close": 9.5,
             "volume": 1e6, "amount": 9.5e6, "adj_factor": 1.1578947,
             "adj_close": 11.00},
            {"asset_id": "SSE:600036", "trade_date": "2024-06-07",
             "open": 9.5, "high": 9.6, "low": 9.4, "close": 9.5,
             "volume": 1e6, "amount": 9.5e6, "adj_factor": 1.1578947,
             "adj_close": 11.00},
        ])

        rows = _adj(con)
        adj_closes = [r[5] for r in rows]

        # All adjusted closes are equal → any-window return is exactly 0,
        # no ex-div jump leaks into the momentum signal.
        max_jump = max(abs(adj_closes[i] - adj_closes[i - 1])
                       for i in range(1, len(adj_closes)))
        assert max_jump < 1e-3

        # A 2-day return straddling the ex-div day (day 2 → day 4) is ~0,
        # whereas the same window on raw close would show a -5% drop.
        ret_straddle = adj_closes[3] / adj_closes[1] - 1.0
        assert abs(ret_straddle) < 1e-3


# ---------------------------------------------------------------------------
# Test 8 — raw_close display (inverse mapping)
# ---------------------------------------------------------------------------

class TestFactorRawCloseDisplay:
    """raw_close = adjusted close / adj_factor must approximate the raw close —
    the inverse mapping the fill_simulator relies on (it back-fills
    raw_close = price / adj_factor)."""

    def test_factor_raw_close_display(self):
        con = _con()
        _insert(con, [
            {"asset_id": "SSE:600036", "trade_date": "2024-07-01",
             "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.1,
             "volume": 1e6, "amount": 1.01e7, "adj_factor": 1.30, "adj_close": 13.13},
            {"asset_id": "SSE:600036", "trade_date": "2024-07-02",
             "open": 10.1, "high": 10.3, "low": 9.9, "close": 10.2,
             "volume": 1e6, "amount": 1.02e7, "adj_factor": 1.30, "adj_close": None},
        ])

        rows = _adj(con)
        for idx, raw_close in enumerate((10.1, 10.2)):
            adj_close = rows[idx][5]
            adj_factor = rows[idx][8]  # adj_factor passthrough column
            # raw_close ≈ adj_close / adj_factor
            assert adj_close / adj_factor == pytest.approx(raw_close, rel=1e-3)
