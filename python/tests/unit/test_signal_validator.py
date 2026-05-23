"""测试 SignalFrame 输入验证工具。"""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.backtest_vector.signal_validator import validate_signals, SignalValidationResult


def _valid_signals() -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": ["SSE:600036", "SSE:000001"],
        "signal_date": [date(2025, 6, 1)] * 2,
        "direction": ["long", "long"],
        "strength": [0.6, 0.4],
        "confidence": [1.0, 0.9],
    })


class TestValidateSignals:
    def test_valid_signals_pass(self) -> None:
        result = validate_signals(_valid_signals())
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_required_column_fails(self) -> None:
        df = _valid_signals().drop("strength")
        result = validate_signals(df)
        assert not result.is_valid
        assert any("strength" in e for e in result.errors)

    def test_negative_strength_fails(self) -> None:
        df = _valid_signals().with_columns(pl.lit(-0.5).alias("strength"))
        result = validate_signals(df)
        assert not result.is_valid
        assert any("strength" in e.lower() for e in result.errors)

    def test_invalid_direction_fails(self) -> None:
        df = _valid_signals().with_columns(pl.lit("hold").alias("direction"))
        result = validate_signals(df)
        assert not result.is_valid
        assert any("direction" in e.lower() for e in result.errors)

    def test_empty_asset_id_fails(self) -> None:
        df = _valid_signals().with_columns(pl.lit("").alias("asset_id"))
        result = validate_signals(df)
        assert not result.is_valid

    def test_empty_dataframe_is_valid(self) -> None:
        df = pl.DataFrame(
            schema={
                "asset_id": pl.Utf8, "signal_date": pl.Date,
                "direction": pl.Utf8, "strength": pl.Float64, "confidence": pl.Float64,
            }
        )
        result = validate_signals(df)
        assert result.is_valid
