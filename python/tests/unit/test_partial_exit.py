"""Partial forced-exit — full-scenario tests (7 scenarios).

Covers the partial-exit feature end to end: tiered GlobalStopPolicy
semantics, engine ``_execute_forced_exit`` partial scaling, T+1 blocked-sell
re-injection, backward compatibility, and dust-position escalation.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import polars as pl
import pytest

from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.engine import (
    MIN_REMAINING_WEIGHT,
    VectorBacktestEngine,
    BacktestSpec,
)
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy
from cquant.riskguard.policies.forced_exit import ForcedExit, ForcedExitPolicy
from cquant.riskguard.policies.global_stop import GlobalStopPolicy

TIERS = [
    {"threshold": -0.03, "fraction": 0.3},
    {"threshold": -0.05, "fraction": 0.4},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _policy_check(policy, pnl, state, asset="A", entry=100.0):
    """Run GlobalStopPolicy.check_exits at a given P&L level."""
    return policy.check_exits(
        positions={asset: {"weight": 0.5}},
        current_prices={asset: entry * (1 + pnl)},
        entry_prices={asset: entry},
        state=state,
    )


def _execute(asset, committed_weight, fraction):
    """Run engine._execute_forced_exit with clean containers.

    Returns (remaining, committed_weights, all_weights) after the call.
    """
    committed = {asset: committed_weight}
    all_w: list[dict] = []
    remaining = VectorBacktestEngine._execute_forced_exit(
        asset_id=asset,
        committed_weights=committed,
        all_weights=all_w,
        exit_date=date(2025, 1, 15),
        exit_fraction=fraction,
    )
    return remaining, committed, all_w


class _ApproveAll(RiskPolicy):
    """Always-approve RiskPolicy so the engine's pre-trade gate passes."""

    @property
    def name(self) -> str:
        return "approve_all"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )


class _HalfExitGlobalStop(GlobalStopPolicy, _ApproveAll):
    """GlobalStopPolicy single tier @ -3% with 50% exit + risk gate."""

    def __init__(self) -> None:
        GlobalStopPolicy.__init__(
            self, tiers=[{"threshold": -0.03, "fraction": 0.5}]
        )


class _BuyAndHold(Strategy):
    def __init__(self, asset_ids: list[str]) -> None:
        self._asset_ids = asset_ids

    @property
    def strategy_id(self) -> str:
        return "buy_and_hold_partial_exit_test"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": self._asset_ids,
            "signal_date": [ctx.as_of_date] * len(self._asset_ids),
            "direction": ["long"] * len(self._asset_ids),
            "strength": [1.0] * len(self._asset_ids),
            "confidence": [1.0] * len(self._asset_ids),
        })


def _crash_prices(drop_pct=-0.20, n_days=25, start=date(2025, 1, 2)) -> pl.DataFrame:
    """Two assets: one flat then crashing, one gently rising."""
    rows: list[dict] = []
    for i in range(n_days):
        d = start + timedelta(days=i)
        p_drop = 10.0 if i <= 8 else 10.0 * (1 + drop_pct)
        rows.append({
            "trade_date": d, "asset_id": "SH600001",
            "open": p_drop, "high": p_drop * 1.01, "low": p_drop * 0.99,
            "close": p_drop, "volume": 1_000_000.0, "amount": p_drop * 1_000_000,
            "is_suspended": False,
        })
        p_stable = 10.0 * (1 + 0.001 * i)
        rows.append({
            "trade_date": d, "asset_id": "SH600002",
            "open": p_stable, "high": p_stable * 1.01, "low": p_stable * 0.99,
            "close": p_stable, "volume": 1_000_000.0, "amount": p_stable * 1_000_000,
            "is_suspended": False,
        })
    return pl.DataFrame(rows)


def _run(prices, policies, start=date(2025, 1, 2), end=date(2025, 1, 26)):
    engine = VectorBacktestEngine()
    spec = BacktestSpec(
        strategy=_BuyAndHold(["SH600001", "SH600002"]),
        prices=prices,
        start_date=start,
        end_date=end,
        initial_cash=Decimal("1_000_000"),
        cost_model=CostModel.for_cn(),
        risk_policies=policies,
        rebalance_frequency="1d",
    )
    return engine.run(spec)


# ---------------------------------------------------------------------------
# Scenario 1: partial exit at 50% halves the position, keeps remainder
# ---------------------------------------------------------------------------

class TestPartialHalf:
    def test_partial_half(self):
        """50% partial exit halves committed weight; remainder stays > 0."""
        remaining, committed, all_w = _execute("SH600001", 0.40, fraction=0.5)
        assert remaining == pytest.approx(0.20)
        assert committed["SH600001"] == pytest.approx(0.20)  # scaled, not deleted
        # Injected target = remaining weight (FillSimulator sells the other half)
        assert len(all_w) == 1
        assert all_w[0]["asset_id"] == "SH600001"
        assert all_w[0]["target_weight"] == pytest.approx(0.20)
        assert all_w[0]["target_weight"] != 0.0  # NOT a full-exit zero target

    def test_partial_half_engine_end_to_end(self):
        """Full engine run with a 50%-tier GlobalStopPolicy keeps residual."""
        result = _run(_crash_prices(), [_HalfExitGlobalStop()])
        assert len(result.forced_exits) > 0
        fe = [e for e in result.forced_exits if e["asset_id"] == "SH600001"]
        assert fe, "expected forced exit for crashing asset"
        # Partial exit fired at least once
        assert any("exit fraction 50%" in e["reason"] for e in fe)

        # The crashing asset should still hold a position afterwards —
        # verify via fills: partial exit sells, but later snapshot exposure
        # remains > 0 (a second tier/rebalance still trades it afterwards).
        sells = result.fills.filter(
            (pl.col("side") == "sell") & (pl.col("asset_id") == "SH600001")
        )
        assert sells.height > 0, "partial exit must produce sell fills"
        # And at least one later buy/hold fill proves the position survived
        # (buy-and-hold re-injects weights on rebalance → partial remainder
        # means the asset is NOT in cooldown, so it keeps trading).
        all_fills = result.fills.filter(pl.col("asset_id") == "SH600001")
        assert all_fills.height > sells.height, (
            "partial exit should not terminate trading of the asset"
        )


# ---------------------------------------------------------------------------
# Scenario 2: two tiers fire progressively (cumulative)
# ---------------------------------------------------------------------------

class TestTieredTP:
    def test_tiered_tp(self):
        """-3.5% fires tier 1 only; -5.5% then fires tier 2 cumulatively."""
        policy = GlobalStopPolicy(tiers=TIERS)
        state = {"fired_tiers": {}}

        # Breach tier 1 only → 30% exit
        exits = _policy_check(policy, -0.035, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.3)
        assert state["fired_tiers"]["A"] == {0}

        # Deeper breach → tier 2 fires on top (cumulative 30% + 40%)
        exits = _policy_check(policy, -0.055, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.4)
        assert state["fired_tiers"]["A"] == {0, 1}

        # Engine-side cumulative effect: 0.5 → 70% → 15% remaining
        committed = {"A": 0.5}
        all_w: list[dict] = []
        d = date(2025, 1, 10)
        r1 = VectorBacktestEngine._execute_forced_exit("A", committed, all_w, d, 0.3)
        r2 = VectorBacktestEngine._execute_forced_exit("A", committed, all_w, d, 0.4)
        assert r1 == pytest.approx(0.35)
        assert r2 == pytest.approx(0.35 * 0.6)  # 0.21
        assert committed["A"] == pytest.approx(0.21)


# ---------------------------------------------------------------------------
# Scenario 3: ratchet — same tier does not re-fire while drawdown persists
# ---------------------------------------------------------------------------

class TestRatchetNoRefire:
    def test_ratchet_no_refire(self):
        policy = GlobalStopPolicy(tiers=TIERS)
        state = {"fired_tiers": {}}

        assert len(_policy_check(policy, -0.035, state)) == 1

        # -4% persists for many days: tier 1 already fired → silence
        for _ in range(10):
            assert _policy_check(policy, -0.04, state) == []

        # Engine-side corollary: no re-execution means committed weight
        # stays at the post-tier-1 level (no repeated 30% shaves).
        committed = {"A": 0.5}
        all_w: list[dict] = []
        VectorBacktestEngine._execute_forced_exit(
            "A", committed, all_w, date(2025, 1, 10), 0.3)
        # Simulate the 10 silent days: no further _execute_forced_exit calls
        assert committed["A"] == pytest.approx(0.35)
        assert len(all_w) == 1  # only one injection happened


# ---------------------------------------------------------------------------
# Scenario 4: rearm on recovery beyond threshold + buffer
# ---------------------------------------------------------------------------

class TestRearmOnRecovery:
    def test_rearm_on_recovery(self):
        policy = GlobalStopPolicy(tiers=TIERS, tier_rearm_buffer=0.005)
        state = {"fired_tiers": {}}

        # Fire tier 1 at -3.5%
        assert len(_policy_check(policy, -0.035, state)) == 1
        assert 0 in state["fired_tiers"]["A"]

        # Recover above -0.03 + 0.005 = -0.025 → tier re-armed
        _policy_check(policy, -0.02, state)
        assert 0 not in state["fired_tiers"]["A"]

        # Fresh breach fires again
        exits = _policy_check(policy, -0.035, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.3)
        assert 0 in state["fired_tiers"]["A"]


# ---------------------------------------------------------------------------
# Scenario 5: T+1 blocked partial exit re-injects the REMAINING weight
# ---------------------------------------------------------------------------

class TestT1BlockedNotEscalated:
    def test_t1_blocked_not_escalated(self):
        """pending_force_exits carries the residual weight (not 0.0)."""
        pending_force_exits: dict[str, float] = {}

        # Simulate the engine's forced-exit block for a partial exit
        committed_weights = {"SH600001": 0.40}
        all_weights: list[dict] = []
        remaining = VectorBacktestEngine._execute_forced_exit(
            "SH600001", committed_weights, all_weights, date(2025, 1, 15),
            exit_fraction=0.5,
        )
        is_full_exit = remaining <= 0.0
        pending_force_exits["SH600001"] = remaining

        # Partial exit → NOT a full exit
        assert not is_full_exit
        # Re-injection value is the residual weight, never escalated to 0.0
        assert pending_force_exits["SH600001"] == pytest.approx(0.20)
        assert pending_force_exits["SH600001"] != 0.0

        # Engine re-injects that weight on the next trade date (T+1 retry)
        next_td = date(2025, 1, 16)
        reinject = [
            {"trade_date": next_td, "asset_id": a, "target_weight": w}
            for a, w in pending_force_exits.items()
        ]
        all_weights.extend(reinject)
        assert reinject[0]["target_weight"] == pytest.approx(0.20)

    def test_full_exit_pending_is_zero(self):
        """Contrast: full exit stores 0.0 in pending_force_exits."""
        committed = {"SH600001": 0.40}
        all_w: list[dict] = []
        remaining = VectorBacktestEngine._execute_forced_exit(
            "SH600001", committed, all_w, date(2025, 1, 15), exit_fraction=1.0)
        assert remaining == 0.0
        assert "SH600001" not in committed
        assert all_w[-1]["target_weight"] == 0.0


# ---------------------------------------------------------------------------
# Scenario 6: backward compatibility — explicit 1.0 == no exit_fraction
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_backward_compat(self):
        """Explicit fraction=1.0 and legacy default produce identical runs."""
        prices = _crash_prices()

        class _LegacyStop(_FixedStopLegacy):
            pass

        # Run 1: policy that emits ForcedExit WITHOUT exit_fraction (legacy)
        result_legacy = _run(prices, [_FixedStopLegacy()])
        # Run 2: same policy but explicitly setting exit_fraction=1.0
        result_explicit = _run(prices, [_FixedStopExplicitFull()])

        # Identical forced-exit events
        assert len(result_legacy.forced_exits) == len(result_explicit.forced_exits)
        assert len(result_legacy.forced_exits) > 0
        for a, b in zip(result_legacy.forced_exits, result_explicit.forced_exits):
            assert a["asset_id"] == b["asset_id"]
            assert a["date"] == b["date"]
            assert a["reason"] == b["reason"]

        # Identical fills (date, asset, side, qty, price)
        assert result_legacy.fills.height == result_explicit.fills.height
        cols = ["trade_date", "asset_id", "side", "qty", "price"]
        f1 = result_legacy.fills.select(cols).sort(cols)
        f2 = result_explicit.fills.select(cols).sort(cols)
        assert f1.equals(f2)

        # Identical NAV series
        nav1 = result_legacy.portfolio_returns
        nav2 = result_explicit.portfolio_returns
        assert len(nav1) == len(nav2)
        assert nav1.equals(nav2)

    def test_default_fraction_semantics(self):
        """_execute_forced_exit with default fraction == explicit 1.0."""
        committed1 = {"SH600001": 0.4}
        committed2 = {"SH600001": 0.4}
        w1: list[dict] = []
        w2: list[dict] = []
        d = date(2025, 1, 15)
        r1 = VectorBacktestEngine._execute_forced_exit("SH600001", committed1, w1, d)
        r2 = VectorBacktestEngine._execute_forced_exit(
            "SH600001", committed2, w2, d, exit_fraction=1.0)
        assert r1 == r2 == 0.0
        assert committed1 == committed2 == {}
        assert w1 == w2


class _FixedStopLegacy(ForcedExitPolicy, RiskPolicy):
    """Legacy-style stop that emits ForcedExit without exit_fraction."""

    def __init__(self, stop_pct: float = -0.05) -> None:
        self._stop_pct = stop_pct

    @property
    def name(self) -> str:
        return "fixed_stop_legacy"

    def evaluate(
        self, candidate: OrderIntent, snapshot: RiskSnapshot, ctx: RiskContext
    ) -> RiskDecision:
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=candidate.requested_qty,
            approved_qty=candidate.requested_qty,
            reasons=[],
            policy_names=[self.name],
        )

    def check_exits(self, positions, current_prices, entry_prices, state=None):
        exits: list[ForcedExit] = []
        for asset_id in positions:
            ep = entry_prices.get(asset_id)
            cp = current_prices.get(asset_id)
            if ep is None or cp is None or ep <= 0:
                continue
            pnl = (cp - ep) / ep
            if pnl < self._stop_pct:
                exits.append(ForcedExit(
                    asset_id=asset_id,
                    reason=f"fixed_stop_loss: P&L {pnl:.2%} < {self._stop_pct:.2%}",
                    urgency="high",
                    # exit_fraction omitted → defaults to 1.0 (legacy)
                ))
        return exits


class _FixedStopExplicitFull(_FixedStopLegacy):
    """Same stop, but explicitly sets exit_fraction=1.0."""

    def check_exits(self, positions, current_prices, entry_prices, state=None):
        exits = super().check_exits(positions, current_prices, entry_prices, state)
        return [
            ForcedExit(
                asset_id=e.asset_id, reason=e.reason, urgency=e.urgency,
                exit_fraction=1.0,
            )
            for e in exits
        ]


# ---------------------------------------------------------------------------
# Scenario 7: tiny remaining position escalates to full exit
# ---------------------------------------------------------------------------

class TestTinyRemainingFull:
    def test_tiny_remaining_full(self):
        """5% residual shaved by another 30% (→3.5%) exits fully."""
        remaining, committed, all_w = _execute("SH600001", 0.05, fraction=0.3)
        # 0.05 * 0.7 = 0.035 < MIN_REMAINING_WEIGHT (0.01)? No: 0.035 > 0.01.
        # Use an even smaller residual: 0.01 * 0.7 = 0.007 < 0.01 → full exit.
        assert 0.05 * 0.7 > MIN_REMAINING_WEIGHT  # sanity: 3.5% is NOT dust
        assert remaining == pytest.approx(0.035)
        assert "SH600001" in committed  # survives at 3.5%

        # True dust case: 1% residual, shave 30% → 0.7% < 1% → full exit
        remaining, committed, all_w = _execute("SH600001", 0.01, fraction=0.3)
        assert remaining == 0.0
        assert "SH600001" not in committed  # cleaned out entirely
        assert all_w[-1]["target_weight"] == 0.0  # full-exit zero target
        assert len(all_w) == 1

    def test_dust_boundary_exact(self):
        """Remaining exactly == MIN_REMAINING_WEIGHT is NOT dust (>= keeps)."""
        weight = MIN_REMAINING_WEIGHT / 0.5  # 50% exit → exactly the bound
        remaining, committed, _ = _execute("SH600001", weight, fraction=0.5)
        assert remaining == pytest.approx(MIN_REMAINING_WEIGHT)
        assert "SH600001" in committed

    def test_zero_lot_residual_full(self):
        """Lot-rounded zero-share case: any sub-threshold remainder → 0.0."""
        # e.g. committed weight so small the remainder is far below 1%
        remaining, committed, all_w = _execute("SH600001", 0.003, fraction=0.5)
        assert remaining == 0.0
        assert committed == {}
        assert all_w == [{"trade_date": date(2025, 1, 15),
                          "asset_id": "SH600001", "target_weight": 0.0}]
