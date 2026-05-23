"""cquant.ml_lab.labels — ML label construction from price data.

Provides utilities to build supervised-learning target labels:
- Forward return labels (simple look-ahead returns)
- Triple barrier labels (barrier-based classification)
"""

from __future__ import annotations

import polars as pl


def forward_return_labels(
    prices: pl.DataFrame,
    periods: int = 5,
    price_col: str = "close",
    output_col: str | None = None,
) -> pl.DataFrame:
    """Compute forward-period return labels.

    For each row: label = close[t + periods] / close[t] - 1.
    Last ``periods`` rows per asset will have null labels.

    Parameters
    ----------
    prices
        DataFrame with at least ``asset_id``, ``trade_date``, and ``price_col``.
    periods
        Number of forward periods for the return horizon.
    price_col
        Column name containing prices (default ``"close"``).
    output_col
        Name of the output label column.  Defaults to ``"ret_{periods}d"``.

    Returns
    -------
    pl.DataFrame
        Columns: ``[asset_id, trade_date, <output_col>]``.
    """
    if output_col is None:
        output_col = f"ret_{periods}d"

    return (
        prices.sort("asset_id", "trade_date")
        .with_columns(
            pl.col(price_col)
            .shift(-periods)
            .over("asset_id")
            .alias("__future_close"),
        )
        .with_columns(
            ((pl.col("__future_close") / pl.col(price_col)) - 1.0)
            .clip(lower_bound=-0.5, upper_bound=0.5)
            .alias(output_col)
        )
        .select("asset_id", "trade_date", output_col)
    )


def triple_barrier_labels(
    prices: pl.DataFrame,
    upper_pct: float = 0.05,
    lower_pct: float = -0.05,
    max_periods: int = 10,
    price_col: str = "close",
) -> pl.DataFrame:
    """Compute Triple Barrier labels.

    For each row, look forward up to ``max_periods`` future prices:

    - If the price hits the upper barrier first: label = ``1.0``
    - If the price hits the lower barrier first: label = ``-1.0``
    - If neither barrier is hit within ``max_periods``: label = ``0.0``

    Parameters
    ----------
    prices
        DataFrame with at least ``asset_id``, ``trade_date``, and ``price_col``.
        Must be sorted or will be sorted internally by (``asset_id``, ``trade_date``).
    upper_pct
        Upper barrier as a fraction of entry price (e.g. 0.05 = +5 %).
    lower_pct
        Lower barrier as a fraction of entry price (e.g. -0.05 = -5 %).
    max_periods
        Maximum number of forward periods to look.
    price_col
        Column name containing prices (default ``"close"``).

    Returns
    -------
    pl.DataFrame
        Columns: ``[asset_id, trade_date, tb_label]``.
        Rows with insufficient future data have ``tb_label`` as null.
    """
    sorted_prices = prices.sort("asset_id", "trade_date")

    # Collect per-asset results
    results: list[pl.DataFrame] = []

    for asset_id, group in sorted_prices.group_by("asset_id", maintain_order=True):
        close_prices = group[price_col].to_list()
        dates = group["trade_date"].to_list()
        n = len(close_prices)
        labels: list[float | None] = []

        for i in range(n):
            entry = close_prices[i]
            upper = entry * (1.0 + upper_pct)
            lower = entry * (1.0 + lower_pct)
            end = i + 1 + max_periods

            # Not enough future data to fill the observation window
            if end > n:
                labels.append(None)
                continue

            label: float = 0.0
            for j in range(i + 1, end):
                price = close_prices[j]
                if price >= upper:
                    label = 1.0
                    break
                if price <= lower:
                    label = -1.0
                    break

            labels.append(label)

        asset_df = pl.DataFrame({
            "asset_id": [asset_id] * n,
            "trade_date": dates,
            "tb_label": labels,
        })
        results.append(asset_df)

    return pl.concat(results) if results else pl.DataFrame(
        schema={"asset_id": pl.Utf8, "trade_date": pl.Int64, "tb_label": pl.Float64}
    )
