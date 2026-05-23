"""端到端集成测试：Factor → ML 训练 → 前向标签 → Backtest 链路。

使用 populated_catalog fixture（来自 conftest.py）的合成价格数据。
全链路用极小参数运行，确保 <60s 完成。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np
import polars as pl
import pytest


@pytest.mark.integration
class TestFactorMLBacktestChain:
    """Factor → ML → Backtest 完整链路集成测试。"""

    def test_forward_return_labels_from_silver_data(self, populated_catalog) -> None:
        """从 silver 数据可计算前向收益标签，且 clip 有效。"""
        from cquant.ml_lab.labels import forward_return_labels

        prices = populated_catalog.query(
            "SELECT asset_id, trade_date, close "
            "FROM silver_prices_1d ORDER BY asset_id, trade_date"
        )
        assert not prices.is_empty(), "silver_prices_1d should have data"

        labels = forward_return_labels(prices, periods=5)
        non_null = labels.drop_nulls()
        assert len(non_null) > 0, "Expected non-null labels"

        col = "ret_5d"
        assert (non_null[col].abs() <= 0.5).all(), (
            "All returns should be clipped to [-0.5, 0.5]"
        )

    def test_factor_materialization_produces_factor_values(
        self, populated_catalog
    ) -> None:
        """因子物化可将 ret_5d 写入 gold_factor_values。"""
        from cquant.factorlab.factor import FactorRegistry
        from cquant.factorlab.factors import BUILTIN_FACTORS
        from cquant.factorlab.materialize import (
            FactorMaterializer,
            FactorMaterializationSpec,
        )

        reg = FactorRegistry()
        for f in BUILTIN_FACTORS:
            if f.name == "ret_5d":
                reg.register(f)
                break

        assert reg.get("ret_5d") is not None, "ret_5d factor must be registered"

        materializer = FactorMaterializer(populated_catalog, reg)
        fsv_id = materializer.run(
            FactorMaterializationSpec(
                dataset_version="chain_test_v1",
                factor_names=["ret_5d"],
                start_date=date(2024, 10, 15),
                end_date=date(2024, 11, 20),
            )
        )

        assert fsv_id, "Expected non-empty feature_set_version"

        result = populated_catalog.query(
            "SELECT COUNT(*) AS cnt FROM gold_factor_values "
            "WHERE feature_set_version = ?",
            [fsv_id],
        )
        assert result["cnt"][0] > 0, (
            f"Expected factor rows for version {fsv_id}"
        )

    def test_lgbm_trainer_on_synthetic_factor_data(self, tmp_path) -> None:
        """LGBMTrainer 在合成因子数据上可完成训练和预测。"""
        pytest.importorskip("lightgbm")

        from cquant.ml_lab.trainers.lgbm import LGBMTrainer

        rng = np.random.default_rng(42)
        n_train, n_valid = 60, 20

        def _make_df(n: int) -> pl.DataFrame:
            return pl.DataFrame(
                {
                    "feat_ret5d": rng.normal(0, 0.02, n).tolist(),
                    "feat_vol20d": rng.uniform(0.1, 0.5, n).tolist(),
                    "label": rng.normal(0.005, 0.02, n).clip(-0.5, 0.5).tolist(),
                }
            )

        train_df = _make_df(n_train)
        valid_df = _make_df(n_valid)

        trainer = LGBMTrainer()
        artifact = trainer.fit(
            train=train_df,
            valid=valid_df,
            config={
                "target_name": "label",
                "model_dir": str(tmp_path / "lgbm_models"),
                "params": {
                    "n_estimators": 5,
                    "max_depth": 3,
                    "learning_rate": 0.1,
                },
            },
        )
        assert artifact is not None, "Expected a ModelArtifact"

        features_df = valid_df.select(["feat_ret5d", "feat_vol20d"])
        preds = trainer.predict(features_df, artifact)
        assert len(preds) == n_valid, (
            f"Expected {n_valid} predictions, got {len(preds)}"
        )

    def test_backtest_runs_and_persists_results(self, populated_catalog) -> None:
        """向量化回测可使用合成因子完整运行并写入 gold_backtest_runs。"""
        from cquant.backtest_vector.run import BacktestRunSpec, BacktestRunner
        from cquant.factorlab.factor import FactorRegistry
        from cquant.factorlab.factors import BUILTIN_FACTORS
        from cquant.factorlab.materialize import (
            FactorMaterializer,
            FactorMaterializationSpec,
        )

        # 1. Register and materialise the ret_5d factor
        reg = FactorRegistry()
        for f in BUILTIN_FACTORS:
            if f.name == "ret_5d":
                reg.register(f)
                break

        materializer = FactorMaterializer(populated_catalog, reg)
        fsv_id = materializer.run(
            FactorMaterializationSpec(
                dataset_version="chain_bt_v1",
                factor_names=["ret_5d"],
                start_date=date(2024, 10, 15),
                end_date=date(2024, 11, 20),
            )
        )
        assert fsv_id, "factor materialisation must return a version id"

        # 2. Run backtest (BacktestRunner creates StaticTopNStrategy internally)
        runner = BacktestRunner(populated_catalog)
        spec = BacktestRunSpec(
            dataset_version="chain_bt_v1",
            strategy_id="chain_test_strat",
            start_date=date(2024, 10, 20),
            end_date=date(2024, 11, 15),
            feature_set_version=fsv_id,
            top_n=2,
            sort_factor="ret_5d",
            initial_cash=Decimal("100000"),
        )
        run_id = runner.run(spec)
        assert run_id is not None, "Expected valid run_id"

        # 3. Verify results were persisted
        result = populated_catalog.query(
            "SELECT run_id, status FROM gold_backtest_runs WHERE run_id = ?",
            [run_id],
        )
        assert not result.is_empty(), (
            f"Expected backtest run {run_id} in gold_backtest_runs"
        )
        assert result["status"][0] == "completed", (
            f"Expected status=completed, got {result['status'][0]}"
        )
