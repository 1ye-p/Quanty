"""cquant.ml_lab.pipeline — ML 预测管道工具函数。

将特征加载 → 滚动训练 → 预测持久化整合为一键调用的函数。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from cquant.datahub.catalog import Catalog

logger = logging.getLogger(__name__)


def run_ml_prediction_pipeline(
    catalog: "Catalog",
    features: pl.DataFrame,
    target_col: str = "ret_5d",
    model_id_prefix: str = "ml",
    n_splits: int = 3,
    gap_days: int = 5,
    horizon: str = "5d",
) -> str:
    """训练 LightGBM 模型并将预测写入 gold_predictions。

    参数
    ----
    catalog:
        已初始化的 Catalog 连接（用于持久化预测）。
    features:
        包含 [asset_id, trade_date, feature_cols...] 的特征 DataFrame。
        必须包含 target_col 列。
    target_col:
        预测目标列名，例如 ``"ret_5d"``。
    model_id_prefix:
        模型 ID 前缀。
    n_splits:
        WalkForwardValidator 的分割数，默认 3。
    gap_days:
        训练集末尾与验证集开头之间的间隔天数（防泄漏）。
    horizon:
        预测周期标签，写入 gold_predictions.horizon 字段。

    返回
    ----
    训练完成的 ModelArtifact.model_id（用于构建 MLModelStrategy）。
    """
    from cquant.ml_lab.trainers.lgbm import LGBMTrainer
    from cquant.ml_lab.walk_forward import WalkForwardValidator

    required = {"asset_id", "trade_date", target_col}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"features 缺少必要列：{missing}")

    wfv = WalkForwardValidator(n_splits=n_splits, gap_days=gap_days)
    splits = wfv.split(features)

    trainer = LGBMTrainer()
    artifact = None

    for i, (train_df, valid_df) in enumerate(splits):
        logger.info("WalkForward 训练折 %d/%d，训练集 %d 行", i + 1, len(splits), len(train_df))
        artifact = trainer.fit(
            train_df.drop_nulls([target_col]),
            valid_df.drop_nulls([target_col]),
            {
                "target_name": target_col,
                "metadata": {"prefix": model_id_prefix, "fold": i},
            },
        )

    if artifact is None:
        raise ValueError("训练失败：WalkForward 未产出有效分割")

    logger.info("生成预测并写入 gold_predictions，model_id=%s", artifact.model_id)
    trainer.predict_and_persist(
        features=features,
        model_artifact=artifact,
        catalog=catalog,
        horizon=horizon,
    )

    return artifact.model_id
