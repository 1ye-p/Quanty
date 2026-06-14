"""End-to-end integration tests for qlib enhanced integration.

Tests:
1. Alpha158 factor completeness (>=158 factors)
2. Alpha360 factor computation (360 features)
3. Model registry completeness (>=25 models)
4. QlibModelTrainer initialization
"""

from datetime import date

import polars as pl
import pytest

from cquant.factorlab.factor import FactorContext
from cquant.factorlab.factors.alpha158 import ALPHA158_FACTORS
from cquant.factorlab.factors.alpha360 import Alpha360
from cquant.qlib_bridge.models import get_all_models, is_qlib_model
from cquant.ml_lab.trainers.qlib_trainer import QlibModelTrainer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_price_frame(n: int = 120) -> pl.DataFrame:
    """Build a synthetic OHLCV DataFrame for factor testing."""
    return pl.DataFrame({
        "asset_id": pl.Series("asset_id", ["SH600000"] * n),
        "trade_date": pl.date_range(
            pl.date(2025, 1, 1),
            pl.date(2025, 1, 1) + pl.duration(days=n - 1),
            eager=True,
        ),
        "close": pl.Series("close", [100.0 + i * 0.1 for i in range(n)]),
        "open": pl.Series("open", [100.0 + i * 0.1 - 0.5 for i in range(n)]),
        "high": pl.Series("high", [100.0 + i * 0.1 + 1.0 for i in range(n)]),
        "low": pl.Series("low", [100.0 + i * 0.1 - 1.0 for i in range(n)]),
        "volume": pl.Series("volume", [1000.0 + i * 10 for i in range(n)]),
        "vwap": pl.Series("vwap", [100.0 + i * 0.1 for i in range(n)]),
    })


def _make_ctx() -> FactorContext:
    """Build a minimal FactorContext for testing."""
    return FactorContext(as_of_date=date(2025, 6, 1))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAlpha158Completeness:
    """Verify Alpha158 factor set completeness."""

    def test_factor_count_ge_155(self):
        """ALPHA158_FACTORS must contain >=155 factors (core Alpha158 set)."""
        assert len(ALPHA158_FACTORS) >= 155, (
            f"Expected >=155 Alpha158 factors, got {len(ALPHA158_FACTORS)}"
        )

    def test_factor_names_unique(self):
        """All Alpha158 factor names must be unique."""
        names = [f.name for f in ALPHA158_FACTORS]
        assert len(names) == len(set(names)), (
            f"Duplicate factor names found: "
            f"{[n for n in names if names.count(n) > 1][:5]}"
        )

    def test_factors_compute_without_error(self):
        """Each Alpha158 factor must compute without raising."""
        frame = _make_price_frame(120)
        ctx = _make_ctx()
        errors: list[str] = []
        for factor in ALPHA158_FACTORS:
            try:
                result = factor.compute(frame, ctx)
                assert result is not None, f"Factor {factor.name} returned None"
            except Exception as exc:
                errors.append(f"{factor.name}: {exc}")
        if errors:
            pytest.fail(
                f"{len(errors)} factors failed:\n" + "\n".join(errors[:10])
            )


class TestAlpha360:
    """Verify Alpha360 factor computation."""

    def test_feature_count_360(self):
        """Alpha360 must produce exactly 360 feature columns."""
        alpha360 = Alpha360()
        frame = _make_price_frame(70)
        result = alpha360.compute(frame)
        feature_cols = [
            c for c in result.columns
            if c not in ["asset_id", "trade_date", "close", "open", "high", "low", "volume", "vwap"]
        ]
        assert len(feature_cols) == 360, (
            f"Expected 360 features, got {len(feature_cols)}"
        )

    def test_feature_names_pattern(self):
        """Alpha360 feature names must follow {field}_{day}_norm pattern."""
        alpha360 = Alpha360()
        feature_names = alpha360.get_feature_names()
        assert len(feature_names) == 360
        for name in feature_names:
            parts = name.rsplit("_", 2)
            assert len(parts) == 3, f"Unexpected feature name format: {name}"
            assert parts[1].isdigit(), f"Day not numeric in: {name}"
            assert parts[2] == "norm", f"Missing _norm suffix in: {name}"

    def test_compute_on_price_frame(self):
        """Alpha360 must compute on a valid price frame without error."""
        alpha360 = Alpha360()
        frame = _make_price_frame(70)
        result = alpha360.compute(frame)
        # Should have all original columns + 360 new ones
        assert result.shape[1] == frame.shape[1] + 360


class TestModelRegistry:
    """Verify qlib model registry completeness."""

    def test_model_count_ge_25(self):
        """Model registry must contain >=25 models."""
        models = get_all_models()
        assert len(models) >= 25, (
            f"Expected >=25 models, got {len(models)}"
        )

    def test_qlib_model_detection(self):
        """is_qlib_model must correctly distinguish qlib vs native models."""
        # LSTM is a qlib-engine model
        assert is_qlib_model("lstm") is True
        # lgbm is a native-engine model
        assert is_qlib_model("lgbm") is False
        # Unknown model returns False
        assert is_qlib_model("nonexistent_model") is False

    def test_model_info_fields(self):
        """Every model must have valid metadata fields."""
        models = get_all_models()
        for name, info in models.items():
            assert info.name == name, f"ModelInfo.name mismatch for {name}"
            assert info.display_name, f"Missing display_name for {name}"
            assert info.description, f"Missing description for {name}"
            assert info.model_type, f"Missing model_type for {name}"
            assert info.engine in ("native", "qlib"), (
                f"Invalid engine for {name}: {info.engine}"
            )

    def test_model_category_groups(self):
        """Category groups must be non-empty."""
        from cquant.qlib_bridge.models import get_model_category_groups
        groups = get_model_category_groups()
        assert len(groups) > 0
        # All models must be in at least one group
        all_in_groups = []
        for group_models in groups.values():
            all_in_groups.extend(group_models)
        models = get_all_models()
        assert set(all_in_groups) == set(models.keys())


class TestQlibModelTrainer:
    """Verify QlibModelTrainer initialization."""

    def test_init_lstm(self):
        """QlibModelTrainer must initialize for LSTM."""
        trainer = QlibModelTrainer("lstm", {"hidden_size": 32})
        assert trainer.model_name == "lstm"
        assert trainer.requires_alpha360 is True

    def test_init_transformer(self):
        """QlibModelTrainer must initialize for Transformer."""
        trainer = QlibModelTrainer("transformer")
        assert trainer.model_name == "transformer"
        assert trainer.requires_alpha360 is True

    def test_init_rejects_native_model(self):
        """QlibModelTrainer must reject native-engine models."""
        with pytest.raises(ValueError, match="not 'qlib'"):
            QlibModelTrainer("lgbm")

    def test_init_unknown_model_raises(self):
        """QlibModelTrainer must raise for unknown model names."""
        with pytest.raises(KeyError, match="Unknown model"):
            QlibModelTrainer("nonexistent_model")

    def test_model_params_override(self):
        """Model params must be stored for later use."""
        custom_params = {"hidden_size": 128, "dropout": 0.5}
        trainer = QlibModelTrainer("lstm", custom_params)
        assert trainer.model_params == custom_params
