"""cquant.execution.execution_persister — Persist live execution results.

Creates and manages the ``gold_live_executions`` table for recording
live/paper trading execution results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from cquant.datahub.catalog import Catalog
from cquant.execution.broker import Order

logger = logging.getLogger(__name__)

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS gold_live_executions (
    execution_id    VARCHAR PRIMARY KEY,
    live_id         VARCHAR NOT NULL,
    strategy_id     VARCHAR NOT NULL,
    order_id        VARCHAR NOT NULL,
    asset_id        VARCHAR NOT NULL,
    side            VARCHAR NOT NULL,
    qty             INTEGER NOT NULL,
    filled_qty      INTEGER NOT NULL,
    filled_price    DOUBLE NOT NULL,
    commission      DOUBLE DEFAULT 0,
    stamp_duty      DOUBLE DEFAULT 0,
    slippage        DOUBLE DEFAULT 0,
    total_cost      DOUBLE DEFAULT 0,
    status          VARCHAR NOT NULL,
    reject_reason   VARCHAR DEFAULT '',
    executed_at     TIMESTAMP NOT NULL
)
"""

_schema_ensured = False


class ExecutionPersister:
    """Persists live execution results to the catalog.

    Usage::

        persister = ExecutionPersister(catalog)
        persister.persist_order(live_id, strategy_id, order)
    """

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the gold_live_executions table if it doesn't exist."""
        global _schema_ensured
        if _schema_ensured:
            return
        try:
            self._catalog.execute(_TABLE_DDL)
            _schema_ensured = True
        except Exception as exc:
            logger.debug("_ensure_schema: %s", exc)

    def persist_order(self, live_id: str, strategy_id: str, order: Order) -> str:
        """Persist a single order execution result.

        Parameters
        ----------
        live_id:
            The live deployment ID.
        strategy_id:
            The strategy identifier.
        order:
            The executed Order object.

        Returns
        -------
        The execution_id (UUID).
        """
        import uuid as _uuid

        execution_id = str(_uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        self._catalog.execute(
            "INSERT INTO gold_live_executions "
            "(execution_id, live_id, strategy_id, order_id, asset_id, side, "
            "qty, filled_qty, filled_price, commission, stamp_duty, slippage, "
            "total_cost, status, reject_reason, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                execution_id,
                live_id,
                strategy_id,
                order.order_id,
                order.asset_id,
                order.side,
                order.qty,
                order.filled_qty,
                order.filled_price,
                order.commission,
                order.stamp_duty,
                order.slippage,
                order.total_cost,
                order.status.value,
                order.reject_reason,
                now,
            ],
        )

        logger.info(
            "Persisted execution %s: %s %s %d @ %.2f (status=%s)",
            execution_id[:8],
            order.side,
            order.asset_id,
            order.filled_qty,
            order.filled_price,
            order.status.value,
        )
        return execution_id

    def persist_batch(
        self, live_id: str, strategy_id: str, orders: list[Order]
    ) -> list[str]:
        """Persist multiple order execution results.

        Parameters
        ----------
        live_id:
            The live deployment ID.
        strategy_id:
            The strategy identifier.
        orders:
            List of executed Order objects.

        Returns
        -------
        List of execution_ids.
        """
        return [
            self.persist_order(live_id, strategy_id, order)
            for order in orders
        ]

    def get_executions(
        self,
        live_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Retrieve execution history for a live deployment.

        Parameters
        ----------
        live_id:
            The live deployment ID.
        limit:
            Max rows to return.
        offset:
            Row offset for pagination.

        Returns
        -------
        Dict with keys: items (list), total (int).
        """
        count_df = self._catalog.query(
            "SELECT COUNT(*) AS cnt FROM gold_live_executions WHERE live_id = ?",
            [live_id],
        )
        total = count_df["cnt"][0] if not count_df.is_empty() else 0

        df = self._catalog.query(
            "SELECT execution_id, live_id, strategy_id, order_id, asset_id, "
            "side, qty, filled_qty, filled_price, commission, stamp_duty, "
            "slippage, total_cost, status, reject_reason, executed_at "
            "FROM gold_live_executions WHERE live_id = ? "
            "ORDER BY executed_at DESC LIMIT ? OFFSET ?",
            [live_id, limit, offset],
        )

        return {
            "items": df.to_dicts() if not df.is_empty() else [],
            "total": total,
        }
