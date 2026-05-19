-- bootstrap.sql — Initialize the cQuant DuckDB catalog.
-- Run once on first setup: duckdb data/catalog.duckdb < sql/duckdb/bootstrap.sql

PRAGMA enable_progress_bar;

-- Load all DDL in dependency order
.read sql/duckdb/bronze.sql
.read sql/duckdb/silver.sql
.read sql/duckdb/gold.sql
