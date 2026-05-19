"""E2E smoke test: ingest → factor materialize → backtest → API read.

Uses a mock connector to avoid external API dependencies.
Validates the full pipeline produces data in DuckDB silver/gold tables.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import polars as pl
import pytest

from cquant.core.enums import Frequency, Market
from cquant.datahub.catalog import Catalog
from cquant.datahub.connectors.base import DataConnector, DataSpec, RawBatch
from cquant.datahub.ingest import IngestionSpec, MarketIngestionOrchestrator
from cquant.datahub.pipelines.silver import SilverNormalizer
from cquant.factorlab import FactorMaterializer, FactorMaterializationSpec, FactorRegistry
from cquant.factorlab.factors import BUILTIN_FACTORS
from cquant.backtest_vector.run import BacktestRunner, BacktestRunSpec


# ── Mock Connector ──────────────────────────────────────────────────────────

class MockMarketConnector(DataConnector):
    """Returns synthetic daily bars for testing."""

    def __init__(self, market: Market, symbols: list[str]) -> None:
        self._market = market
        self._symbols = symbols

    @property
    def source_name(self) -> str:
        return "mock"

    @property
    def supported_markets(self) -> list[Market]:
        return [self._market]

    @property
    def supported_frequencies(self) -> list[Frequency]:
        return [Frequency.D1]

    def fetch(self, spec: DataSpec) -> Iterable[RawBatch]:
        random.seed(42)
        rows = []
        for symbol in spec.symbols:
            price = 50.0 if self._market == Market.CN else 100.0
            d = spec.start_date
            while d <= spec.end_date:
                if d.weekday() < 5:  # Skip weekends
                    ret = random.uniform(-0.03, 0.03)
                    price *= (1 + ret)
                    if self._market == Market.CN:
                        rows.append({
                            "ts_code": f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ",
                            "trade_date": d.strftime("%Y%m%d"),
                            "open": round(price * 0.999, 2),
                            "high": round(price * 1.005, 2),
                            "low": round(price * 0.995, 2),
                            "close": round(price, 2),
                            "vol": float(random.randint(100_000, 10_000_000)),
                            "amount": float(random.randint(10_000_000, 1_000_000_000)),
                        })
                    else:
                        rows.append({
                            "Date": d,
                            "Open": round(price * 0.999, 2),
                            "High": round(price * 1.005, 2),
                            "Low": round(price * 0.995, 2),
                            "Close": round(price, 2),
                            "Volume": float(random.randint(100_000, 10_000_000)),
                            "symbol": symbol,
                        })
                d += timedelta(days=1)

        df = pl.DataFrame(rows)
        yield RawBatch(
            source="tushare" if self._market == Market.CN else "yfinance",
            dataset="daily_bar",
            data=df,
            fetched_at="2024-01-01T00:00:00Z",
            spec=spec,
        )


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_catalog(tmp_path: Path) -> Catalog:
    """Create a fresh DuckDB catalog in a temp directory."""
    db_path = tmp_path / "test_catalog.duckdb"
    repo_root = Path(__file__).resolve().parents[3]  # cQuant root
    catalog = Catalog(db_path=db_path, repo_root=repo_root)
    yield catalog
    catalog.close()


@pytest.fixture
def cn_connector() -> MockMarketConnector:
    return MockMarketConnector(Market.CN, ["600036", "000001", "601318", "000858", "600519"])


@pytest.fixture
def us_connector() -> MockMarketConnector:
    return MockMarketConnector(Market.US, ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"])


# ── Tests ───────────────────────────────────────────────────────────────────

class TestCNPipeline:
    """Test the full CN pipeline: ingest → factor → backtest."""

    def test_ingest_cn(self, tmp_catalog: Catalog, cn_connector: MockMarketConnector) -> None:
        orchestrator = MarketIngestionOrchestrator(tmp_catalog, [cn_connector])
        version_id = orchestrator.ingest(IngestionSpec(
            market=Market.CN,
            symbols=["600036", "000001"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
        ))

        assert version_id
        df = tmp_catalog.query("SELECT COUNT(*) AS cnt FROM silver_prices_1d")
        assert df["cnt"].item() > 0

    def test_factor_materialize_cn(self, tmp_catalog: Catalog, cn_connector: MockMarketConnector) -> None:
        # Ingest first
        orchestrator = MarketIngestionOrchestrator(tmp_catalog, [cn_connector])
        version_id = orchestrator.ingest(IngestionSpec(
            market=Market.CN,
            symbols=["600036", "000001", "601318"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
        ))

        # Materialize factors
        registry = FactorRegistry()
        for f in BUILTIN_FACTORS:
            registry.register(f)

        materializer = FactorMaterializer(tmp_catalog, registry)
        fsv = materializer.run(FactorMaterializationSpec(
            dataset_version=version_id,
            factor_names=["ret_20d", "vol_20d"],
            start_date=date(2024, 3, 1),
            end_date=date(2024, 6, 30),
        ))

        assert fsv
        df = tmp_catalog.query("SELECT COUNT(*) AS cnt FROM gold_factor_values")
        assert df["cnt"].item() > 0

    def test_full_chain_cn(self, tmp_catalog: Catalog, cn_connector: MockMarketConnector) -> None:
        # Step 1: Ingest
        orchestrator = MarketIngestionOrchestrator(tmp_catalog, [cn_connector])
        version_id = orchestrator.ingest(IngestionSpec(
            market=Market.CN,
            symbols=["600036", "000001", "601318", "000858", "600519"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ))

        # Step 2: Materialize factors
        registry = FactorRegistry()
        for f in BUILTIN_FACTORS:
            registry.register(f)

        materializer = FactorMaterializer(tmp_catalog, registry)
        fsv = materializer.run(FactorMaterializationSpec(
            dataset_version=version_id,
            factor_names=["ret_20d", "vol_20d"],
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
        ))

        # Step 3: Run backtest
        runner = BacktestRunner(tmp_catalog)
        run_id = runner.run(BacktestRunSpec(
            dataset_version=version_id,
            strategy_id="top3_momentum_cn",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
            feature_set_version=fsv,
            top_n=3,
            sort_factor="ret_20d",
        ))

        assert run_id
        df = tmp_catalog.query(
            "SELECT status, metrics_uri FROM gold_backtest_runs WHERE run_id = ?",
            [run_id],
        )
        assert df["status"].item() == "completed"
        assert df["metrics_uri"].item() is not None


class TestUSPipeline:
    """Test the full US pipeline: ingest → factor → backtest."""

    def test_full_chain_us(self, tmp_catalog: Catalog, us_connector: MockMarketConnector) -> None:
        # Step 1: Ingest
        orchestrator = MarketIngestionOrchestrator(tmp_catalog, [us_connector])
        version_id = orchestrator.ingest(IngestionSpec(
            market=Market.US,
            symbols=["AAPL", "MSFT", "GOOGL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ))

        # Step 2: Materialize factors
        registry = FactorRegistry()
        for f in BUILTIN_FACTORS:
            registry.register(f)

        materializer = FactorMaterializer(tmp_catalog, registry)
        fsv = materializer.run(FactorMaterializationSpec(
            dataset_version=version_id,
            factor_names=["ret_20d", "vol_20d"],
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
        ))

        # Step 3: Run backtest
        runner = BacktestRunner(tmp_catalog)
        run_id = runner.run(BacktestRunSpec(
            dataset_version=version_id,
            strategy_id="top2_momentum_us",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
            feature_set_version=fsv,
            top_n=2,
            sort_factor="ret_20d",
        ))

        assert run_id
        df = tmp_catalog.query(
            "SELECT status FROM gold_backtest_runs WHERE run_id = ?",
            [run_id],
        )
        assert df["status"].item() == "completed"
