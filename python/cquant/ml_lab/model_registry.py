"""cquant.ml_lab.model_registry — Model lifecycle registry.

Manages model lifecycle stages: staging -> production -> archived.
Uses the ``meta_model_registry`` DuckDB table for persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)

# Valid lifecycle stages
VALID_STAGES = ("staging", "production", "archived")

_DDL = """
CREATE TABLE IF NOT EXISTS meta_model_registry (
    model_id        VARCHAR NOT NULL,
    model_version   VARCHAR NOT NULL,
    trainer_name    VARCHAR NOT NULL,
    artifact_path   VARCHAR NOT NULL DEFAULT '',
    feature_set_version VARCHAR NOT NULL DEFAULT '',
    target_name     VARCHAR NOT NULL DEFAULT '',
    stage           VARCHAR NOT NULL DEFAULT 'staging',
    metrics_json    VARCHAR NOT NULL DEFAULT '{}',
    description     VARCHAR NOT NULL DEFAULT '',
    registered_at   TIMESTAMP NOT NULL,
    promoted_at     TIMESTAMP,
    archived_at     TIMESTAMP,
    PRIMARY KEY (model_id, model_version)
);
"""


class ModelRegistry:
    """Manages model lifecycle stages (staging -> production -> archived).

    Parameters
    ----------
    catalog
        An initialised ``Catalog`` (DuckDB) instance.
    """

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        # Ensure table exists
        self._catalog.execute(_DDL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        model_id: str,
        model_version: str,
        trainer_name: str,
        artifact_path: str = "",
        feature_set_version: str = "",
        target_name: str = "",
        metrics: dict[str, Any] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Register a new model version in *staging* stage.

        Returns the created registry row as a dict.
        """
        import json

        now = datetime.now(tz=timezone.utc).isoformat()
        metrics_json = json.dumps(metrics or {})

        # Check if model already exists — reject if not in staging
        existing = self._get_row(model_id, model_version)
        if existing is not None and existing.get("stage") != "staging":
            raise ValueError(
                f"Model {model_id}/{model_version} already exists in "
                f"'{existing['stage']}' stage. Only staging models can be re-registered."
            )

        self._catalog.execute(
            """INSERT OR REPLACE INTO meta_model_registry
               (model_id, model_version, trainer_name, artifact_path,
                feature_set_version, target_name, stage, metrics_json,
                description, registered_at, promoted_at, archived_at)
               VALUES (?, ?, ?, ?, ?, ?, 'staging', ?, ?, ?, NULL, NULL)""",
            [
                model_id, model_version, trainer_name, artifact_path,
                feature_set_version, target_name, metrics_json,
                description, now,
            ],
        )

        logger.info("Registered model %s/%s in staging", model_id, model_version)
        return {
            "model_id": model_id,
            "model_version": model_version,
            "stage": "staging",
            "registered_at": now,
        }

    def promote(self, model_id: str, model_version: str) -> dict[str, Any]:
        """Promote a model version to *production*.

        Any existing production model with the same ``model_id`` is demoted
        to *archived* before the promotion.
        """
        # Verify the model exists
        row = self._get_row(model_id, model_version)
        if row is None:
            raise ValueError(f"Model {model_id}/{model_version} not found in registry")

        now = datetime.now(tz=timezone.utc).isoformat()

        # Atomic demote + promote in a single transaction
        self._catalog.execute("BEGIN")
        try:
            self._catalog.execute(
                """UPDATE meta_model_registry
                   SET stage = 'archived', archived_at = ?
                   WHERE model_id = ? AND stage = 'production'""",
                [now, model_id],
            )
            self._catalog.execute(
                """UPDATE meta_model_registry
                   SET stage = 'production', promoted_at = ?
                   WHERE model_id = ? AND model_version = ?""",
                [now, model_id, model_version],
            )
            self._catalog.execute("COMMIT")
        except Exception:
            self._catalog.execute("ROLLBACK")
            raise

        logger.info("Promoted model %s/%s to production", model_id, model_version)
        return {
            "model_id": model_id,
            "model_version": model_version,
            "stage": "production",
            "promoted_at": now,
        }

    def archive(self, model_id: str, model_version: str) -> dict[str, Any]:
        """Move a model version to *archived* stage."""
        row = self._get_row(model_id, model_version)
        if row is None:
            raise ValueError(f"Model {model_id}/{model_version} not found in registry")

        now = datetime.now(tz=timezone.utc).isoformat()
        self._catalog.execute(
            """UPDATE meta_model_registry
               SET stage = 'archived', archived_at = ?
               WHERE model_id = ? AND model_version = ?""",
            [now, model_id, model_version],
        )

        logger.info("Archived model %s/%s", model_id, model_version)
        return {
            "model_id": model_id,
            "model_version": model_version,
            "stage": "archived",
            "archived_at": now,
        }

    def get_production(self, model_id: str) -> dict[str, Any] | None:
        """Return the current production model for *model_id*, or ``None``."""
        import json

        df = self._catalog.query(
            """SELECT * FROM meta_model_registry
               WHERE model_id = ? AND stage = 'production'
               LIMIT 1""",
            [model_id],
        )
        if df.is_empty():
            return None
        row = df.to_dicts()[0]
        row["metrics"] = json.loads(row.get("metrics_json", "{}"))
        return row

    def list_models(
        self,
        stage: str | None = None,
        model_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models, optionally filtered by stage and/or model_id."""
        import json

        clauses: list[str] = []
        params: list[Any] = []
        if stage:
            clauses.append("stage = ?")
            params.append(stage)
        if model_id:
            clauses.append("model_id = ?")
            params.append(model_id)

        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        df = self._catalog.query(
            f"SELECT * FROM meta_model_registry {where} ORDER BY registered_at DESC",
            params,
        )
        if df.is_empty():
            return []
        rows = df.to_dicts()
        for row in rows:
            row["metrics"] = json.loads(row.get("metrics_json", "{}"))
        return rows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_row(self, model_id: str, model_version: str) -> dict[str, Any] | None:
        df = self._catalog.query(
            "SELECT * FROM meta_model_registry WHERE model_id = ? AND model_version = ?",
            [model_id, model_version],
        )
        if df.is_empty():
            return None
        return df.to_dicts()[0]
