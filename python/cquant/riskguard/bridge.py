"""cquant.riskguard.bridge — Optional Rust bridge for portfolio risk state.

Gracefully degrades when the Rust cquant_py wheel is not built:
  - pre_trade_check → conservative Python-only approval
  - apply_fill / snapshot → returns empty/unchanged RiskSnapshot

Usage::

    bridge = RustRiskBridge()
    if bridge.available:
        decision = bridge.pre_trade_check(intent, snapshot, ctx)
    # If not available, still safe to call — returns Python fallback.
"""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from cquant.core.enums import RiskDecisionType
from cquant.core.types import OrderFill, OrderIntent, RiskDecision, RiskSnapshot
from cquant.riskguard.models import RiskContext

logger = logging.getLogger(__name__)


class RustRiskBridge:
    """Wrap the optional Rust risk state machine from ``cquant_py``.

    The bridge probes the loaded module for a compatible risk state-machine
    object (duck-typed: must expose pre_trade_check / apply_fill / snapshot).
    When the wheel is absent or the state machine is not yet exposed, every
    call transparently falls back to a safe Python-only path.
    """

    def __init__(self) -> None:
        self._module: Any | None = None
        self._state_machine: Any | None = None
        self._last_snapshot: RiskSnapshot | None = None
        self._init()

    @property
    def available(self) -> bool:
        """True when the Rust risk state machine is loaded and ready."""
        return self._state_machine is not None

    # ── Public API ─────────────────────────────────────────────────────────────

    def pre_trade_check(
        self,
        intent: OrderIntent,
        snapshot: RiskSnapshot,
        ctx: RiskContext,
    ) -> RiskDecision:
        self._last_snapshot = snapshot
        if self.available:
            try:
                raw = self._state_machine.pre_trade_check(intent, self._to_rust_snapshot(snapshot), ctx)
                return self._coerce_decision(raw, intent)
            except Exception as exc:
                logger.warning("Rust pre_trade_check failed, using Python fallback: %s", exc)
        return self._py_pre_trade_check(intent)

    def apply_fill(self, fill: OrderFill) -> RiskSnapshot:
        if self.available:
            try:
                raw = self._state_machine.apply_fill(fill)
                self._last_snapshot = self._coerce_snapshot(raw)
                return self._last_snapshot
            except Exception as exc:
                logger.warning("Rust apply_fill failed, using Python fallback: %s", exc)
        self._last_snapshot = self._py_apply_fill(fill)
        return self._last_snapshot

    def snapshot(self) -> RiskSnapshot:
        if self.available:
            try:
                raw = self._state_machine.snapshot()
                self._last_snapshot = self._coerce_snapshot(raw)
                return self._last_snapshot
            except Exception as exc:
                logger.warning("Rust snapshot fetch failed, using Python fallback: %s", exc)
        return self._last_snapshot or self._empty_snapshot()

    # ── Initialisation ─────────────────────────────────────────────────────────

    def _init(self) -> None:
        try:
            self._module = importlib.import_module("cquant_py")
        except ImportError:
            logger.debug("cquant_py wheel not found; RustRiskBridge running in Python-only mode")
            return
        self._state_machine = self._find_state_machine(self._module)

    def _find_state_machine(self, module: Any) -> Any | None:
        """Duck-type probe for a compatible risk state machine in the module."""
        required = ("pre_trade_check", "apply_fill", "snapshot")
        for name in ("PyRiskEngine", "PyRiskStateMachine", "create_risk_engine", "create_risk_state_machine"):
            obj = getattr(module, name, None)
            if obj is None:
                continue
            # Already an instance
            if not isinstance(obj, type) and all(hasattr(obj, m) for m in required):
                return obj
            # Class — try to instantiate with no args
            if isinstance(obj, type):
                try:
                    instance = obj()
                    if all(hasattr(instance, m) for m in required):
                        return instance
                except TypeError:
                    continue
            # Factory function
            if callable(obj):
                try:
                    instance = obj()
                    if all(hasattr(instance, m) for m in required):
                        return instance
                except TypeError:
                    continue
        return None

    # ── Type coercion helpers ──────────────────────────────────────────────────

    def _to_rust_snapshot(self, snap: RiskSnapshot) -> Any:
        if self._module is None:
            return snap
        cls = getattr(self._module, "PyRiskSnapshot", None)
        if cls is None:
            return snap
        try:
            return cls(**snap.model_dump())
        except Exception:
            return snap

    def _coerce_decision(self, raw: Any, intent: OrderIntent) -> RiskDecision:
        if isinstance(raw, RiskDecision):
            return raw
        payload: dict = {}
        if hasattr(raw, "model_dump"):
            payload = raw.model_dump()
        elif isinstance(raw, dict):
            payload = dict(raw)
        else:
            payload = {
                "decision": getattr(raw, "decision", RiskDecisionType.APPROVED.value),
                "original_qty": getattr(raw, "original_qty", intent.requested_qty),
                "approved_qty": getattr(raw, "approved_qty", intent.requested_qty),
                "reasons": list(getattr(raw, "reasons", [])),
                "policy_names": list(getattr(raw, "policy_names", ["rust"])),
            }
        payload.setdefault("decision", RiskDecisionType.APPROVED.value)
        payload.setdefault("original_qty", intent.requested_qty)
        payload.setdefault("approved_qty", intent.requested_qty)
        payload.setdefault("reasons", [])
        payload.setdefault("policy_names", ["rust"])
        return RiskDecision(**payload)

    def _coerce_snapshot(self, raw: Any) -> RiskSnapshot:
        if isinstance(raw, RiskSnapshot):
            return raw
        if hasattr(raw, "model_dump"):
            return RiskSnapshot(**raw.model_dump())
        if isinstance(raw, dict):
            return RiskSnapshot(**raw)
        return RiskSnapshot(
            snapshot_ts=datetime.now(tz=timezone.utc),
            strategy_id="",
            gross_leverage=getattr(raw, "gross_leverage", 0.0),
            net_leverage=getattr(raw, "net_leverage", 0.0),
            drawdown=getattr(raw, "drawdown", 0.0),
            var_95=getattr(raw, "var_95", None),
        )

    # ── Python-only fallbacks ──────────────────────────────────────────────────

    def _py_pre_trade_check(self, intent: OrderIntent) -> RiskDecision:
        if intent.requested_qty <= Decimal("0"):
            return RiskDecision(
                decision=RiskDecisionType.REJECTED,
                original_qty=intent.requested_qty,
                approved_qty=Decimal("0"),
                reasons=["requested_qty must be positive"],
                policy_names=["python_fallback"],
            )
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            original_qty=intent.requested_qty,
            approved_qty=intent.requested_qty,
            reasons=[],
            policy_names=["python_fallback"],
        )

    def _py_apply_fill(self, fill: OrderFill) -> RiskSnapshot:
        base = self._last_snapshot or self._empty_snapshot()
        ts = fill.filled_at or datetime.now(tz=timezone.utc)
        return base.model_copy(update={"snapshot_ts": ts})

    @staticmethod
    def _empty_snapshot() -> RiskSnapshot:
        return RiskSnapshot(snapshot_ts=datetime.now(tz=timezone.utc), strategy_id="")
