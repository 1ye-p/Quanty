"""cquant.qlib_bridge.models — qlib model registry and factory.

Provides a unified registry of qlib-compatible models with structured
``ModelInfo`` metadata, and a ``create_model()`` factory function.

Usage::

    from cquant.qlib_bridge.models import QLIB_MODELS, create_model, ModelInfo

    # List available models
    for name, info in QLIB_MODELS.items():
        print(f"{name}: {info.model_type} — {info.description}")

    # Create a model instance
    model = create_model("lgbm", {"learning_rate": 0.05, "n_estimators": 300})

    # Query by type
    from cquant.qlib_bridge.models import get_models_by_type
    tree_models = get_models_by_type("tree")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from cquant.qlib_bridge._compat import QLIB_AVAILABLE


# ---------------------------------------------------------------------------
# ModelInfo dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelInfo:
    """Structured model metadata.

    Parameters
    ----------
    name : str
        Registry key (e.g. ``"lgbm"``).
    display_name : str
        Human-readable label (e.g. ``"LightGBM"``).
    model_type : str
        Category: ``"tree"``, ``"deep_learning"``, ``"linear"``,
        ``"ensemble"``, ``"online"``, ``"specialised"``.
    engine : str
        ``"native"`` (cQuant built-in) or ``"qlib"`` (uses qlib wrapper).
    description : str
        Short description (Chinese).
    default_params : dict
        Default hyperparameters.
    requires_alpha360 : bool
        Whether the model requires Alpha360 feature set (DL models).
    class_path : str or None
        Dotted import path for qlib model class.
    tunable_params : tuple
        Names of tunable hyperparameters.
    category_label : str
        UI group label (e.g. ``"传统模型"``, ``"深度学习"``).
    """

    name: str
    display_name: str
    model_type: str
    engine: str
    description: str
    default_params: dict[str, Any] = field(default_factory=dict)
    requires_alpha360: bool = False
    class_path: Optional[str] = None
    tunable_params: tuple[str, ...] = ()
    category_label: str = ""


# ---------------------------------------------------------------------------
# Model definitions — grouped by category
# ---------------------------------------------------------------------------

# --- Native cQuant models (LGBM / XGB wrappers via qlib) ---
NATIVE_MODELS: dict[str, ModelInfo] = {
    "lgbm": ModelInfo(
        name="lgbm",
        display_name="LightGBM",
        model_type="tree",
        engine="native",
        description="LightGBM 梯度提升树",
        class_path="qlib.contrib.model.gbdt_model.LGBModel",
        default_params={
            "learning_rate": 0.05,
            "n_estimators": 300,
            "max_depth": 6,
            "num_leaves": 31,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
        },
        tunable_params=(
            "learning_rate", "n_estimators", "max_depth", "num_leaves",
            "subsample", "colsample_bytree", "reg_alpha", "reg_lambda",
            "min_child_samples", "min_child_weight",
        ),
        category_label="传统模型",
    ),
    "xgb": ModelInfo(
        name="xgb",
        display_name="XGBoost",
        model_type="tree",
        engine="native",
        description="XGBoost 梯度提升树",
        class_path="qlib.contrib.model.xgboost_model.XGBModel",
        default_params={
            "learning_rate": 0.05,
            "n_estimators": 300,
            "max_depth": 6,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
        },
        tunable_params=(
            "learning_rate", "n_estimators", "max_depth",
            "subsample", "colsample_bytree", "reg_alpha", "reg_lambda",
            "min_child_weight", "gamma",
        ),
        category_label="传统模型",
    ),
    "catboost": ModelInfo(
        name="catboost",
        display_name="CatBoost",
        model_type="tree",
        engine="native",
        description="CatBoost 梯度提升（支持类别特征）",
        class_path="qlib.contrib.model.catboost_model.CatBoostModel",
        default_params={
            "learning_rate": 0.05,
            "iterations": 300,
            "depth": 6,
            "l2_leaf_reg": 3.0,
            "random_seed": 42,
        },
        tunable_params=(
            "learning_rate", "iterations", "depth", "l2_leaf_reg",
            "bagging_temperature", "random_strength",
        ),
        category_label="传统模型",
    ),
    "adaboost": ModelInfo(
        name="adaboost",
        display_name="AdaBoost",
        model_type="tree",
        engine="native",
        description="AdaBoost 集成（via LightGBM wrapper）",
        class_path="qlib.contrib.model.gbdt_model.LGBModel",
        default_params={
            "boosting_type": "dart",
            "learning_rate": 0.05,
            "n_estimators": 300,
        },
        tunable_params=("learning_rate", "n_estimators", "drop_rate"),
        category_label="传统模型",
    ),
    "extra_trees": ModelInfo(
        name="extra_trees",
        display_name="Extra Trees",
        model_type="tree",
        engine="native",
        description="Extra Trees 极端随机树",
        class_path="qlib.contrib.model.gbdt_model.LGBModel",
        default_params={
            "boosting_type": "rf",
            "n_estimators": 300,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        },
        tunable_params=("n_estimators", "subsample", "colsample_bytree"),
        category_label="传统模型",
    ),
    "random_forest": ModelInfo(
        name="random_forest",
        display_name="Random Forest",
        model_type="tree",
        engine="native",
        description="随机森林",
        class_path="qlib.contrib.model.gbdt_model.LGBModel",
        default_params={
            "boosting_type": "rf",
            "n_estimators": 500,
            "subsample": 0.632,
            "colsample_bytree": 0.8,
        },
        tunable_params=("n_estimators", "subsample", "colsample_bytree", "max_depth"),
        category_label="传统模型",
    ),
    "hist_gradient_boosting": ModelInfo(
        name="hist_gradient_boosting",
        display_name="Histogram GBDT",
        model_type="tree",
        engine="native",
        description="Histogram-based 梯度提升（LightGBM 原生）",
        class_path="qlib.contrib.model.gbdt_model.LGBModel",
        default_params={
            "learning_rate": 0.05,
            "n_estimators": 500,
            "max_bins": 255,
        },
        tunable_params=("learning_rate", "n_estimators", "max_bins", "max_depth"),
        category_label="传统模型",
    ),
    # --- Online / Incremental tree models ---
    "online_lightgbm": ModelInfo(
        name="online_lightgbm",
        display_name="Online LightGBM",
        model_type="online",
        engine="native",
        description="在线增量 LightGBM（每日更新）",
        class_path="qlib.contrib.model.gbdt_model.LGBModel",
        default_params={
            "learning_rate": 0.02,
            "n_estimators": 100,
            "max_depth": 5,
            "num_leaves": 31,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
        },
        tunable_params=("learning_rate", "n_estimators", "max_depth"),
        category_label="在线模型",
    ),
    "online_xgboost": ModelInfo(
        name="online_xgboost",
        display_name="Online XGBoost",
        model_type="online",
        engine="native",
        description="在线增量 XGBoost（每日更新）",
        class_path="qlib.contrib.model.xgboost_model.XGBModel",
        default_params={
            "learning_rate": 0.02,
            "n_estimators": 100,
            "max_depth": 5,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
        },
        tunable_params=("learning_rate", "n_estimators", "max_depth"),
        category_label="在线模型",
    ),
    "catboost_online": ModelInfo(
        name="catboost_online",
        display_name="Online CatBoost",
        model_type="online",
        engine="native",
        description="在线增量 CatBoost（每日更新）",
        class_path="qlib.contrib.model.catboost_model.CatBoostModel",
        default_params={
            "learning_rate": 0.02,
            "iterations": 100,
            "depth": 5,
            "l2_leaf_reg": 3.0,
        },
        tunable_params=("learning_rate", "iterations", "depth"),
        category_label="在线模型",
    ),
}

# --- Qlib deep learning models ---
QLIB_DL_MODELS: dict[str, ModelInfo] = {
    "lstm": ModelInfo(
        name="lstm",
        display_name="LSTM",
        model_type="deep_learning",
        engine="qlib",
        description="LSTM 长短期记忆网络",
        class_path="qlib.contrib.model.pytorch_lstm_model.LSTM",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        tunable_params=(
            "hidden_size", "num_layers", "dropout", "lr", "batch_size",
            "n_epochs", "early_stop",
        ),
        category_label="深度学习",
    ),
    "transformer": ModelInfo(
        name="transformer",
        display_name="Transformer",
        model_type="deep_learning",
        engine="qlib",
        description="Transformer 自注意力模型",
        class_path="qlib.contrib.model.pytorch_transformer_model.TransformerModel",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "d_model": 64,
            "nhead": 4,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        tunable_params=(
            "d_model", "nhead", "num_layers", "dropout", "lr",
            "batch_size", "n_epochs", "early_stop",
        ),
        category_label="深度学习",
    ),
    "tabnet": ModelInfo(
        name="tabnet",
        display_name="TabNet",
        model_type="deep_learning",
        engine="qlib",
        description="TabNet 注意力表格模型",
        class_path="qlib.contrib.model.tabnet_model.TabNetModel",
        requires_alpha360=True,
        default_params={
            "n_d": 32,
            "n_a": 32,
            "n_steps": 5,
            "gamma": 1.5,
            "lambda_sparse": 1e-3,
            "n_epochs": 200,
            "lr": 0.02,
            "batch_size": 1024,
        },
        tunable_params=(
            "n_d", "n_a", "n_steps", "gamma", "lambda_sparse",
            "lr", "batch_size", "n_epochs",
        ),
        category_label="深度学习",
    ),
    "mlp": ModelInfo(
        name="mlp",
        display_name="MLP",
        model_type="deep_learning",
        engine="qlib",
        description="多层感知机（MLP）",
        class_path="qlib.contrib.model.pytorch_lstm_model.LSTM",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "hidden_size": 128,
            "num_layers": 3,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        tunable_params=("hidden_size", "num_layers", "dropout", "lr", "batch_size"),
        category_label="深度学习",
    ),
    "gru": ModelInfo(
        name="gru",
        display_name="GRU",
        model_type="deep_learning",
        engine="qlib",
        description="GRU 门控循环单元",
        class_path="qlib.contrib.model.pytorch_lstm_model.LSTM",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        tunable_params=("hidden_size", "num_layers", "dropout", "lr", "batch_size"),
        category_label="深度学习",
    ),
    "tcn": ModelInfo(
        name="tcn",
        display_name="TCN",
        model_type="deep_learning",
        engine="qlib",
        description="时间卷积网络（TCN）",
        class_path="qlib.contrib.model.pytorch_lstm_model.LSTM",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 4,
            "dropout": 0.2,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        tunable_params=("hidden_size", "num_layers", "dropout", "lr", "batch_size"),
        category_label="深度学习",
    ),
    "wavelet_net": ModelInfo(
        name="wavelet_net",
        display_name="WaveletNet",
        model_type="deep_learning",
        engine="qlib",
        description="小波神经网络",
        class_path="qlib.contrib.model.pytorch_lstm_model.LSTM",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
        },
        tunable_params=("hidden_size", "num_layers", "dropout", "lr"),
        category_label="深度学习",
    ),
    # --- Specialised (DL-based) ---
    "double_adapt": ModelInfo(
        name="double_adapt",
        display_name="DoubleAdapt",
        model_type="specialised",
        engine="qlib",
        description="DoubleAdapt 自适应学习率模型",
        class_path="qlib.contrib.model.pytorch_lstm_model.LSTM",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        tunable_params=("hidden_size", "num_layers", "dropout", "lr"),
        category_label="专用模型",
    ),
    "tra": ModelInfo(
        name="tra",
        display_name="TRA",
        model_type="specialised",
        engine="qlib",
        description="TRA 时序路由注意力模型",
        class_path="qlib.contrib.model.pytorch_transformer_model.TransformerModel",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "d_model": 64,
            "nhead": 4,
            "num_layers": 3,
            "dropout": 0.2,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        tunable_params=("d_model", "nhead", "num_layers", "dropout", "lr"),
        category_label="专用模型",
    ),
    "localformer": ModelInfo(
        name="localformer",
        display_name="Localformer",
        model_type="specialised",
        engine="qlib",
        description="Localformer 局部注意力 Transformer",
        class_path="qlib.contrib.model.pytorch_transformer_model.TransformerModel",
        requires_alpha360=True,
        default_params={
            "d_feat": 6,
            "d_model": 64,
            "nhead": 4,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
        },
        tunable_params=("d_model", "nhead", "num_layers", "dropout", "lr"),
        category_label="专用模型",
    ),
}

# --- Qlib tree models (CatBoost via qlib, ensemble wrappers) ---
QLIB_TREE_MODELS: dict[str, ModelInfo] = {
    "catboost_ensemble": ModelInfo(
        name="catboost_ensemble",
        display_name="CatBoost Ensemble",
        model_type="ensemble",
        engine="qlib",
        description="滚动窗口 CatBoost 集成",
        class_path="qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        default_params={
            "base_model": "catboost",
            "n_estimators": 5,
            "rolling_days": 120,
        },
        tunable_params=("n_estimators", "rolling_days"),
        category_label="集成模型",
    ),
    "bagging": ModelInfo(
        name="bagging",
        display_name="Bagging",
        model_type="ensemble",
        engine="qlib",
        description="Bagging 自助聚合集成",
        class_path="qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        default_params={
            "base_model": "lgbm",
            "n_estimators": 10,
            "rolling_days": 120,
        },
        tunable_params=("n_estimators", "rolling_days"),
        category_label="集成模型",
    ),
    "stacking": ModelInfo(
        name="stacking",
        display_name="Stacking",
        model_type="ensemble",
        engine="qlib",
        description="Stacking 堆叠集成",
        class_path="qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        default_params={
            "base_model": "xgb",
            "n_estimators": 5,
            "rolling_days": 60,
        },
        tunable_params=("n_estimators", "rolling_days"),
        category_label="集成模型",
    ),
    "voting": ModelInfo(
        name="voting",
        display_name="Voting",
        model_type="ensemble",
        engine="qlib",
        description="Voting 投票集成",
        class_path="qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        default_params={
            "base_model": "catboost",
            "n_estimators": 3,
            "rolling_days": 90,
        },
        tunable_params=("n_estimators", "rolling_days"),
        category_label="集成模型",
    ),
    "blending": ModelInfo(
        name="blending",
        display_name="Blending",
        model_type="ensemble",
        engine="qlib",
        description="Blending 混合集成",
        class_path="qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        default_params={
            "base_model": "lgbm",
            "n_estimators": 8,
            "rolling_days": 150,
        },
        tunable_params=("n_estimators", "rolling_days"),
        category_label="集成模型",
    ),
}

# --- Qlib linear / traditional models ---
QLIB_LINEAR_MODELS: dict[str, ModelInfo] = {
    "linear": ModelInfo(
        name="linear",
        display_name="OLS",
        model_type="linear",
        engine="qlib",
        description="线性回归模型（OLS / Ridge / Lasso）",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "ols"},
        tunable_params=("estimator", "alpha"),
        category_label="传统模型",
    ),
    "ridge": ModelInfo(
        name="ridge",
        display_name="Ridge",
        model_type="linear",
        engine="qlib",
        description="Ridge 岭回归",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "ridge", "alpha": 1.0},
        tunable_params=("alpha",),
        category_label="传统模型",
    ),
    "lasso": ModelInfo(
        name="lasso",
        display_name="Lasso",
        model_type="linear",
        engine="qlib",
        description="Lasso 回归（L1 正则化）",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "lasso", "alpha": 0.1},
        tunable_params=("alpha",),
        category_label="传统模型",
    ),
    "elastic_net": ModelInfo(
        name="elastic_net",
        display_name="ElasticNet",
        model_type="linear",
        engine="qlib",
        description="ElasticNet 弹性网络（L1+L2 混合正则化）",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "elastic_net", "alpha": 0.1, "l1_ratio": 0.5},
        tunable_params=("alpha", "l1_ratio"),
        category_label="传统模型",
    ),
    "bayesian_ridge": ModelInfo(
        name="bayesian_ridge",
        display_name="Bayesian Ridge",
        model_type="linear",
        engine="qlib",
        description="贝叶斯岭回归",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={
            "estimator": "bayesian_ridge",
            "alpha_1": 1e-6,
            "alpha_2": 1e-6,
        },
        tunable_params=("alpha_1", "alpha_2", "lambda_1", "lambda_2"),
        category_label="传统模型",
    ),
    "huber": ModelInfo(
        name="huber",
        display_name="Huber",
        model_type="linear",
        engine="qlib",
        description="Huber 回归（对异常值鲁棒）",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "huber", "epsilon": 1.35},
        tunable_params=("epsilon", "alpha"),
        category_label="传统模型",
    ),
    "quantile": ModelInfo(
        name="quantile",
        display_name="Quantile",
        model_type="linear",
        engine="qlib",
        description="分位数回归",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "quantile", "quantile": 0.5},
        tunable_params=("quantile", "alpha"),
        category_label="传统模型",
    ),
    "theilsen": ModelInfo(
        name="theilsen",
        display_name="Theil-Sen",
        model_type="linear",
        engine="qlib",
        description="Theil-Sen 回归（中位数回归，高崩溃点）",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "theilsen"},
        category_label="传统模型",
    ),
    "sgd": ModelInfo(
        name="sgd",
        display_name="SGD",
        model_type="linear",
        engine="qlib",
        description="SGD 随机梯度下降回归",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "sgd", "alpha": 0.0001, "penalty": "l2"},
        tunable_params=("alpha", "penalty", "learning_rate"),
        category_label="传统模型",
    ),
    "passive_aggressive": ModelInfo(
        name="passive_aggressive",
        display_name="Passive Aggressive",
        model_type="linear",
        engine="qlib",
        description="被动攻击回归器",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "passive_aggressive", "C": 1.0},
        tunable_params=("C", "epsilon"),
        category_label="传统模型",
    ),
    "kernel_ridge": ModelInfo(
        name="kernel_ridge",
        display_name="Kernel Ridge",
        model_type="linear",
        engine="qlib",
        description="核岭回归",
        class_path="qlib.contrib.model.linear_model.LinearModel",
        default_params={"estimator": "kernel_ridge", "alpha": 1.0, "kernel": "rbf"},
        tunable_params=("alpha", "kernel", "gamma"),
        category_label="传统模型",
    ),
}


# ---------------------------------------------------------------------------
# Unified model registry
# ---------------------------------------------------------------------------

ALL_MODELS: dict[str, ModelInfo] = {
    **NATIVE_MODELS,
    **QLIB_DL_MODELS,
    **QLIB_TREE_MODELS,
    **QLIB_LINEAR_MODELS,
}

# Backward-compatible flat dict (dict-of-dicts) for existing callers.
# New code should use ALL_MODELS / ModelInfo directly.
QLIB_MODELS: dict[str, dict[str, Any]] = {
    name: {
        "class_path": info.class_path,
        "category": info.model_type,
        "category_label": info.category_label,
        "description": info.description,
        "default_params": dict(info.default_params),
        "tunable_params": list(info.tunable_params),
    }
    for name, info in ALL_MODELS.items()
}


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_model_info(model_name: str) -> ModelInfo:
    """Return the ``ModelInfo`` for *model_name*.

    Raises ``KeyError`` if the model is not registered.
    """
    if model_name not in ALL_MODELS:
        raise KeyError(
            f"Unknown model: {model_name!r}. "
            f"Available: {list(ALL_MODELS.keys())}"
        )
    return ALL_MODELS[model_name]


def get_models_by_type(model_type: str) -> dict[str, ModelInfo]:
    """Return all models whose ``model_type`` matches *model_type*."""
    return {
        name: info
        for name, info in ALL_MODELS.items()
        if info.model_type == model_type
    }


def get_all_models() -> dict[str, ModelInfo]:
    """Return the full model registry."""
    return dict(ALL_MODELS)


def is_qlib_model(model_name: str) -> bool:
    """Return ``True`` if *model_name* is a qlib-engine model (not native)."""
    info = ALL_MODELS.get(model_name)
    if info is None:
        return False
    return info.engine == "qlib"


def get_model_category_groups() -> dict[str, list[str]]:
    """Group model names by ``category_label`` for UI rendering.

    Returns::

        {
            "传统模型": ["lgbm", "xgb", "catboost", ...],
            "深度学习": ["lstm", "transformer", ...],
            "集成模型": ["catboost_ensemble", ...],
        }
    """
    groups: dict[str, list[str]] = {}
    for name, info in ALL_MODELS.items():
        groups.setdefault(info.category_label, []).append(name)
    return groups


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_model(
    model_name: str,
    params: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a qlib model instance by registry name.

    Parameters
    ----------
    model_name : str
        Key in ``ALL_MODELS`` (e.g. ``"lgbm"``, ``"lstm"``).
    params : dict, optional
        Hyperparameters to override defaults.  If ``None``, uses
        ``ALL_MODELS[model_name].default_params``.
    **kwargs
        Extra keyword arguments passed directly to the model constructor.

    Returns
    -------
    model
        Instantiated qlib model object.

    Raises
    ------
    KeyError
        If ``model_name`` is not in ``ALL_MODELS``.
    ImportError
        If qlib is not installed.
    """
    info = get_model_info(model_name)

    if not QLIB_AVAILABLE:
        raise ImportError(
            "qlib is not installed. Install it with: pip install pyqlib"
        )

    if info.class_path is None:
        raise ValueError(
            f"Model {model_name!r} has no class_path — cannot instantiate."
        )

    merged_params = {**info.default_params, **(params or {}), **kwargs}

    # Dynamic import of the model class
    module_path, class_name = info.class_path.rsplit(".", 1)

    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    return cls(**merged_params)
