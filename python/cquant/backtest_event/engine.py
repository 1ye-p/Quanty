"""cquant.backtest_event.engine — Swappable facade for the Rust event-driven engine.

Until cquant_py exposes a Rust-backed event engine this facade delegates to
VectorBacktestEngine, preserving a stable import surface for strategies and tests.

When the Rust wheel is available and exports one of the known entry points
(PyEventBacktestEngine, EventBacktestEngine, create_event_backtest_engine),
EventBacktestEngine.available returns True and run() dispatches to Rust.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

from cquant.backtest_vector.engine import BacktestResult, BacktestSpec, VectorBacktestEngine

logger = logging.getLogger(__name__)

_RUST_ENTRY_POINTS = (
    "PyEventBacktestEngine",
    "EventBacktestEngine",
    "create_event_backtest_engine",
)


@dataclass
class BacktestEventSpec(BacktestSpec):
    """Event-engine backtest specification (mirrors BacktestSpec for now)."""


class EventBacktestEngine:
    """Python entry point for the Rust event-driven backtest engine.

    Falls back to VectorBacktestEngine until the Rust engine is compiled.
    """

    def __init__(self) -> None:
        self._vector = VectorBacktestEngine()
        self._rust = self._load_rust_engine()

    @property
    def available(self) -> bool:
        """True when a Rust-backed event engine is loaded."""
        return self._rust is not None

    def run(self, spec: BacktestEventSpec) -> BacktestResult:
        """Execute a backtest, routing to Rust when available."""
        if self._rust is not None:
            return self._rust.run(spec)
        logger.info("Rust event engine not available; delegating to VectorBacktestEngine")
        return self._vector.run(_to_vector_spec(spec))

    @staticmethod
    def _load_rust_engine() -> Any | None:
        try:
            module = importlib.import_module("cquant_py")
        except ImportError:
            return None

        for name in _RUST_ENTRY_POINTS:
            candidate = getattr(module, name, None)
            if candidate is None:
                continue
            if not isinstance(candidate, type) and hasattr(candidate, "run"):
                return candidate
            if isinstance(candidate, type):
                try:
                    instance = candidate()
                    if hasattr(instance, "run"):
                        return instance
                except TypeError:
                    continue
            if callable(candidate):
                try:
                    instance = candidate()
                    if hasattr(instance, "run"):
                        return instance
                except TypeError:
                    continue
        return None


def _to_vector_spec(spec: BacktestEventSpec) -> BacktestSpec:
    return BacktestSpec(
        strategy=spec.strategy,
        prices=spec.prices,
        start_date=spec.start_date,
        end_date=spec.end_date,
        initial_cash=spec.initial_cash,
        cost_model=spec.cost_model,
        sizer=spec.sizer,
        risk_policies=spec.risk_policies,
        rebalance_frequency=spec.rebalance_frequency,
        benchmark_asset_id=spec.benchmark_asset_id,
        universe_id=spec.universe_id,
        features=spec.features,
        tags={**spec.tags, "event_engine_mode": "vector_fallback"},
    )
