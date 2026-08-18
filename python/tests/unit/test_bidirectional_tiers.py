"""Bidirectional tiered stop — PRD sec.5, 7 scenarios.

Covers the five-section PRD scenarios for the two-sided tier ladder:
engine-level tp partial exit, ratchet/rearm semantics, side-combination
independence, sign validation, legacy alias parity, and cross-policy
same-day double forced exits.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import polars as pl
import pytest

from cquant.backtest_vector.costs import CostModel
from cquant.backtest_vector.engine import VectorBacktestEngine, BacktestSpec
from cquant.backtest_vector.strategy import Strategy, StrategyContext
from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext
from cquant.riskguard.policies.base import RiskPolicy
from cquant.riskguard.policies.forced_exit import ForcedExitPolicy
from cquant.riskguard.policies.global_stop import GlobalStopPolicy
from cquant.riskguard.policies.stop_loss import FixedStopLossPolicy

TP_TIERS = [
    {"threshold": 0.15, "fraction": 0.5},
    {"threshold": 0.30, "fraction": 1.0},
]
SL_TIERS = [
    {"threshold": -0.03, "fraction": 0.3},
    {"threshold": -0.05, "fraction": 0.4},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check(policy, pnl, state, asset="A", entry=100.0):
    return policy.check_exits(
        positions={asset: {"weight": 0.5}},
        current_prices={asset: entry * (1 + pnl)},
        entry_prices={asset: entry},
        state=state,
    )


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


class _TpTierGlobalStop(GlobalStopPolicy, _ApproveAll):
    """GlobalStopPolicy with tp tiers @ 15%/50% + risk gate."""

    def __init__(self) -> None:
        GlobalStopPolicy.__init__(self, take_profit_tiers=TP_TIERS)


class _SlTierGlobalStop(GlobalStopPolicy, _ApproveAll):
    """GlobalStopPolicy with sl tier @ -3%/50% + risk gate."""

    def __init__(self) -> None:
        GlobalStopPolicy.__init__(
            self, stop_loss_tiers=[{"threshold": -0.03, "fraction": 0.5}]
        )


class _FixedStopWithGate(FixedStopLossPolicy, _ApproveAll, ForcedExitPolicy):
    """FixedStopLossPolicy(-5%) wired into the forced-exit loop.

    Plain FixedStopLossPolicy is only a RiskPolicy (pre-trade gate); the
    engine's forced-exit loop picks policies that are ForcedExitPolicy
    instances, so we mix it in to reuse FixedStopLossPolicy.check_exits.
    """

    def __init__(self, stop_pct: float = -0.05) -> None:
        FixedStopLossPolicy.__init__(self, stop_pct=stop_pct)


class _BuyAndHold(Strategy):
    def __init__(self, asset_ids: list[str]) -> None:
        self._asset_ids = asset_ids

    @property
    def strategy_id(self) -> str:
        return "buy_and_hold_bidir_tier_test"

    def generate_signals(self, ctx: StrategyContext) -> pl.DataFrame:
        return pl.DataFrame({
            "asset_id": self._asset_ids,
            "signal_date": [ctx.as_of_date] * len(self._asset_ids),
            "direction": ["long"] * len(self._asset_ids),
            "strength": [1.0] * len(self._asset_ids),
            "confidence": [1.0] * len(self._asset_ids),
        })


def _two_asset_prices(
    path_a: list[float], n_days: int, start=date(2025, 1, 2)
) -> pl.DataFrame:
    """Asset A follows path_a (one price per day, extended flat at the end);
    asset B is a gently rising distractor."""
    path = list(path_a)
    if len(path) < n_days:
        path = path + [path[-1]] * (n_days - len(path))
    rows: list[dict] = []
    for i in range(n_days):
        d = start + timedelta(days=i)
        p_a = path[i]
        rows.append({
            "trade_date": d, "asset_id": "SH600001",
            "open": p_a, "high": p_a * 1.01, "low": p_a * 0.99,
            "close": p_a, "volume": 1_000_000.0, "amount": p_a * 1_000_000,
            "is_suspended": False,
        })
        p_b = 10.0 * (1 + 0.001 * i)
        rows.append({
            "trade_date": d, "asset_id": "SH600002",
            "open": p_b, "high": p_b * 1.01, "low": p_b * 0.99,
            "close": p_b, "volume": 1_000_000.0, "amount": p_b * 1_000_000,
            "is_suspended": False,
        })
    return pl.DataFrame(rows)


def _run(prices, policies, start=date(2025, 1, 2), end=date(2025, 1, 26)):
    """Monthly rebalance: the engine clears fired_tiers on every rebalance
    and re-injects weights (which re-buys exited assets), so daily/weekly
    rebalancing would reset the tier ladder mid-scenario.  Monthly fires
    only at the window start, keeping the ratchet state alive throughout."""
    engine = VectorBacktestEngine()
    spec = BacktestSpec(
        strategy=_BuyAndHold(["SH600001", "SH600002"]),
        prices=prices,
        start_date=start,
        end_date=end,
        initial_cash=Decimal("1_000_000"),
        cost_model=CostModel.for_cn(),
        risk_policies=policies,
        rebalance_frequency="1mo",
    )
    return engine.run(spec)


# ---------------------------------------------------------------------------
# Scenario 1: engine-level tp tier partial exit
# ---------------------------------------------------------------------------

class TestTpTierPartialExitEngine:
    def test_tp_tier_partial_exit(self):
        """Engine run: +16% breaches tp tier 0 → sell ~50%, tier0 fired once."""
        # A rises 10 → 11.6 (+16%) on day 10, then stays
        path = [10.0] * 10 + [11.6] * 10
        result = _run(_two_asset_prices(path, 20), [_TpTierGlobalStop()])

        fe = [e for e in result.forced_exits if e["asset_id"] == "SH600001"]
        assert fe, "expected forced exit for the rising asset"
        # Tier 0 (15%, 50% fraction) fired — exactly once
        tier0 = [e for e in fe if "global_take_profit_tier0" in e["reason"]]
        assert len(tier0) == 1
        assert "exit fraction 50%" in tier0[0]["reason"]
        # Tier 1 (30%) never fired (+16% < +30%)
        assert not any("tier1" in e["reason"] for e in fe)
        # The partial exit materialised as a sell fill
        sells = result.fills.filter(
            (pl.col("side") == "sell") & (pl.col("asset_id") == "SH600001")
        )
        assert sells.height > 0

        # Engine-side scaling: committed weight halves under fraction 0.5
        committed = {"SH600001": 0.40}
        all_w: list[dict] = []
        remaining = VectorBacktestEngine._execute_forced_exit(
            "SH600001", committed, all_w, date(2025, 1, 15), exit_fraction=0.5,
        )
        assert remaining == pytest.approx(0.20)
        assert all_w[-1]["target_weight"] == pytest.approx(0.20)  # sell ~50%


# ---------------------------------------------------------------------------
# Scenario 2: ratchet — fired tier does not re-fire without a rearm
# ---------------------------------------------------------------------------
# Semantics note (vs the PRD wording): the rearm line for a tp tier at
# threshold t is ``pnl < t - buffer``.  With the default buffer (0.5%) the
# line sits at 14.5%, so a pullback to +14% HAS crossed it and the tier
# legitimately re-arms (see test 3).  For the ratchet scenario to hold —
# "pull back modestly, rally again, no re-fire" — the pullback must stay
# above the rearm line, which the explicit buffer=0.02 (line at 13%)
# guarantees for the PRD's +14% pullback.  Both behaviours are asserted
# below against the implementation's actual hysteresis semantics.

class TestTpRatchetNoRefire:
    def test_tp_ratchet_no_refire(self):
        """+16% fires → +14% (above 13% rearm line) → +17% must NOT re-fire."""
        policy = GlobalStopPolicy(
            take_profit_tiers=TP_TIERS, tier_rearm_buffer=0.02
        )
        state = {"fired_tiers": {}}

        assert len(_check(policy, 0.16, state)) == 1
        assert 0 in state["fired_tiers"]["A"]["tp"]

        # Pullback to +14%: 14% > 15% - 2% = 13% → NOT re-armed, still fired
        assert _check(policy, 0.14, state) == []
        assert 0 in state["fired_tiers"]["A"]["tp"]

        # Rally to +17% — tier 0 still fired → no re-fire
        assert _check(policy, 0.17, state) == []

    def test_tp_default_buffer_14pct_pullback_rearms(self):
        """Default buffer (0.5%): +14% < 14.5% rearm line → re-arms, re-fires.

        This documents the actual hysteresis semantics: with the default
        buffer the PRD's +14% pullback DOES re-arm tier 0, so the +17%
        rally fires again.  Ratchet suppression requires the pullback to
        stay above ``threshold - buffer``.
        """
        policy = GlobalStopPolicy(take_profit_tiers=TP_TIERS)  # buffer=0.005
        state = {"fired_tiers": {}}

        assert len(_check(policy, 0.16, state)) == 1
        # 14% < 15% - 0.5% = 14.5% → re-armed
        assert _check(policy, 0.14, state) == []
        assert 0 not in state["fired_tiers"]["A"]["tp"]
        # +17% breaches the re-armed tier → fires again
        exits = _check(policy, 0.17, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Scenario 3: rearm after a deep pullback, then fresh breach re-fires
# ---------------------------------------------------------------------------

class TestTpRearmAfterPullback:
    def test_tp_rearm_after_pullback(self):
        """Fire 15% tier → pull back to +9% (rearm) → +16% re-fires."""
        policy = GlobalStopPolicy(take_profit_tiers=TP_TIERS)
        state = {"fired_tiers": {}}

        assert len(_check(policy, 0.16, state)) == 1
        assert 0 in state["fired_tiers"]["A"]["tp"]

        # +9% < 14.5% rearm line → tier 0 re-armed
        assert _check(policy, 0.09, state) == []
        assert 0 not in state["fired_tiers"]["A"]["tp"]

        # Fresh breach at +16% → fires again
        exits = _check(policy, 0.16, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.5)
        assert 0 in state["fired_tiers"]["A"]["tp"]


# ---------------------------------------------------------------------------
# Scenario 4: side independence — all 5 configuration combos
# ---------------------------------------------------------------------------

class TestBothSidesIndependent:
    def test_only_sl_tiers(self):
        policy = GlobalStopPolicy(stop_loss_tiers=SL_TIERS)
        state = {"fired_tiers": {}}
        # Loss side: tiered
        exits = _check(policy, -0.035, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.3)
        assert "global_stop_tier0" in exits[0].reason
        # Gain side: silent
        assert _check(policy, 0.16, state) == []
        assert "tp" not in state["fired_tiers"]["A"] or (
            state["fired_tiers"]["A"]["tp"] == set()
        )

    def test_only_tp_tiers(self):
        policy = GlobalStopPolicy(take_profit_tiers=TP_TIERS)
        state = {"fired_tiers": {}}
        exits = _check(policy, 0.16, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.5)
        assert "global_take_profit_tier0" in exits[0].reason
        # Loss side: silent
        assert _check(policy, -0.06, state) == []
        assert state["fired_tiers"]["A"]["sl"] == set()

    def test_both_sides_tiers(self):
        policy = GlobalStopPolicy(
            stop_loss_tiers=SL_TIERS, take_profit_tiers=TP_TIERS
        )
        state = {"fired_tiers": {}}
        # Loss side fires its own ladder, gain side untouched
        exits = _check(policy, -0.035, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.3)
        assert state["fired_tiers"]["A"]["sl"] == {0}
        assert state["fired_tiers"]["A"]["tp"] == set()
        # Gain side fires its own ladder.  Note: +16% also re-arms the sl
        # tier (rearm line -2.5% < +16%), so the sl set empties — sides are
        # evaluated independently against the same pnl, exactly the
        # implementation's hysteresis semantics.
        exits = _check(policy, 0.16, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == pytest.approx(0.5)
        assert state["fired_tiers"]["A"]["tp"] == {0}
        assert state["fired_tiers"]["A"]["sl"] == set()  # re-armed by the gain

    def test_both_sides_single_threshold(self):
        policy = GlobalStopPolicy(stop_loss_pct=-0.05, take_profit_pct=0.15)
        state = {"fired_tiers": {}}
        exits = _check(policy, 0.16, state)
        assert len(exits) == 1
        assert "global_take_profit" in exits[0].reason
        assert exits[0].exit_fraction == 1.0
        exits = _check(policy, -0.06, state)
        assert len(exits) == 1
        assert "global_stop_loss" in exits[0].reason
        assert exits[0].exit_fraction == 1.0

    def test_one_side_disabled(self):
        """Only tp configured; the sl leg is fully absent (None)."""
        policy = GlobalStopPolicy(take_profit_pct=0.15)
        state = {"fired_tiers": {}}
        assert _check(policy, -0.50, state) == []  # no sl leg → no exit
        exits = _check(policy, 0.20, state)
        assert len(exits) == 1
        assert exits[0].exit_fraction == 1.0


# ---------------------------------------------------------------------------
# Scenario 5: threshold sign validation
# ---------------------------------------------------------------------------

class TestThresholdSignValidation:
    def test_tp_negative_threshold_rejected(self):
        with pytest.raises(ValueError, match="tp tier threshold must be >= 0"):
            GlobalStopPolicy(
                take_profit_tiers=[{"threshold": -0.15, "fraction": 0.5}]
            )

    def test_sl_positive_threshold_rejected(self):
        with pytest.raises(ValueError, match="sl tier threshold must be <= 0"):
            GlobalStopPolicy(
                stop_loss_tiers=[{"threshold": 0.03, "fraction": 0.3}]
            )


# ---------------------------------------------------------------------------
# Scenario 6: legacy `tiers` alias parity (field-by-field ForcedExit equality)
# ---------------------------------------------------------------------------

class TestLegacyTiersAlias:
    def test_legacy_tiers_alias(self):
        tiers = [
            {"threshold": -0.03, "fraction": 0.3},
            {"threshold": -0.05, "fraction": 0.4},
        ]
        legacy = GlobalStopPolicy(tiers=tiers)
        named = GlobalStopPolicy(stop_loss_tiers=tiers)

        state_l = {"fired_tiers": {}}
        state_n = {"fired_tiers": {}}
        for pnl in (-0.02, -0.035, -0.04, -0.055, -0.06, -0.02, -0.035):
            el = _check(legacy, pnl, state_l)
            en = _check(named, pnl, state_n)
            assert el == en  # dataclass equality: every field identical
        assert state_l["fired_tiers"]["A"]["sl"] == state_n["fired_tiers"]["A"]["sl"]


# ---------------------------------------------------------------------------
# Scenario 7: cross-policy same-day double forced exit
# ---------------------------------------------------------------------------

class TestCrossPolicySameDay:
    def test_second_fraction_applies_to_remaining(self):
        """Partial (50%) then full (100%) same day: second scales the rest."""
        committed = {"SH600001": 0.50}
        all_w: list[dict] = []
        d = date(2025, 1, 15)
        r1 = VectorBacktestEngine._execute_forced_exit(
            "SH600001", committed, all_w, d, exit_fraction=0.5)
        r2 = VectorBacktestEngine._execute_forced_exit(
            "SH600001", committed, all_w, d, exit_fraction=1.0)
        assert r1 == pytest.approx(0.25)
        assert r2 == 0.0  # full exit of the REMAINING 50%
        assert "SH600001" not in committed

    def test_engine_global_then_fixed_double_exit(self):
        """Global partial + Fixed full on the crash day: both execute in order."""
        # A crashes 10 → 7.8 (-22%) on day 9: breaches the -3% tier AND -5% fixed
        path = [10.0] * 9 + [7.8] * 11
        result = _run(
            _two_asset_prices(path, 20),
            [_SlTierGlobalStop(), _FixedStopWithGate(-0.05)],
        )
        fe = [e for e in result.forced_exits if e["asset_id"] == "SH600001"]
        assert len(fe) == 2, "both policies must fire on the same day"
        reasons = [e["reason"] for e in fe]
        assert "global_stop_tier0" in reasons[0]  # policy order preserved
        assert "fixed_stop_loss" in reasons[1]
        assert "exit fraction 50%" in reasons[0]
        # Full exit materialised as sells (partial 50% + remaining 50%)
        sells = result.fills.filter(
            (pl.col("side") == "sell") & (pl.col("asset_id") == "SH600001")
        )
        assert sells.height > 0

    def test_engine_full_exit_first_second_guarded(self):
        """Fixed full exit first → Global's exit is skipped by the guard."""
        path = [10.0] * 9 + [7.8] * 11
        result = _run(
            _two_asset_prices(path, 20),
            [_FixedStopWithGate(-0.05), _SlTierGlobalStop()],
        )
        fe = [e for e in result.forced_exits if e["asset_id"] == "SH600001"]
        # Only the fixed stop's event: the asset is gone from committed
        # weights (and its entry price popped), so the Global tier exit —
        # even if evaluated — is skipped by the `in committed_weights` guard.
        assert len(fe) == 1
        assert "fixed_stop_loss" in fe[0]["reason"]
        sells = result.fills.filter(
            (pl.col("side") == "sell") & (pl.col("asset_id") == "SH600001")
        )
        assert sells.height > 0
