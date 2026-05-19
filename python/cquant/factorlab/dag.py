"""DAG-based factor execution engine."""
from __future__ import annotations

import logging
from collections import deque

import polars as pl

from cquant.factorlab.factor import Factor, FactorContext

logger = logging.getLogger(__name__)


class DAGPipeline:
    """Execute factors in dependency order using topological sort.

    Each factor can declare `dependencies` (list of factor names it needs).
    The pipeline sorts factors topologically and executes in order, injecting
    computed columns into the frame so dependent factors can use them.

    Parameters:
        factors: List of Factor instances.
        strict: If True, raise on missing dependencies. If False, skip factors with missing deps.
    """

    def __init__(self, factors: list[Factor], strict: bool = False) -> None:
        self._factors = {f.name: f for f in factors}
        self._strict = strict
        self._order = self._topological_sort()

    def execution_order(self) -> list[str]:
        """Return factor names in topological execution order."""
        return list(self._order)

    def run(self, frame: pl.DataFrame, ctx: FactorContext) -> pl.DataFrame:
        """Execute all factors in dependency order and return enriched frame."""
        result = frame.clone()
        available: set[str] = set(frame.columns)
        skipped: list[str] = []

        for fname in self._order:
            factor = self._factors[fname]
            deps = getattr(factor, "dependencies", [])
            missing_deps = [d for d in deps if d not in available]

            if missing_deps:
                if self._strict:
                    raise ValueError(
                        f"Factor '{fname}' has missing dependencies: {missing_deps}"
                    )
                logger.warning(
                    "Skipping factor '%s': missing dependencies %s", fname, missing_deps
                )
                skipped.append(fname)
                continue

            try:
                series = factor.safe_compute(result, ctx)
                result = result.with_columns(series.alias(fname))
                available.add(fname)
            except Exception as exc:
                logger.error("Factor '%s' failed: %s", fname, exc)
                if self._strict:
                    raise
                result = result.with_columns(pl.lit(None).cast(pl.Float64).alias(fname))

        if skipped:
            logger.info("Skipped factors (missing deps): %s", skipped)

        return result

    def _topological_sort(self) -> list[str]:
        """Kahn's algorithm for topological sort with cycle detection."""
        in_degree: dict[str, int] = {name: 0 for name in self._factors}
        dependents: dict[str, list[str]] = {name: [] for name in self._factors}

        for name, factor in self._factors.items():
            deps = getattr(factor, "dependencies", [])
            for dep in deps:
                if dep in self._factors:
                    dependents[dep].append(name)
                    in_degree[name] += 1

        # Kahn's algorithm
        queue = deque(name for name, deg in in_degree.items() if deg == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for dependent in dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(self._factors):
            cycle_names = [n for n in self._factors if n not in order]
            raise ValueError(f"Dependency cycle detected involving: {cycle_names}")

        return order
