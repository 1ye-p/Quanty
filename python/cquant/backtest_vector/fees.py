"""cquant.backtest_vector.fees — Net-of-fee return model (P3-3).

Hedge-fund-style fee application layered *on top of* the gross portfolio
return series produced by the engine. The fee model deliberately does NOT
touch :class:`CostModel` / :class:`FillSimulator` — those model per-fill
transaction costs (commission, stamp duty, slippage, market impact).
Management and performance fees are fund-level charges applied to NAV, so
they belong here.

Two fee components are supported:

* **Management fee** — an annualised charge deducted daily
  (``mgmt_fee_annual / 252``). Applied unconditionally to the gross NAV.
* **Performance fee** — a fraction (``perf_fee``) of *excess* return over a
  ``hurdle``. Two accrual conventions:

  - ``use_hwm=True`` (high-water-mark, the hedge-fund standard): the fee is
    only charged when the current NAV exceeds its all-time peak, and only on
    the gain that crosses the peak. Drawdowns are never charged twice — once
    the peak is updated it ratchets upward.
  - ``use_hwm=False`` (simple hurdle): the fee is charged every day whose
    return exceeds ``hurdle / 252``.

The function returns a *net-of-fee return series* aligned to the input.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

TRADING_DAYS_PER_YEAR = 252


@dataclass
class FeeModel:
    """Fund-level fee parameters applied to portfolio NAV.

    Attributes
    ----------
    mgmt_fee_annual:
        Annualised management fee as a fraction (e.g. 0.01 = 1%/yr).
        Deducted uniformly each trading day (``/252``).
    perf_fee:
        Performance-fee share of excess return (e.g. 0.20 = "2 and 20"
        carry). Zero disables the performance component.
    hurdle:
        Annualised hurdle rate. Performance fee is only levied on the return
        above ``hurdle / 252`` per day (or, under HWM, on the peak-crossing
        gain above the cumulative hurdle).
    use_hwm:
        When ``True`` use the high-water-mark convention (charge only on
        new peak NAVs); when ``False`` use a simple daily excess hurdle.
    """

    mgmt_fee_annual: float = 0.01
    perf_fee: float = 0.0
    hurdle: float = 0.0
    use_hwm: bool = True


def _coerce_to_list(returns: "pl.Series | list[float]") -> list[float]:
    """Accept a Polars Series or plain list and return a Python list."""
    if isinstance(returns, pl.Series):
        return returns.to_list()
    return list(returns)


def apply_fee_model(returns: "pl.Series | list[float]", fee: FeeModel) -> pl.Series:
    """Apply a :class:`FeeModel` to a gross NAV return series.

    Parameters
    ----------
    returns:
        Periodic (daily) gross portfolio returns, e.g. the
        ``portfolio_return`` column from
        :class:`~cquant.backtest_vector.engine.BacktestResult`.
    fee:
        Fee model to apply.

    Returns
    -------
    pl.Series
        Net-of-fee return series, same length as the input. Named ``"net"``.

    Notes
    -----
    Internally the gross returns are compounded into a NAV path (starting at
    1.0), fees are extracted from NAV, and the result is converted back to a
    net return series. This keeps the HWM bookkeeping (which is inherently
    level-based rather than return-based) correct.

    The management fee is applied first (it accrues regardless of
    performance), then the performance fee is layered on top of the
    post-management-fee NAV.
    """
    gross = _coerce_to_list(returns)
    n = len(gross)

    if n == 0:
        return pl.Series("net", [], dtype=pl.Float64)

    # No-op fast path: nothing to charge.
    if fee.mgmt_fee_annual <= 0 and fee.perf_fee <= 0:
        return pl.Series("net", gross, dtype=pl.Float64)

    daily_mgmt = fee.mgmt_fee_annual / TRADING_DAYS_PER_YEAR
    daily_hurdle = fee.hurdle / TRADING_DAYS_PER_YEAR

    # --- Build gross NAV path (cumprod, starting at 1.0) ---
    gross_nav = [1.0] * n
    for i in range(1, n):
        gross_nav[i] = gross_nav[i - 1] * (1.0 + gross[i])

    # --- Apply management fee, then performance fee, day by day ---
    net_nav = [0.0] * n
    net_nav[0] = 1.0  # first period has no return to charge against
    peak_nav = 1.0    # running high-water mark for performance-fee accrual

    for i in range(1, n):
        prev_net = net_nav[i - 1]

        # Management fee: accrues unconditionally, scaled by today's gross move.
        # We apply it to the net NAV carried forward: net grows by gross return
        # then loses the daily management fraction.
        gross_r = gross[i]
        after_mgmt = prev_net * (1.0 + gross_r) * (1.0 - daily_mgmt)

        if fee.perf_fee > 0:
            if fee.use_hwm:
                # High-water-mark: charge only the portion that exceeds the
                # running peak AND the cumulative hurdle accrued this period.
                # Candidate new NAV before perf fee:
                candidate = after_mgmt
                # Effective hurdle for this period relative to prev_net:
                hurdle_threshold = prev_net * (1.0 + daily_hurdle)
                # Chargeable base = amount candidate exceeds max(peak, hurdle_threshold)
                base = max(peak_nav, hurdle_threshold)
                chargeable = candidate - base
                if chargeable > 0:
                    perf_charge = chargeable * fee.perf_fee
                    after_perf = candidate - perf_charge
                    # Update peak only when we actually set a new high
                    if after_perf > peak_nav:
                        peak_nav = after_perf
                else:
                    after_perf = candidate
                    # NAV didn't make a new peak — peak stays
                net_nav[i] = after_perf
            else:
                # Simple daily hurdle: charge perf_fee on return above hurdle/252.
                excess = gross_r - daily_hurdle
                if excess > 0:
                    # Apply perf fee as NAV deduction (consistent with HWM path)
                    perf_charge = prev_net * (1.0 + gross_r) * fee.perf_fee * excess
                    net_nav[i] = after_mgmt - perf_charge
                else:
                    net_nav[i] = after_mgmt
        else:
            net_nav[i] = after_mgmt

    # --- Convert net NAV path back to a net return series ---
    net_returns = [0.0] * n
    for i in range(1, n):
        prev = net_nav[i - 1]
        net_returns[i] = (net_nav[i] - prev) / prev if prev > 0 else 0.0

    return pl.Series("net", net_returns, dtype=pl.Float64)
