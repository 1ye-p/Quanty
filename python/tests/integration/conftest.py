"""Shared fixtures for integration tests.

Provides ``populated_catalog`` (scope="session") so that all integration
test modules can share a single in-memory catalog seeded with synthetic data,
without each test file having to rebuild it from scratch.

Note: test_smoke.py defines its own module-scoped ``populated_catalog`` which
shadows this one for tests that live inside that module — that is intentional
and keeps the original smoke tests self-contained.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from cquant.datahub.catalog import Catalog

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def populated_catalog(tmp_path_factory):
    """Session-scoped catalog with 3 assets × 60 days of synthetic price data.

    Date range : 2024-10-01 – 2024-11-29
    Assets     : SSE:600036, SSE:000001, SSE:600519
    """
    tmp_path = tmp_path_factory.mktemp("integration_session")
    cat = Catalog(db_path=tmp_path / "integration.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()

    rng = np.random.default_rng(42)
    dates = [date(2024, 10, 1) + timedelta(days=i) for i in range(60)]
    assets = ["SSE:600036", "SSE:000001", "SSE:600519"]
    rows = []
    prices = {a: 50.0 for a in assets}
    for d in dates:
        for a in assets:
            prices[a] *= 1 + rng.normal(0.001, 0.015)
            p = prices[a]
            rows.append(
                {
                    "asset_id": a,
                    "trade_date": d,
                    "open": p,
                    "high": p * 1.02,
                    "low": p * 0.98,
                    "close": p,
                    "volume": float(rng.integers(500_000, 2_000_000)),
                    "amount": p * float(rng.integers(500_000, 2_000_000)),
                    "adj_factor": 1.0,
                    "adj_close": p,
                    "is_suspended": False,
                    "source": "test",
                }
            )

    df = pl.DataFrame(rows)
    conn = cat._get_conn()
    conn.register("_stage", df.to_arrow())
    conn.execute(
        """
        INSERT INTO silver_prices_1d
            (asset_id, trade_date, open, high, low, close, volume, amount,
             adj_factor, adj_close, is_suspended, source)
        SELECT asset_id, trade_date, open, high, low, close, volume, amount,
               adj_factor, adj_close, is_suspended, source
        FROM _stage
        """
    )
    conn.unregister("_stage")
    return cat
