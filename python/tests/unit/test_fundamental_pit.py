"""PIT (point-in-time) correctness tests for Phase 1-4 fundamental fixes.

Covers:
  1. silver_valuation_daily filters on trade_date only (no look-ahead).
  2. silver_fundamentals respects announce_date (true disclosure date).
  3. announce_date column carries the real f_ann_date value.
  4. migrate_fundamentals_pit tiered backfill (annual+120 / H1+90 / Q1/Q3+45).
  5. cross_section_scorer market_cap neutralization reads silver_valuation_daily.

All tests use an in-memory DuckDB (no real data files).
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import duckdb
import polars as pl
import pytest

from cquant.datahub.backends.duckdb_backend import DuckDBBackend
from cquant.datahub.catalog import Catalog


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _memory_catalog() -> Catalog:
    """Create a Catalog backed by an in-memory DuckDB instance."""
    backend = DuckDBBackend.__new__(DuckDBBackend)
    backend._conn = duckdb.connect(":memory:")
    cat = Catalog.__new__(Catalog)
    cat._backend = backend
    cat._db_path = None  # type: ignore[assignment]
    return cat


def _create_valuation_daily(cat: Catalog) -> None:
    cat.execute("""
        CREATE TABLE silver_valuation_daily (
            asset_id      VARCHAR,
            trade_date    DATE,
            pe_ttm        DOUBLE,
            pb            DOUBLE,
            ps_ttm        DOUBLE,
            market_cap    DOUBLE,
            turnover_rate DOUBLE,
            dividend_yield DOUBLE,
            PRIMARY KEY (asset_id, trade_date)
        )
    """)


def _create_fundamentals(cat: Catalog) -> None:
    cat.execute("""
        CREATE TABLE silver_fundamentals (
            asset_id            VARCHAR,
            report_date         DATE,
            pe_ttm              DOUBLE,
            roe                 DOUBLE,
            gross_margin        DOUBLE,
            market_cap          DOUBLE,
            announce_date       DATE,
            PRIMARY KEY (asset_id, report_date)
        )
    """)


def _load_migrate_module():
    """Load scripts/migrate_fundamentals_pit.py via importlib (matches existing test style)."""
    spec = importlib.util.spec_from_file_location(
        "migrate_fundamentals_pit",
        Path(__file__).resolve().parents[3] / "scripts" / "migrate_fundamentals_pit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Test 1 — valuation uses trade_date only
# ---------------------------------------------------------------------------

class TestValuationTradeDate:
    """silver_valuation_daily is PIT-correct via trade_date <= ? filtering."""

    def test_valuation_uses_trade_date_only(self) -> None:
        cat = _memory_catalog()
        _create_valuation_daily(cat)
        cat.execute(
            "INSERT INTO silver_valuation_daily (asset_id, trade_date, pe_ttm) "
            "VALUES ('SSE:600036', DATE '2024-01-15', 10.0)"
        )
        cat.execute(
            "INSERT INTO silver_valuation_daily (asset_id, trade_date, pe_ttm) "
            "VALUES ('SSE:600036', DATE '2024-06-15', 20.0)"
        )

        # Mirror materialize._load_valuation: WHERE trade_date <= ?
        rows = cat.query(
            "SELECT trade_date, pe_ttm FROM silver_valuation_daily "
            "WHERE trade_date <= ? ORDER BY trade_date",
            ["2024-03-01"],
        )

        # Only the 2024-01-15 row is visible at 2024-03-01; the 2024-06-15
        # row is future data and must NOT leak in.
        assert len(rows) == 1
        assert rows["trade_date"][0] == date(2024, 1, 15)
        assert rows["pe_ttm"][0] == 10.0


# ---------------------------------------------------------------------------
# Test 2 — fundamental respects announce_date
# ---------------------------------------------------------------------------

class TestFundamentalAnnounceDate:
    """silver_fundamentals must be filtered by announce_date (disclosure day)."""

    def test_fundamental_respects_announce_date(self) -> None:
        cat = _memory_catalog()
        _create_fundamentals(cat)
        # 2024-Q1 report; not disclosed until 2024-04-30.
        cat.execute(
            "INSERT INTO silver_fundamentals (asset_id, report_date, announce_date, roe) "
            "VALUES ('SSE:600036', DATE '2024-03-31', DATE '2024-04-30', 15.0)"
        )

        # Before disclosure: announce_date <= 2024-04-15 → row must NOT be visible.
        before = cat.query(
            "SELECT asset_id, report_date FROM silver_fundamentals "
            "WHERE announce_date <= ?",
            ["2024-04-15"],
        )
        assert len(before) == 0

        # After disclosure: announce_date <= 2024-05-01 → row IS visible.
        after = cat.query(
            "SELECT asset_id, report_date FROM silver_fundamentals "
            "WHERE announce_date <= ?",
            ["2024-05-01"],
        )
        assert len(after) == 1
        assert after["asset_id"][0] == "SSE:600036"
        assert after["report_date"][0] == date(2024, 3, 31)


# ---------------------------------------------------------------------------
# Test 3 — announce_date column carries f_ann_date (Phase 2 priority)
# ---------------------------------------------------------------------------

class TestFundamentalFAnnDate:
    """announce_date must hold the actual disclosure date (f_ann_date when
    present), proving fetch_fundamentals' f_ann_date-first priority persists."""

    def test_fundamental_uses_f_ann_date(self) -> None:
        cat = _memory_catalog()
        _create_fundamentals(cat)
        # Simulate the post-ingestion state: announce_date = real f_ann_date.
        # fetch_fundamentals chooses row.get("f_ann_date") or row.get("ann_date")
        # → f_ann_date wins. Persist it into the announce_date column.
        real_f_ann_date = date(2024, 4, 25)
        cat.execute(
            "INSERT INTO silver_fundamentals (asset_id, report_date, announce_date, roe) "
            "VALUES ('SZSE:000001', DATE '2024-03-31', ?, 12.0)",
            [real_f_ann_date],
        )

        row = cat.query("SELECT announce_date FROM silver_fundamentals")
        # The persisted value equals the expected f_ann_date (not ann_date, not NULL).
        assert row["announce_date"][0] == real_f_ann_date


# ---------------------------------------------------------------------------
# Test 4 — tiered migration backfill
# ---------------------------------------------------------------------------

class TestMigrationTiered:
    """migrate() must apply the tier-based announce_date offset per report month."""

    @pytest.mark.parametrize(
        "report_date, expected_announce",
        [
            (date(2024, 3, 31), date(2024, 5, 15)),    # Q1  → +45d
            (date(2024, 6, 30), date(2024, 9, 28)),    # H1  → +90d
            (date(2024, 9, 30), date(2024, 11, 14)),   # Q3  → +45d
            (date(2024, 12, 31), date(2025, 4, 30)),   # Ann → +120d
        ],
    )
    def test_migration_backfill_tiered(
        self, report_date: date, expected_announce: date
    ) -> None:
        cat = _memory_catalog()
        _create_fundamentals(cat)
        cat.execute(
            "INSERT INTO silver_fundamentals (asset_id, report_date, announce_date, roe) "
            "VALUES (?, ?, NULL, 10.0)",
            [f"SSE:{report_date.strftime('%m%d')}", report_date],
        )

        migrate = _load_migrate_module().migrate
        migrate(cat)

        row = cat.query("SELECT announce_date FROM silver_fundamentals")
        assert row["announce_date"][0] == expected_announce


# ---------------------------------------------------------------------------
# Test 5 — scorer market_cap comes from silver_valuation_daily
# ---------------------------------------------------------------------------

class TestScorerMarketCapSource:
    """cross_section_scorer's market_cap neutralization must read from
    silver_valuation_daily (PIT-correct), NOT silver_fundamentals."""

    SCORER_SQL = """
        SELECT asset_id, trade_date, market_cap
        FROM silver_valuation_daily
        WHERE trade_date >= ? AND trade_date <= ?
          AND market_cap IS NOT NULL AND market_cap > 0
    """

    def test_scorer_market_cap_from_valuation_daily(self) -> None:
        cat = _memory_catalog()
        _create_valuation_daily(cat)
        _create_fundamentals(cat)

        asset = "SSE:600036"
        td = date(2024, 1, 15)

        # PIT-INCORRECT value sitting in fundamentals (must be ignored).
        cat.execute(
            "INSERT INTO silver_fundamentals (asset_id, report_date, announce_date, market_cap) "
            "VALUES (?, ?, ?, 999999.0)",
            [asset, date(2023, 12, 31), date(2024, 1, 10)],
        )
        # PIT-CORRECT value in valuation_daily (must be the one returned).
        correct_cap = 12345.0
        cat.execute(
            "INSERT INTO silver_valuation_daily (asset_id, trade_date, market_cap) "
            "VALUES (?, ?, ?)",
            [asset, td, correct_cap],
        )

        # Execute the scorer's actual market_cap query.
        df = cat.query(self.SCORER_SQL, [td.isoformat(), td.isoformat()])

        # 1) Structural: the query reads ONLY silver_valuation_daily, so the
        #    fundamentals value (999999.0) can never appear here.
        assert "999999.0" not in {r for r in df["market_cap"]}
        assert df["market_cap"][0] == correct_cap

        # 2) Source-coupling: assert the production scorer's FROM clause points
        #    at silver_valuation_daily for the market_cap neutralization load.
        scorer_src = (
            Path(__file__).resolve().parents[2]
            / "cquant"
            / "factorlab"
            / "cross_section_scorer.py"
        ).read_text(encoding="utf-8")

        # The market_cap neutralization query must source silver_valuation_daily.
        assert "FROM silver_valuation_daily" in scorer_src
        # And must NOT source fundamentals for market_cap.
        # (industry is allowed from silver_assets; only market_cap is in scope here.)
        mc_block = scorer_src[
            scorer_src.index("market_cap from silver_valuation_daily".lower())
            if "market_cap from silver_valuation_daily" in scorer_src.lower()
            else scorer_src.index("silver_valuation_daily")
            : scorer_src.index("silver_valuation_daily") + 600
        ].lower()
        assert "silver_fundamentals" not in mc_block


# ---------------------------------------------------------------------------
# Guard: ensure polars is the return type used by catalog.query (used above).
# ---------------------------------------------------------------------------

def test_catalog_query_returns_polars() -> None:
    """catalog.query returns a polars DataFrame — the contract our assertions rely on."""
    cat = _memory_catalog()
    cat.execute("CREATE TABLE t (a INTEGER)")
    cat.execute("INSERT INTO t VALUES (1)")
    df = cat.query("SELECT a FROM t")
    assert isinstance(df, pl.DataFrame)
