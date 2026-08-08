"""cquant.scheduler.cleanup — Gold table retention / cleanup.

Two independent retention policies:

1. ``cleanup_run_scoped`` — cascade-delete data tied to expired backtest runs.
   Driven by ``gold_backtest_runs.completed_at``. The run_id is propagated from
   the runs table into the run-scoped gold tables, so deleting an expired run
   also removes its fills / snapshots / risk rows.

   IMPORTANT — *shared* caches are deliberately excluded:
   - ``gold_factor_values`` — keyed by ``feature_set_version`` (PIT factor cache,
     reused across many runs).
   - ``gold_signals``         — keyed by ``signal_set_version`` (no ``run_id``).
   - ``gold_predictions``     — keyed by ``model_version``    (no ``run_id``).
   These are never deleted by run_id; ``cleanup_factor_cache`` handles the
   factor cache independently by version age.

2. ``cleanup_factor_cache`` — keep only the *N* newest ``feature_set_version``
   slices in ``gold_factor_values``, evicting the oldest.

Both methods are safe to call on a catalog whose gold tables do not yet exist
(e.g. fresh DB) — missing tables are skipped with a debug log.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Run-scoped gold tables that carry a ``run_id`` column. Order matters only for
# readability (deletion is by run_id equality, no FK ordering required in DuckDB).
# gold_factor_values / gold_signals / gold_predictions are intentionally absent
# — they are version-scoped shared caches, not run-scoped.
RUN_SCOPED_GOLD_TABLES: list[str] = [
    "gold_fills",
    "gold_portfolio_snapshots",
    "gold_pretrade_decisions",
    "gold_risk_snapshots",
    "gold_risk_budgets",
    "gold_risk_rolling",
    "gold_drawdown_periods",
]

# gold_bt_analysis_runs links back to a run via ``backtest_run_id`` (different
# column name) — handled separately from RUN_SCOPED_GOLD_TABLES.
BT_ANALYSIS_TABLE = "gold_bt_analysis_runs"

RUNS_TABLE = "gold_backtest_runs"
FACTOR_CACHE_TABLE = "gold_factor_values"


class GoldTableCleaner:
    """Retention/cleanup for the gold mart layer.

    Parameters
    ----------
    catalog
        An initialised ``Catalog`` instance exposing ``query``/``execute``.
    """

    def __init__(self, catalog: Any) -> None:
        self._catalog = catalog

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _table_exists(self, table: str) -> bool:
        """Return True if *table* exists in the catalog (best-effort)."""
        try:
            df = self._catalog.query(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name = ?",
                [table],
            )
            return not df.is_empty()
        except Exception:
            # Fallback: introspect via duckdb_tables() for newer DuckDB versions.
            try:
                df = self._catalog.query(
                    "SELECT table_name FROM duckdb_tables() WHERE table_name = ?",
                    [table],
                )
                return not df.is_empty()
            except Exception:
                logger.debug("Could not determine existence of %s", table, exc_info=True)
                return False

    def _exec(self, sql: str, params: list[Any] | None = None) -> None:
        """Execute a statement, swallowing nothing (errors propagate)."""
        if params is None:
            self._catalog.execute(sql)
        else:
            self._catalog.execute(sql, params)

    # ------------------------------------------------------------------
    # run-scoped cascade cleanup
    # ------------------------------------------------------------------
    def cleanup_run_scoped(self, catalog: Any | None = None, retention_days: int = 90) -> dict[str, int]:
        """Cascade-delete run-scoped gold data older than ``retention_days``.

        Resolution order:
        1. Select ``run_id`` from ``gold_backtest_runs`` where
           ``completed_at < now() - retention_days``.
        2. Delete matching rows from each run-scoped table by ``run_id``.
        3. Delete from ``gold_bt_analysis_runs`` via ``backtest_run_id``.
        4. Delete the runs themselves from ``gold_backtest_runs``.
        5. ``VACUUM`` to reclaim disk space.

        Parameters
        ----------
        catalog
            Optional catalog override (defaults to the one passed at init).
        retention_days
            Number of days a completed run is retained. Runs whose
            ``completed_at`` is older than ``now() - retention_days`` are
            removed. ``NULL`` completed_at rows are treated as still running
            (never expired).

        Returns
        -------
        dict[str, int]
            ``{table_name: rows_deleted}`` summary. Includes an ``"_expired_runs"``
            entry with the count of runs selected for deletion and
            ``"_vacuumed"`` set to 1 if VACUUM ran.
        """
        cat = catalog if catalog is not None else self._catalog
        summary: dict[str, int] = {}

        if not self._table_exists_with(cat, RUNS_TABLE):
            logger.debug("cleanup_run_scoped: %s missing, nothing to do", RUNS_TABLE)
            return summary

        # 1. Identify expired run_ids.
        expired_df = cat.query(
            f"SELECT run_id FROM {RUNS_TABLE} "
            "WHERE completed_at IS NOT NULL "
            f"  AND completed_at < (now() - INTERVAL '{int(retention_days)} days')"
        )
        if expired_df.is_empty():
            logger.info(
                "cleanup_run_scoped: no runs older than %d days, nothing to delete",
                retention_days,
            )
            return summary

        expired_runs = expired_df["run_id"].to_list()
        n_runs = len(expired_runs)
        summary["_expired_runs"] = n_runs
        logger.info(
            "cleanup_run_scoped: %d runs expired (retention=%d days)",
            n_runs, retention_days,
        )

        # 2. Delete from each run-scoped table.
        for table in RUN_SCOPED_GOLD_TABLES:
            if not self._table_exists_with(cat, table):
                continue
            deleted = self._delete_run_ids(cat, table, "run_id", expired_runs)
            summary[table] = deleted
            if deleted:
                logger.info("cleanup_run_scoped: %s — %d rows deleted", table, deleted)

        # 3. gold_bt_analysis_runs (linked via backtest_run_id).
        if self._table_exists_with(cat, BT_ANALYSIS_TABLE):
            deleted = self._delete_run_ids(cat, BT_ANALYSIS_TABLE, "backtest_run_id", expired_runs)
            summary[BT_ANALYSIS_TABLE] = deleted
            if deleted:
                logger.info(
                    "cleanup_run_scoped: %s — %d rows deleted", BT_ANALYSIS_TABLE, deleted
                )

        # 4. Delete the run rows themselves.
        self._delete_run_ids(cat, RUNS_TABLE, "run_id", expired_runs)
        summary[RUNS_TABLE] = n_runs
        logger.info("cleanup_run_scoped: %s — %d run rows deleted", RUNS_TABLE, n_runs)

        # 5. VACUUM to reclaim space.
        try:
            cat.execute("VACUUM")
            summary["_vacuumed"] = 1
            logger.info("cleanup_run_scoped: VACUUM completed")
        except Exception as exc:
            summary["_vacuumed"] = 0
            logger.warning("cleanup_run_scoped: VACUUM failed: %s", exc)

        return summary

    # ------------------------------------------------------------------
    # factor cache cleanup (version-scoped, NOT run-scoped)
    # ------------------------------------------------------------------
    def cleanup_factor_cache(self, catalog: Any | None = None, keep_versions: int = 10) -> dict[str, int]:
        """Evict the oldest ``feature_set_version`` slices from the factor cache.

        ``gold_factor_values`` is keyed by ``feature_set_version`` and shared
        across many backtest runs (PIT factor cache). It is cleaned by *version
        age* rather than by run_id: the newest ``keep_versions`` versions are
        preserved; older versions are deleted wholesale.

        Parameters
        ----------
        catalog
            Optional catalog override.
        keep_versions
            Number of newest ``feature_set_version`` slices to keep.

        Returns
        -------
        dict[str, int]
            ``{"versions_evicted": n, "rows_deleted": m, "_vacuumed": 0|1}``.
        """
        cat = catalog if catalog is not None else self._catalog

        if not self._table_exists_with(cat, FACTOR_CACHE_TABLE):
            logger.debug("cleanup_factor_cache: %s missing, nothing to do", FACTOR_CACHE_TABLE)
            return {"versions_evicted": 0, "rows_deleted": 0}

        versions_df = cat.query(
            f"SELECT feature_set_version "
            f"FROM {FACTOR_CACHE_TABLE} "
            f"GROUP BY feature_set_version "
            f"ORDER BY MAX(asof_ts) DESC"
        )
        if versions_df.is_empty():
            logger.info("cleanup_factor_cache: factor cache empty, nothing to do")
            return {"versions_evicted": 0, "rows_deleted": 0}

        all_versions = versions_df["feature_set_version"].to_list()
        if len(all_versions) <= keep_versions:
            logger.info(
                "cleanup_factor_cache: %d versions <= keep_versions=%d, nothing to evict",
                len(all_versions), keep_versions,
            )
            return {"versions_evicted": 0, "rows_deleted": 0}

        # Newest kept; everything older is evicted.
        evict = all_versions[keep_versions:]
        logger.info(
            "cleanup_factor_cache: evicting %d of %d versions (keep=%d)",
            len(evict), len(all_versions), keep_versions,
        )

        # Build a parameterised IN-list once and reuse.
        placeholders = ", ".join(["?"] * len(evict))
        del_sql = (
            f"DELETE FROM {FACTOR_CACHE_TABLE} "
            f"WHERE feature_set_version IN ({placeholders})"
        )
        # Count rows before deleting for the summary.
        count_df = cat.query(
            f"SELECT COUNT(*) AS cnt FROM {FACTOR_CACHE_TABLE} "
            f"WHERE feature_set_version IN ({placeholders})",
            evict,
        )
        rows_deleted = int(count_df["cnt"][0]) if not count_df.is_empty() else 0

        cat.execute(del_sql, evict)
        logger.info(
            "cleanup_factor_cache: evicted %d versions, %d rows",
            len(evict), rows_deleted,
        )

        summary = {"versions_evicted": len(evict), "rows_deleted": rows_deleted}

        try:
            cat.execute("VACUUM")
            summary["_vacuumed"] = 1
            logger.info("cleanup_factor_cache: VACUUM completed")
        except Exception as exc:
            summary["_vacuumed"] = 0
            logger.warning("cleanup_factor_cache: VACUUM failed: %s", exc)

        return summary

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _table_exists_with(self, cat: Any, table: str) -> bool:
        """Existence check using an explicit catalog (module-level helper
        is bound to ``self._catalog``; pass-through used during overrides)."""
        try:
            df = cat.query(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name = ?",
                [table],
            )
            return not df.is_empty()
        except Exception:
            try:
                df = cat.query(
                    "SELECT table_name FROM duckdb_tables() WHERE table_name = ?",
                    [table],
                )
                return not df.is_empty()
            except Exception:
                logger.debug("Could not determine existence of %s", table, exc_info=True)
                return False

    def _delete_run_ids(
        self, cat: Any, table: str, column: str, run_ids: list[str]
    ) -> int:
        """Delete rows where ``column`` matches any of ``run_ids``.

        Returns the number of rows deleted. Uses a parameterised IN-list. If the
        catalog does not support a row-count return from DELETE, falls back to a
        before/after COUNT.
        """
        if not run_ids:
            return 0
        placeholders = ", ".join(["?"] * len(run_ids))
        # Count before delete (DuckDB doesn't reliably return affected rows via execute).
        count_df = cat.query(
            f"SELECT COUNT(*) AS cnt FROM {table} WHERE {column} IN ({placeholders})",
            run_ids,
        )
        before = int(count_df["cnt"][0]) if not count_df.is_empty() else 0
        if before == 0:
            return 0
        cat.execute(
            f"DELETE FROM {table} WHERE {column} IN ({placeholders})",
            run_ids,
        )
        return before
