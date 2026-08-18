"""cquant.backtest_vector.prices — Shared adjusted-OHLC SQL helper.

Provides :func:`adjusted_ohlc_sql`, a single canonical SELECT fragment that
produces fully-adjusted OHLC prices (``OHLC × adj_factor``) while keeping
``volume`` / ``amount`` raw. It is shared by both the backtest path and the
factor materialization path so that the two always agree on the adjustment
convention.

Adjustment rules:
- ``open/high/low`` → ``<col> * adj_factor`` (forward-adjusted, backtest-safe).
- ``close`` → ``COALESCE(adj_close, close * adj_factor)``: prefer the vendor
  ``adj_close`` when present, fall back to ``close × adj_factor`` otherwise.
- ``volume`` / ``amount`` are intentionally left unadjusted (share/turnover,
  not cash value).
- ``adj_factor`` itself and ``is_suspended`` are passed through for downstream
  consumers (e.g. tradability filtering).

Callers are expected to append their own ``WHERE`` / ``ORDER BY`` clauses and a
trailing ``;`` when needed; the fragment deliberately returns **without** a
terminator so it can be embedded in larger queries.
"""

from __future__ import annotations


def adjusted_ohlc_sql(table: str = "silver_prices_1d") -> str:
    """Return a fully-adjusted OHLC SELECT fragment for ``table``.

    OHLC is multiplied by ``adj_factor`` (forward-adjusted); ``close`` prefers
    the vendor ``adj_close`` and falls back to ``close × adj_factor`` when
    ``adj_close`` is NULL. ``volume``/``amount`` are returned raw.

    Parameters
    ----------
    table:
        Source table name. Defaults to ``"silver_prices_1d"``. The value is
        interpolated directly into the SQL, so only pass trusted identifiers.

    Returns
    -------
    str
        A SQL SELECT fragment (no trailing ``;``) selecting ``asset_id``,
        ``trade_date``, adjusted ``open/high/low/close``, raw ``volume`` and
        ``amount``, plus ``adj_factor`` and ``is_suspended``.
    """
    return f"""
        SELECT asset_id, trade_date,
            CAST(open AS DOUBLE) * CAST(adj_factor AS DOUBLE)               AS open,
            CAST(high AS DOUBLE) * CAST(adj_factor AS DOUBLE)               AS high,
            CAST(low  AS DOUBLE) * CAST(adj_factor AS DOUBLE)               AS low,
            COALESCE(adj_close, CAST(close AS DOUBLE) * CAST(adj_factor AS DOUBLE)) AS close,
            volume,
            amount,
            adj_factor, is_suspended
        FROM {table}
    """
