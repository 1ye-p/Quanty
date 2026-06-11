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
