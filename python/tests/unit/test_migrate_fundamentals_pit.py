"""Tests for scripts/migrate_fundamentals_pit.py — announce_date backfill."""
from __future__ import annotations

from datetime import date


from cquant.datahub.backends.duckdb_backend import DuckDBBackend
from cquant.datahub.catalog import Catalog


def _memory_catalog() -> Catalog:
    """Create a Catalog backed by an in-memory DuckDB instance."""
    backend = DuckDBBackend.__new__(DuckDBBackend)
    import duckdb as _duckdb

    backend._conn = _duckdb.connect(":memory:")
    cat = Catalog.__new__(Catalog)
    cat._backend = backend
    cat._db_path = None  # type: ignore[assignment]
    return cat


def _create_table(cat: Catalog) -> None:
    cat.execute("""
        CREATE TABLE silver_fundamentals (
            asset_id      VARCHAR,
            report_date   DATE,
            announce_date DATE,
            revenue       DOUBLE
        )
    """)


# ---------------------------------------------------------------------------
# Tier-correctness tests
# ---------------------------------------------------------------------------

class TestTierCorrectness:
    """announce_date should follow the tier-based offset rules."""

    def test_annual_report_plus_120d(self) -> None:
        cat = _memory_catalog()
        _create_table(cat)
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SSE:600036', DATE '2024-12-31', NULL, 100.0)"
        )
        from scripts.migrate_fundamentals_pit import migrate

        migrate(cat)

        row = cat.query("SELECT announce_date FROM silver_fundamentals")
        assert row["announce_date"][0] == date(2025, 4, 30)

    def test_q1_plus_45d(self) -> None:
        cat = _memory_catalog()
        _create_table(cat)
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SSE:600036', DATE '2024-03-31', NULL, 100.0)"
        )
        from scripts.migrate_fundamentals_pit import migrate

        migrate(cat)

        row = cat.query("SELECT announce_date FROM silver_fundamentals")
        assert row["announce_date"][0] == date(2024, 5, 15)

    def test_h1_plus_90d(self) -> None:
        cat = _memory_catalog()
        _create_table(cat)
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SSE:600036', DATE '2024-06-30', NULL, 100.0)"
        )
        from scripts.migrate_fundamentals_pit import migrate

        migrate(cat)

        row = cat.query("SELECT announce_date FROM silver_fundamentals")
        assert row["announce_date"][0] == date(2024, 9, 28)

    def test_q3_plus_45d(self) -> None:
        cat = _memory_catalog()
        _create_table(cat)
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SSE:600036', DATE '2024-09-30', NULL, 100.0)"
        )
        from scripts.migrate_fundamentals_pit import migrate

        migrate(cat)

        row = cat.query("SELECT announce_date FROM silver_fundamentals")
        assert row["announce_date"][0] == date(2024, 11, 14)


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Running migrate() twice must not overwrite existing announce_date values."""

    def test_existing_announce_date_preserved(self) -> None:
        cat = _memory_catalog()
        _create_table(cat)
        # Row with existing announce_date — should NOT be overwritten.
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SSE:600036', DATE '2024-12-31', DATE '2025-03-01', 100.0)"
        )
        # Row with NULL announce_date — should be filled.
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SZSE:000001', DATE '2024-03-31', NULL, 200.0)"
        )

        from scripts.migrate_fundamentals_pit import migrate

        migrate(cat)
        migrate(cat)  # second call — idempotency check

        rows = cat.query(
            "SELECT asset_id, announce_date FROM silver_fundamentals ORDER BY asset_id"
        )

        # Existing value preserved.
        assert rows["announce_date"][0] == date(2025, 3, 1)
        # NULL value filled.
        assert rows["announce_date"][1] == date(2024, 5, 15)

    def test_no_null_remaining_after_migration(self) -> None:
        cat = _memory_catalog()
        _create_table(cat)
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SSE:600036', DATE '2024-06-30', NULL, 100.0)"
        )
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SZSE:000001', DATE '2024-09-30', NULL, 200.0)"
        )

        from scripts.migrate_fundamentals_pit import migrate

        migrate(cat)

        remaining = cat.query(
            "SELECT COUNT(*) AS n FROM silver_fundamentals WHERE announce_date IS NULL"
        )
        assert remaining["n"][0] == 0

    def test_skip_when_nothing_to_migrate(self) -> None:
        """migrate() should be a no-op when all rows already have announce_date."""
        cat = _memory_catalog()
        _create_table(cat)
        cat.execute(
            "INSERT INTO silver_fundamentals VALUES ('SSE:600036', DATE '2024-12-31', DATE '2025-04-30', 100.0)"
        )

        from scripts.migrate_fundamentals_pit import migrate

        migrate(cat)  # should not raise

        row = cat.query("SELECT announce_date FROM silver_fundamentals")
        assert row["announce_date"][0] == date(2025, 4, 30)
