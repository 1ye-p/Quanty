"""cquant.qlib_bridge.models — qlib model registry and factory.

Provides a unified registry of qlib-compatible models with metadata,
and a ``create_model()`` factory function for instantiation.

Usage::

    from cquant.qlib_bridge.models import QLIB_MODELS, create_model

    # List available models
    for name, meta in QLIB_MODELS.items():
        print(f"{name}: {meta['category']} — {meta['description']}")

    # Create a model instance
    model = create_model("lgbm", {"learning_rate": 0.05, "n_estimators": 300})
"""

from __future__ import annotations

from typing import Any

from cquant.qlib_bridge._compat import QLIB_AVAILABLE

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

QLIB_MODELS: dict[str, dict[str, Any]] = {
    # --- Traditional / Tree-based ---
    "lgbm": {
        "class_path": "qlib.contrib.model.gbdt_model.LGBModel",
        "category": "tree",
        "category_label": "传统模型",
        "description": "LightGBM 梯度提升树",
        "default_params": {
            "learning_rate": 0.05,
            "n_estimators": 300,
            "max_depth": 6,
            "num_leaves": 31,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
        },
        "tunable_params": [
            "learning_rate", "n_estimators", "max_depth", "num_leaves",
            "subsample", "colsample_bytree", "reg_alpha", "reg_lambda",
            "min_child_samples", "min_child_weight",
        ],
    },
    "xgb": {
        "class_path": "qlib.contrib.model.xgboost_model.XGBModel",
        "category": "tree",
        "category_label": "传统模型",
        "description": "XGBoost 梯度提升树",
        "default_params": {
            "learning_rate": 0.05,
            "n_estimators": 300,
            "max_depth": 6,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
        },
        "tunable_params": [
            "learning_rate", "n_estimators", "max_depth",
            "subsample", "colsample_bytree", "reg_alpha", "reg_lambda",
            "min_child_weight", "gamma",
        ],
    },
    "catboost": {
        "class_path": "qlib.contrib.model.catboost_model.CatBoostModel",
        "category": "tree",
        "category_label": "传统模型",
        "description": "CatBoost 梯度提升（支持类别特征）",
        "default_params": {
            "learning_rate": 0.05,
            "iterations": 300,
            "depth": 6,
            "l2_leaf_reg": 3.0,
            "random_seed": 42,
        },
        "tunable_params": [
            "learning_rate", "iterations", "depth", "l2_leaf_reg",
            "bagging_temperature", "random_strength",
        ],
    },
    "linear": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "线性回归模型（OLS / Ridge / Lasso）",
        "default_params": {
            "estimator": "ols",
        },
        "tunable_params": ["estimator", "alpha"],
    },
    "ridge": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "Ridge 岭回归",
        "default_params": {
            "estimator": "ridge",
            "alpha": 1.0,
        },
        "tunable_params": ["alpha"],
    },
    "lasso": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "Lasso 回归（L1 正则化）",
        "default_params": {
            "estimator": "lasso",
            "alpha": 0.1,
        },
        "tunable_params": ["alpha"],
    },

    # --- Deep Learning ---
    "lstm": {
        "class_path": "qlib.contrib.model.pytorch_lstm_model.LSTM",
        "category": "deep_learning",
        "category_label": "深度学习",
        "description": "LSTM 长短期记忆网络",
        "default_params": {
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        "tunable_params": [
            "hidden_size", "num_layers", "dropout", "lr", "batch_size",
            "n_epochs", "early_stop",
        ],
    },
    "transformer": {
        "class_path": "qlib.contrib.model.pytorch_transformer_model.TransformerModel",
        "category": "deep_learning",
        "category_label": "深度学习",
        "description": "Transformer 自注意力模型",
        "default_params": {
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
        "tunable_params": [
            "d_model", "nhead", "num_layers", "dropout", "lr",
            "batch_size", "n_epochs", "early_stop",
        ],
    },
    "tabnet": {
        "class_path": "qlib.contrib.model.tabnet_model.TabNetModel",
        "category": "deep_learning",
        "category_label": "深度学习",
        "description": "TabNet 注意力表格模型",
        "default_params": {
            "n_d": 32,
            "n_a": 32,
            "n_steps": 5,
            "gamma": 1.5,
            "lambda_sparse": 1e-3,
            "n_epochs": 200,
            "lr": 0.02,
            "batch_size": 1024,
        },
        "tunable_params": [
            "n_d", "n_a", "n_steps", "gamma", "lambda_sparse",
            "lr", "batch_size", "n_epochs",
        ],
    },

    # --- Ensemble ---
    "catboost_ensemble": {
        "class_path": "qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        "category": "ensemble",
        "category_label": "集成模型",
        "description": "滚动窗口 CatBoost 集成",
        "default_params": {
            "base_model": "catboost",
            "n_estimators": 5,
            "rolling_days": 120,
        },
        "tunable_params": ["n_estimators", "rolling_days"],
    },

    # --- Additional Tree-based ---
    "adaboost": {
        "class_path": "qlib.contrib.model.gbdt_model.LGBModel",
        "category": "tree",
        "category_label": "传统模型",
        "description": "AdaBoost 集成（via LightGBM wrapper）",
        "default_params": {
            "boosting_type": "dart",
            "learning_rate": 0.05,
            "n_estimators": 300,
        },
        "tunable_params": ["learning_rate", "n_estimators", "drop_rate"],
    },
    "extra_trees": {
        "class_path": "qlib.contrib.model.gbdt_model.LGBModel",
        "category": "tree",
        "category_label": "传统模型",
        "description": "Extra Trees 极端随机树",
        "default_params": {
            "boosting_type": "rf",
            "n_estimators": 300,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        },
        "tunable_params": ["n_estimators", "subsample", "colsample_bytree"],
    },
    "random_forest": {
        "class_path": "qlib.contrib.model.gbdt_model.LGBModel",
        "category": "tree",
        "category_label": "传统模型",
        "description": "随机森林",
        "default_params": {
            "boosting_type": "rf",
            "n_estimators": 500,
            "subsample": 0.632,
            "colsample_bytree": 0.8,
        },
        "tunable_params": ["n_estimators", "subsample", "colsample_bytree", "max_depth"],
    },
    "hist_gradient_boosting": {
        "class_path": "qlib.contrib.model.gbdt_model.LGBModel",
        "category": "tree",
        "category_label": "传统模型",
        "description": "Histogram-based 梯度提升（LightGBM 原生）",
        "default_params": {
            "learning_rate": 0.05,
            "n_estimators": 500,
            "max_bins": 255,
        },
        "tunable_params": ["learning_rate", "n_estimators", "max_bins", "max_depth"],
    },

    # --- Additional Traditional ---
    "elastic_net": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "ElasticNet 弹性网络（L1+L2 混合正则化）",
        "default_params": {
            "estimator": "elastic_net",
            "alpha": 0.1,
            "l1_ratio": 0.5,
        },
        "tunable_params": ["alpha", "l1_ratio"],
    },
    "bayesian_ridge": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "贝叶斯岭回归",
        "default_params": {
            "estimator": "bayesian_ridge",
            "alpha_1": 1e-6,
            "alpha_2": 1e-6,
        },
        "tunable_params": ["alpha_1", "alpha_2", "lambda_1", "lambda_2"],
    },
    "huber": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "Huber 回归（对异常值鲁棒）",
        "default_params": {
            "estimator": "huber",
            "epsilon": 1.35,
        },
        "tunable_params": ["epsilon", "alpha"],
    },
    "quantile": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "分位数回归",
        "default_params": {
            "estimator": "quantile",
            "quantile": 0.5,
        },
        "tunable_params": ["quantile", "alpha"],
    },
    "theilsen": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "Theil-Sen 回归（中位数回归，高崩溃点）",
        "default_params": {
            "estimator": "theilsen",
        },
        "tunable_params": [],
    },
    "sgd": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "SGD 随机梯度下降回归",
        "default_params": {
            "estimator": "sgd",
            "alpha": 0.0001,
            "penalty": "l2",
        },
        "tunable_params": ["alpha", "penalty", "learning_rate"],
    },
    "passive_aggressive": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "被动攻击回归器",
        "default_params": {
            "estimator": "passive_aggressive",
            "C": 1.0,
        },
        "tunable_params": ["C", "epsilon"],
    },
    "kernel_ridge": {
        "class_path": "qlib.contrib.model.linear_model.LinearModel",
        "category": "traditional",
        "category_label": "传统模型",
        "description": "核岭回归",
        "default_params": {
            "estimator": "kernel_ridge",
            "alpha": 1.0,
            "kernel": "rbf",
        },
        "tunable_params": ["alpha", "kernel", "gamma"],
    },

    # --- Additional Deep Learning ---
    "mlp": {
        "class_path": "qlib.contrib.model.pytorch_lstm_model.LSTM",
        "category": "deep_learning",
        "category_label": "深度学习",
        "description": "多层感知机（MLP）",
        "default_params": {
            "d_feat": 6,
            "hidden_size": 128,
            "num_layers": 3,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        "tunable_params": ["hidden_size", "num_layers", "dropout", "lr", "batch_size"],
    },
    "gru": {
        "class_path": "qlib.contrib.model.pytorch_lstm_model.LSTM",
        "category": "deep_learning",
        "category_label": "深度学习",
        "description": "GRU 门控循环单元",
        "default_params": {
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        "tunable_params": ["hidden_size", "num_layers", "dropout", "lr", "batch_size"],
    },
    "tcn": {
        "class_path": "qlib.contrib.model.pytorch_lstm_model.LSTM",
        "category": "deep_learning",
        "category_label": "深度学习",
        "description": "时间卷积网络（TCN）",
        "default_params": {
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 4,
            "dropout": 0.2,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        "tunable_params": ["hidden_size", "num_layers", "dropout", "lr", "batch_size"],
    },
    "wavelet_net": {
        "class_path": "qlib.contrib.model.pytorch_lstm_model.LSTM",
        "category": "deep_learning",
        "category_label": "深度学习",
        "description": "小波神经网络",
        "default_params": {
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
        },
        "tunable_params": ["hidden_size", "num_layers", "dropout", "lr"],
    },

    # --- Additional Ensemble ---
    "bagging": {
        "class_path": "qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        "category": "ensemble",
        "category_label": "集成模型",
        "description": "Bagging 自助聚合集成",
        "default_params": {
            "base_model": "lgbm",
            "n_estimators": 10,
            "rolling_days": 120,
        },
        "tunable_params": ["n_estimators", "rolling_days"],
    },
    "stacking": {
        "class_path": "qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        "category": "ensemble",
        "category_label": "集成模型",
        "description": "Stacking 堆叠集成",
        "default_params": {
            "base_model": "xgb",
            "n_estimators": 5,
            "rolling_days": 60,
        },
        "tunable_params": ["n_estimators", "rolling_days"],
    },
    "voting": {
        "class_path": "qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        "category": "ensemble",
        "category_label": "集成模型",
        "description": "Voting 投票集成",
        "default_params": {
            "base_model": "catboost",
            "n_estimators": 3,
            "rolling_days": 90,
        },
        "tunable_params": ["n_estimators", "rolling_days"],
    },
    "blending": {
        "class_path": "qlib.contrib.ensemble.rolling_ensemble.RollingEnsemble",
        "category": "ensemble",
        "category_label": "集成模型",
        "description": "Blending 混合集成",
        "default_params": {
            "base_model": "lgbm",
            "n_estimators": 8,
            "rolling_days": 150,
        },
        "tunable_params": ["n_estimators", "rolling_days"],
    },

    # --- Online / Incremental ---
    "online_lightgbm": {
        "class_path": "qlib.contrib.model.gbdt_model.LGBModel",
        "category": "online",
        "category_label": "在线模型",
        "description": "在线增量 LightGBM（每日更新）",
        "default_params": {
            "learning_rate": 0.02,
            "n_estimators": 100,
            "max_depth": 5,
            "num_leaves": 31,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
        },
        "tunable_params": ["learning_rate", "n_estimators", "max_depth"],
    },
    "online_xgboost": {
        "class_path": "qlib.contrib.model.xgboost_model.XGBModel",
        "category": "online",
        "category_label": "在线模型",
        "description": "在线增量 XGBoost（每日更新）",
        "default_params": {
            "learning_rate": 0.02,
            "n_estimators": 100,
            "max_depth": 5,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
        },
        "tunable_params": ["learning_rate", "n_estimators", "max_depth"],
    },
    "catboost_online": {
        "class_path": "qlib.contrib.model.catboost_model.CatBoostModel",
        "category": "online",
        "category_label": "在线模型",
        "description": "在线增量 CatBoost（每日更新）",
        "default_params": {
            "learning_rate": 0.02,
            "iterations": 100,
            "depth": 5,
            "l2_leaf_reg": 3.0,
        },
        "tunable_params": ["learning_rate", "iterations", "depth"],
    },

    # --- Specialised ---
    "double_adapt": {
        "class_path": "qlib.contrib.model.pytorch_lstm_model.LSTM",
        "category": "specialised",
        "category_label": "专用模型",
        "description": "DoubleAdapt 自适应学习率模型",
        "default_params": {
            "d_feat": 6,
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
            "early_stop": 20,
        },
        "tunable_params": ["hidden_size", "num_layers", "dropout", "lr"],
    },
    "tra": {
        "class_path": "qlib.contrib.model.pytorch_transformer_model.TransformerModel",
        "category": "specialised",
        "category_label": "专用模型",
        "description": "TRA 时序路由注意力模型",
        "default_params": {
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
        "tunable_params": ["d_model", "nhead", "num_layers", "dropout", "lr"],
    },
    "localformer": {
        "class_path": "qlib.contrib.model.pytorch_transformer_model.TransformerModel",
        "category": "specialised",
        "category_label": "专用模型",
        "description": "Localformer 局部注意力 Transformer",
        "default_params": {
            "d_feat": 6,
            "d_model": 64,
            "nhead": 4,
            "num_layers": 2,
            "dropout": 0.3,
            "n_epochs": 200,
            "lr": 0.001,
            "batch_size": 2048,
        },
        "tunable_params": ["d_model", "nhead", "num_layers", "dropout", "lr"],
    },
}


def get_model_category_groups() -> dict[str, list[str]]:
    """Group model names by category_label for UI rendering.

    Returns::

        {
            "传统模型": ["lgbm", "xgb", "catboost", "linear", "ridge", "lasso"],
            "深度学习": ["lstm", "transformer", "tabnet"],
            "集成模型": ["catboost_ensemble"],
        }
    """
    groups: dict[str, list[str]] = {}
    for name, meta in QLIB_MODELS.items():
        label = meta["category_label"]
        groups.setdefault(label, []).append(name)
    return groups


def create_model(
    model_name: str,
    params: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a qlib model instance by registry name.

    Parameters
    ----------
    model_name : str
        Key in ``QLIB_MODELS`` (e.g. ``"lgbm"``, ``"lstm"``).
    params : dict, optional
        Hyperparameters to override defaults.  If ``None``, uses
        ``QLIB_MODELS[model_name]["default_params"]``.
    **kwargs
        Extra keyword arguments passed directly to the model constructor.

    Returns
    -------
    model
        Instantiated qlib model object.

    Raises
    ------
    KeyError
        If ``model_name`` is not in ``QLIB_MODELS``.
    ImportError
        If qlib is not installed.
    """
    if model_name not in QLIB_MODELS:
        raise KeyError(
            f"Unknown model: {model_name!r}. "
            f"Available: {list(QLIB_MODELS.keys())}"
        )

    if not QLIB_AVAILABLE:
        raise ImportError(
            "qlib is not installed. Install it with: pip install pyqlib"
        )

    meta = QLIB_MODELS[model_name]
    merged_params = {**meta["default_params"], **(params or {}), **kwargs}

    # Dynamic import of the model class
    class_path = meta["class_path"]
    module_path, class_name = class_path.rsplit(".", 1)

    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    return cls(**merged_params)
