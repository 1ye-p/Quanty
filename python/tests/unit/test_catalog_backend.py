"""Tests for Catalog backend abstraction."""
from __future__ import annotations

import pytest


class TestDuckDBBackend:
    def test_query_returns_polars(self):
        from cquant.datahub.backends.duckdb_backend import DuckDBBackend
        backend = DuckDBBackend(":memory:")
        result = backend.query("SELECT 1 AS val")
        assert result["val"][0] == 1
        backend.close()

    def test_execute_and_query(self):
        from cquant.datahub.backends.duckdb_backend import DuckDBBackend
        backend = DuckDBBackend(":memory:")
        backend.execute("CREATE TABLE test (id INT, name VARCHAR)")
        backend.execute("INSERT INTO test VALUES (1, 'hello')")
        result = backend.query("SELECT * FROM test")
        assert len(result) == 1
        assert result["name"][0] == "hello"
        backend.close()

    def test_upsert(self):
        from cquant.datahub.backends.duckdb_backend import DuckDBBackend
        backend = DuckDBBackend(":memory:")
        backend.execute("CREATE TABLE test (id INT PRIMARY KEY, name VARCHAR)")
        backend.upsert("test", ["id", "name"], [(1, "a")], ["id"])
        backend.upsert("test", ["id", "name"], [(1, "b")], ["id"])
        result = backend.query("SELECT * FROM test")
        assert len(result) == 1
        assert result["name"][0] == "b"
        backend.close()

    def test_executemany(self):
        from cquant.datahub.backends.duckdb_backend import DuckDBBackend
        backend = DuckDBBackend(":memory:")
        backend.execute("CREATE TABLE test (id INT, name VARCHAR)")
        backend.executemany("INSERT INTO test VALUES (?, ?)", [(1, "a"), (2, "b")])
        result = backend.query("SELECT * FROM test ORDER BY id")
        assert len(result) == 2
        backend.close()


class TestCatalogFactory:
    def test_default_creates_duckdb(self):
        from cquant.datahub.catalog import Catalog
        catalog = Catalog(db_path=":memory:")
        result = catalog.query("SELECT 1 AS val")
        assert result["val"][0] == 1
        catalog.close()

    def test_upsert_through_catalog(self):
        from cquant.datahub.catalog import Catalog
        catalog = Catalog(db_path=":memory:")
        catalog.execute("CREATE TABLE test (id INT PRIMARY KEY, name VARCHAR)")
        catalog.upsert("test", ["id", "name"], [(1, "a")], ["id"])
        catalog.upsert("test", ["id", "name"], [(1, "b")], ["id"])
        result = catalog.query("SELECT * FROM test")
        assert len(result) == 1
        assert result["name"][0] == "b"
        catalog.close()
