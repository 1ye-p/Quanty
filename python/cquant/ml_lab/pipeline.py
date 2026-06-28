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


def _create_trainer(model_type: str, model_params: dict | None = None):
    """Create the appropriate trainer based on model type.

    Parameters
    ----------
    model_type:
        Model registry key (e.g. ``"lgbm"``, ``"xgb"``, ``"lstm"``, ``"transformer"``).
    model_params:
        Optional hyperparameter overrides for qlib models.

    Returns
    -------
    A ``Trainer`` instance — either a native tree trainer or ``QlibModelTrainer``.
    """
    from cquant.qlib_bridge.models import is_qlib_model

    if is_qlib_model(model_type):
        from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer

        logger.info("Routing model %r to QlibModelTrainer", model_type)
        return QlibModelTrainer(model_type, model_params)

    # Native tree models
    if model_type == "xgb":
        from cquant.ml_lab.trainers.xgb import XGBTrainer
        return XGBTrainer()

    if model_type == "xgb_clf":
        from cquant.ml_lab.trainers.xgb_classifier import XGBClassifierTrainer
        return XGBClassifierTrainer()

    # Default to LightGBM
    from cquant.ml_lab.trainers.lgbm import LGBMTrainer
    return LGBMTrainer()


def run_ml_prediction_pipeline(
    catalog: "Catalog",
    features: pl.DataFrame,
    target_col: str = "ret_5d",
    model_id_prefix: str = "ml",
    n_splits: int = 3,
    gap_days: int = 5,
    horizon: str = "5d",
    model_type: str = "lgbm",
    model_params: dict | None = None,
) -> str:
    """训练模型并将每个 fold 的 OOS 预测写入 gold_predictions。

    Walk-forward 训练流程：
    1. 将数据按时间分割为 n_splits 个 fold
    2. 对每个 fold：训练模型 → 只在 OOS 期间生成预测 → 持久化
    3. 返回组合 model_id（MLModelStrategy 按前缀匹配所有 fold）

    支持的 model_type：
    - 原生模型：``"lgbm"``（默认）、``"xgb"``
    - qlib DL 模型：``"lstm"``, ``"transformer"``, ``"tabnet"``, ``"mlp"``, ``"gru"``,
      ``"tcn"``, ``"wavelet_net"``, ``"double_adapt"``, ``"tra"``, ``"localformer"``
    - qlib 集成模型：``"catboost_ensemble"``, ``"bagging"``, ``"stacking"``,
      ``"voting"``, ``"blending"``
    - qlib 线性模型：``"linear"``, ``"ridge"``, ``"lasso"``, ``"elastic_net"``, ...

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
    model_type:
        模型类型，自动路由到对应的 Trainer。
    model_params:
        传递给模型的超参数（qlib 模型使用 ModelInfo.default_params 作为基础）。

    返回
    ----
    组合 model_id（格式：``"{prefix}_wf_{n_splits}folds"``）。
    MLModelStrategy 使用此前缀查询所有 fold 的预测。
    """
    from cquant.ml_lab.walk_forward import WalkForwardValidator

    required = {"asset_id", "trade_date", target_col}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"features 缺少必要列：{missing}")

    wfv = WalkForwardValidator(n_splits=n_splits, gap_days=gap_days)
    splits = wfv.split(features)

    trainer = _create_trainer(model_type, model_params)
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
