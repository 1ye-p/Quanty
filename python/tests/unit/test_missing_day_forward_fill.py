"""Unit tests for missing-day forward-fill + delisting handling in run.py.

Covers P2-1 (HARD-1): when an asset skips a trade date, the price matrix and
FillSimulator previously saw a 0.0 / NULL price -> no trade. Forward-filling
``close`` per asset (after reindexing onto the union of trade dates) recovers
those gaps for the price matrix and FillSimulator in one place, while keeping
first-day NULLs NULL and not tail-filling delisted assets.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cquant.backtest_vector.run import _forward_fill_long_prices, _handle_delisting


def test_missing_day_forward_fill() -> None:
    """An internal gap (asset A missing 1/3) is filled from the prior close."""
    prices = pl.DataFrame(
        {
            "asset_id": ["A", "A", "A", "B", "B", "B", "B"],
            "trade_date": [
                date(2024, 1, 2),
                date(2024, 1, 4),
                date(2024, 1, 5),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 5),
            ],
            "close": [10.0, 11.0, 12.0, 20.0, 21.0, 22.0, 23.0],
        }
    )

    filled = _forward_fill_long_prices(prices)

    # Asset A now has a 1/3 row (reindexed from the union of trade dates) whose
    # close equals the 1/2 close (carried forward).
    a_jan3 = filled.filter(
        (pl.col("asset_id") == "A") & (pl.col("trade_date") == date(2024, 1, 3))
    )
    assert a_jan3.height == 1, "Asset A should have a reindexed 1/3 row"
    assert a_jan3["close"].item() == 10.0, "A 1/3 close must equal A 1/2 close (10.0)"

    # Existing real values are unchanged.
    a_jan4 = filled.filter(
        (pl.col("asset_id") == "A") & (pl.col("trade_date") == date(2024, 1, 4))
    )["close"].item()
    assert a_jan4 == 11.0


def test_first_day_null_not_filled() -> None:
    """A leading NULL close (asset B first day) is NOT back-filled."""
    prices = pl.DataFrame(
        {
            "asset_id": ["B", "B", "B"],
            "trade_date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            "close": [None, 21.0, 22.0],
        }
    )

    filled = _forward_fill_long_prices(prices)

    b_jan2 = filled.filter(
        (pl.col("asset_id") == "B") & (pl.col("trade_date") == date(2024, 1, 2))
    )
    assert b_jan2.height == 1, "Asset B 1/2 row must be retained"
    assert (
        b_jan2["close"].item() is None
    ), "First-day NULL must NOT be back-filled (stays None)"

    # Later rows are unaffected.
    b_jan3 = filled.filter(
        (pl.col("asset_id") == "B") & (pl.col("trade_date") == date(2024, 1, 3))
    )["close"].item()
    assert b_jan3 == 21.0


def test_delisted_not_tail_filled() -> None:
    """A delisted asset (last data 12/15) is not tail-filled to 12/31."""
    prices = pl.DataFrame(
        {
            "asset_id": [
                "C", "C", "C",
                "D", "D", "D", "D",
            ],
            "trade_date": [
                date(2024, 12, 10),
                date(2024, 12, 13),
                date(2024, 12, 15),
                date(2024, 12, 10),
                date(2024, 12, 15),
                date(2024, 12, 20),
                date(2024, 12, 31),
            ],
            "close": [1.0, 2.0, 3.0, 7.0, 8.0, 9.0, 10.0],
        }
    )

    filled = _forward_fill_long_prices(prices)
    result = _handle_delisting(filled, end_date=date(2024, 12, 31))

    # Delisted C: no rows after its last valid date (12/15). The 12/16-31 window
    # must NOT be filled with carried-forward close values.
    c_dates = result.filter(pl.col("asset_id") == "C")["trade_date"].to_list()
    assert max(c_dates) == date(2024, 12, 15), (
        f"Delisted C must stop at 12/15, got max {max(c_dates)}"
    )
    # No synthetic close value should appear beyond 12/15 for C.
    assert date(2024, 12, 20) not in c_dates
    assert date(2024, 12, 31) not in c_dates

    # Live D continues through the backtest end (12/31).
    d_dates = result.filter(pl.col("asset_id") == "D")["trade_date"].to_list()
    assert max(d_dates) == date(2024, 12, 31), "Live D must reach 12/31"
