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
    """训练 LightGBM 模型并将每个 fold 的 OOS 预测写入 gold_predictions。

    Walk-forward 训练流程：
    1. 将数据按时间分割为 n_splits 个 fold
    2. 对每个 fold：训练模型 → 只在 OOS 期间生成预测 → 持久化
    3. 返回组合 model_id（MLModelStrategy 按前缀匹配所有 fold）

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
    组合 model_id（格式：``"{prefix}_wf_{n_splits}folds"``）。
    MLModelStrategy 使用此前缀查询所有 fold 的预测。
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
    composite_id = f"{model_id_prefix}_wf_{n_splits}folds"

    for i, (train_df, valid_df) in enumerate(splits):
        fold_id = f"fold{i}"
        logger.info(
            "WalkForward 训练折 %d/%d，训练集 %d 行，OOS %d 行",
            i + 1, len(splits), len(train_df), len(valid_df),
        )

        artifact = trainer.fit(
            train_df.drop_nulls([target_col]),
            valid_df.drop_nulls([target_col]),
            {
                "target_name": target_col,
                "model_id": composite_id,
                "metadata": {"prefix": model_id_prefix, "fold": i},
            },
        )

        # 只在 OOS 期间生成预测，使用 fold_id 标识
        trainer.predict_and_persist(
            features=valid_df,
            model_artifact=artifact,
            catalog=catalog,
            horizon=horizon,
            fold_id=fold_id,
        )

    logger.info(
        "Walk-forward 训练完成，共 %d 个 fold，组合 model_id=%s",
        len(splits), composite_id,
    )
    return composite_id
