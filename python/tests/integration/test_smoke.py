"""端到端冒烟测试：数据加载 → 因子计算 → 策略回测 完整流程。

使用内存 DuckDB 和合成数据，验证各模块可以协同工作。
运行时间约 5-15 秒，可单独运行：
    pytest python/tests/integration/ -v -m integration
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from cquant.datahub.catalog import Catalog
from cquant.factorlab.factor import FactorRegistry
from cquant.factorlab.factors import BUILTIN_FACTORS
from cquant.factorlab.materialize import FactorMaterializer, FactorMaterializationSpec

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def populated_catalog(tmp_path_factory):
    """创建包含合成价格数据的临时目录和 DuckDB。"""
    tmp_path = tmp_path_factory.mktemp("integration")
    cat = Catalog(db_path=tmp_path / "integration.duckdb", repo_root=_REPO_ROOT)
    cat.initialize()

    # 生成 60 天合成 A 股价格数据（3 只股票）
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


@pytest.mark.integration
class TestEndToEndSmoke:
    def test_catalog_has_price_data(self, populated_catalog: Catalog) -> None:
        """步骤 1：数据层 — 价格数据已正确写入。"""
        result = populated_catalog.query("SELECT COUNT(*) as n FROM silver_prices_1d")
        assert result["n"][0] == 60 * 3

    def test_factor_materialization_runs(self, populated_catalog: Catalog) -> None:
        """步骤 2：因子层 — 能够物化动量因子。"""
        reg = FactorRegistry()
        for f in BUILTIN_FACTORS:
            if f.name in ("ret_20d", "vol_20d"):
                reg.register(f)

        materializer = FactorMaterializer(populated_catalog, reg)
        spec = FactorMaterializationSpec(
            dataset_version="smoke_v1",
            factor_names=["ret_20d", "vol_20d"],
            start_date=date(2024, 11, 1),
            end_date=date(2024, 11, 30),
        )
        fsv_id = materializer.run(spec)
        assert fsv_id is not None

        factors = populated_catalog.query(
            "SELECT COUNT(*) as n FROM gold_factor_values WHERE feature_set_version = ?",
            [fsv_id],
        )
        assert factors["n"][0] > 0

    def test_backtest_pipeline_runs(self, populated_catalog: Catalog) -> None:
        """步骤 3：回测层 — 能够完整执行 Top-N 动量策略。"""
        from cquant.backtest_vector.run import BacktestRunSpec, BacktestRunner

        # Materialize factors first so the strategy has signals to rank on
        reg = FactorRegistry()
        for f in BUILTIN_FACTORS:
            if f.name in ("ret_20d", "vol_20d"):
                reg.register(f)

        materializer = FactorMaterializer(populated_catalog, reg)
        fsv_id = materializer.run(
            FactorMaterializationSpec(
                dataset_version="smoke_bt_v1",
                factor_names=["ret_20d", "vol_20d"],
                start_date=date(2024, 11, 5),
                end_date=date(2024, 11, 28),
            )
        )

        runner = BacktestRunner(populated_catalog)
        spec = BacktestRunSpec(
            dataset_version="smoke_bt_v1",
            strategy_id="smoke_top2",
            start_date=date(2024, 11, 5),
            end_date=date(2024, 11, 28),
            feature_set_version=fsv_id,
            top_n=2,
            initial_cash=Decimal("100000"),
        )
        run_id = runner.run(spec)
        assert run_id is not None

        runs = populated_catalog.query(
            "SELECT run_id, status FROM gold_backtest_runs WHERE run_id = ?",
            [run_id],
        )
        assert not runs.is_empty()
        assert runs["status"][0] == "completed"

    def test_full_pipeline_metrics_are_valid(self, populated_catalog: Catalog) -> None:
        """步骤 4：指标合理性 — 回测结果指标在合理范围内。"""
        from cquant.backtest_vector.run import BacktestRunSpec, BacktestRunner

        # Materialize factors for the metrics test
        reg = FactorRegistry()
        for f in BUILTIN_FACTORS:
            if f.name in ("ret_20d", "vol_20d"):
                reg.register(f)

        materializer = FactorMaterializer(populated_catalog, reg)
        fsv_id = materializer.run(
            FactorMaterializationSpec(
                dataset_version="smoke_metrics_v1",
                factor_names=["ret_20d", "vol_20d"],
                start_date=date(2024, 11, 5),
                end_date=date(2024, 11, 28),
            )
        )

        runner = BacktestRunner(populated_catalog)
        spec = BacktestRunSpec(
            dataset_version="smoke_metrics_v1",
            strategy_id="smoke_metrics",
            start_date=date(2024, 11, 5),
            end_date=date(2024, 11, 28),
            feature_set_version=fsv_id,
            top_n=3,
            initial_cash=Decimal("500000"),
        )
        run_id = runner.run(spec)
        assert run_id is not None

        # Verify metrics artifact was written
        metrics_path = Path("data/backtest_artifacts") / f"{run_id}.json"
        assert metrics_path.exists(), f"Metrics artifact not found: {metrics_path}"

        data = json.loads(metrics_path.read_text())
        assert "sharpe_ratio" in data
        assert "max_drawdown" in data
        assert data["max_drawdown"] <= 0
        assert "annualized_return" in data
        assert "total_return" in data
        assert "annualized_volatility" in data
        assert "turnover_pct" in data
