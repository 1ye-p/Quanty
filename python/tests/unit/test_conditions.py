"""Tests for condition DSL parser, evaluator, and let binding support."""

from datetime import date

import polars as pl
import pytest

from cquant.indicator.conditions import (
    Comparison,
    CrossOver,
    Duration,
    LogicalAnd,
    LogicalNot,
    LogicalOr,
    Within,
    evaluate_condition,
    parse_condition,
    signals_as_mask,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data() -> pl.DataFrame:
    """Create sample DataFrame with indicator columns."""
    return pl.DataFrame({
        "trade_date": [date(2025, 1, i) for i in range(1, 11)],
        "close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
        "rsi(14)": [25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0],
        "sma(20)": [102.0, 102.5, 103.0, 103.5, 104.0, 104.5, 105.0, 105.5, 106.0, 106.5],
        "sma(50)": [98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
        "ema(close,10)": [101.0, 101.5, 102.0, 102.5, 103.0, 103.5, 104.0, 104.5, 105.0, 105.5],
        "volume": [1_000_000, 1_100_000, 1_200_000, 1_300_000, 1_400_000,
                   1_500_000, 1_600_000, 1_700_000, 1_800_000, 1_900_000],
    })


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParseCondition:
    def test_comparison_gt(self):
        cond = parse_condition("rsi(14) > 70")
        assert isinstance(cond, Comparison)
        assert cond.left == "rsi(14)"
        assert cond.op == ">"
        assert cond.right == "70"

    def test_comparison_lt(self):
        cond = parse_condition("close < 100")
        assert isinstance(cond, Comparison)
        assert cond.left == "close"
        assert cond.op == "<"
        assert cond.right == "100"

    def test_comparison_gte(self):
        cond = parse_condition("rsi(14) >= 50")
        assert isinstance(cond, Comparison)
        assert cond.op == ">="

    def test_comparison_eq(self):
        cond = parse_condition("close == 100")
        assert isinstance(cond, Comparison)
        assert cond.op == "=="

    def test_comparison_neq(self):
        cond = parse_condition("close != 0")
        assert isinstance(cond, Comparison)
        assert cond.op == "!="

    def test_crossover_above(self):
        cond = parse_condition("sma(5) crosses_above sma(20)")
        assert isinstance(cond, CrossOver)
        assert cond.left == "sma(5)"
        assert cond.direction == "crosses_above"
        assert cond.right == "sma(20)"

    def test_crossover_below(self):
        cond = parse_condition("ema(close,10) crosses_below sma(50)")
        assert isinstance(cond, CrossOver)
        assert cond.direction == "crosses_below"

    def test_logical_and(self):
        cond = parse_condition("rsi(14) < 30 AND close > sma(20)")
        assert isinstance(cond, LogicalAnd)
        assert isinstance(cond.left, Comparison)
        assert isinstance(cond.right, Comparison)

    def test_logical_or(self):
        cond = parse_condition("rsi(14) < 30 OR rsi(14) > 70")
        assert isinstance(cond, LogicalOr)

    def test_logical_not(self):
        cond = parse_condition("NOT rsi(14) > 80")
        assert isinstance(cond, LogicalNot)
        assert isinstance(cond.operand, Comparison)

    def test_duration(self):
        cond = parse_condition("rsi(14) < 30 for 5 bars")
        assert isinstance(cond, Duration)
        assert cond.bars == 5

    def test_within(self):
        cond = parse_condition("close > sma(20) within 10 bars")
        assert isinstance(cond, Within)
        assert cond.bars == 10

    def test_parentheses(self):
        cond = parse_condition("(rsi(14) < 30 OR rsi(14) > 70) AND close > sma(20)")
        assert isinstance(cond, LogicalAnd)
        assert isinstance(cond.left, LogicalOr)

    def test_complex_expression(self):
        cond = parse_condition(
            "rsi(14) < 30 AND close > sma(20) AND volume > 1000000"
        )
        assert isinstance(cond, LogicalAnd)

    def test_invalid_expression(self):
        with pytest.raises(SyntaxError):
            parse_condition("rsi(14)")

    def test_empty_expression(self):
        with pytest.raises(SyntaxError):
            parse_condition("")


# ---------------------------------------------------------------------------
# Evaluator tests
# ---------------------------------------------------------------------------

class TestEvaluateCondition:
    def test_comparison_gt(self, sample_data):
        result = evaluate_condition(sample_data, "rsi(14) > 65")
        assert result["hit_count"] == 1  # Only 70 > 65
        assert result["total_bars"] == 10
        assert len(result["signals"]) == 10

    def test_comparison_lt(self, sample_data):
        result = evaluate_condition(sample_data, "rsi(14) < 35")
        assert result["hit_count"] == 2  # 25, 30 < 35

    def test_crossover(self, sample_data):
        # sma(5) crosses_above sma(20): need sma(5) column
        data = sample_data.with_columns(
            pl.Series("sma(5)", [101.0, 102.0, 103.0, 104.0, 105.0,
                                  106.0, 107.0, 108.0, 109.0, 110.0])
        )
        result = evaluate_condition(data, "sma(5) crosses_above sma(20)")
        assert "signals" in result
        assert len(result["signals"]) == 10

    def test_logical_and(self, sample_data):
        result = evaluate_condition(sample_data, "rsi(14) > 50 AND close > sma(20)")
        assert "signals" in result

    def test_signal_dates(self, sample_data):
        result = evaluate_condition(sample_data, "rsi(14) > 65")
        assert "signal_dates" in result
        assert len(result["signal_dates"]) == result["hit_count"]

    def test_hit_rate(self, sample_data):
        result = evaluate_condition(sample_data, "rsi(14) > 65")
        expected_rate = result["hit_count"] / result["total_bars"]
        assert abs(result["hit_rate"] - expected_rate) < 1e-10


# ---------------------------------------------------------------------------
# Let binding tests
# ---------------------------------------------------------------------------

class TestLetBindings:
    def test_simple_let_binding(self, sample_data):
        """Let binding creates an alias for an existing column."""
        dsl = """let my_rsi = rsi(14)
my_rsi > 65"""
        result = evaluate_condition(sample_data, dsl)
        assert result["hit_count"] == 1  # Only 70 > 65

    def test_multiple_let_bindings(self, sample_data):
        """Multiple let bindings create multiple aliases."""
        dsl = """let fast = rsi(14)
let slow = sma(20)
fast > 50 AND close > slow"""
        result = evaluate_condition(sample_data, dsl)
        assert "signals" in result

    def test_let_binding_with_crossover(self, sample_data):
        """Let bindings work with crossover conditions."""
        dsl = """let fast_ma = ema(close,10)
let slow_ma = sma(50)
fast_ma crosses_above slow_ma"""
        result = evaluate_condition(sample_data, dsl)
        assert "signals" in result

    def test_let_binding_with_blank_lines(self, sample_data):
        """Blank lines are ignored in multi-line DSL."""
        dsl = """let my_rsi = rsi(14)

my_rsi > 65"""
        result = evaluate_condition(sample_data, dsl)
        assert result["hit_count"] == 1

    def test_let_binding_invalid_name(self, sample_data):
        """Invalid variable names raise SyntaxError."""
        dsl = """let 123invalid = rsi(14)
123invalid > 65"""
        with pytest.raises(SyntaxError, match="Invalid variable name"):
            evaluate_condition(sample_data, dsl)

    def test_let_binding_missing_equals(self, sample_data):
        """Missing equals sign raises SyntaxError."""
        dsl = """let my_rsi rsi(14)
my_rsi > 65"""
        with pytest.raises(SyntaxError, match="Invalid let binding"):
            evaluate_condition(sample_data, dsl)

    def test_let_binding_empty_name(self, sample_data):
        """Empty variable name raises SyntaxError."""
        dsl = """let  = rsi(14)
> 65"""
        with pytest.raises(SyntaxError, match="Invalid let binding"):
            evaluate_condition(sample_data, dsl)

    def test_let_binding_missing_column(self, sample_data):
        """Referencing non-existent column raises ValueError."""
        dsl = """let my_var = nonexistent_column
my_var > 65"""
        with pytest.raises(ValueError, match="not found in data"):
            evaluate_condition(sample_data, dsl)

    def test_no_condition_line(self, sample_data):
        """Only let bindings without condition raises SyntaxError."""
        dsl = """let my_rsi = rsi(14)"""
        with pytest.raises(SyntaxError, match="No condition expression found"):
            evaluate_condition(sample_data, dsl)

    def test_let_binding_does_not_modify_original(self, sample_data):
        """Let bindings don't modify the original DataFrame."""
        original_columns = set(sample_data.columns)
        dsl = """let my_alias = close
my_alias > 105"""
        evaluate_condition(sample_data, dsl)
        assert set(sample_data.columns) == original_columns

    def test_let_binding_with_temporal(self, sample_data):
        """Let bindings work with temporal modifiers."""
        dsl = """let my_rsi = rsi(14)
my_rsi < 50 for 3 bars"""
        result = evaluate_condition(sample_data, dsl)
        assert "signals" in result


# ---------------------------------------------------------------------------
# signals_as_mask tests
# ---------------------------------------------------------------------------

class TestSignalsAsMask:
    def test_returns_boolean_series(self, sample_data):
        mask = signals_as_mask(sample_data, "rsi(14) > 65")
        assert isinstance(mask, pl.Series)
        assert mask.dtype == pl.Boolean
        assert len(mask) == 10

    def test_with_let_bindings(self, sample_data):
        mask = signals_as_mask(sample_data, "let my_rsi = rsi(14)\nmy_rsi > 65")
        assert isinstance(mask, pl.Series)
        assert mask.dtype == pl.Boolean
        assert mask.sum() == 1


# ---------------------------------------------------------------------------
# _extract_indicator_refs tests (let binding support)
# ---------------------------------------------------------------------------

class TestExtractIndicatorRefsLetBindings:
    def test_let_binding_extracts_indicators(self):
        from cquant.backtest_vector.strategies.indicator_signal import _extract_indicator_refs

        dsl = """let fast_ma = ema(close, 10)
let slow_ma = ema(close, 30)
fast_ma crosses_above slow_ma"""
        refs = _extract_indicator_refs([dsl])
        names = {r["col_name"] for r in refs}
        assert "ema(close, 10)" in names
        assert "ema(close, 30)" in names

    def test_let_binding_deduplication(self):
        from cquant.backtest_vector.strategies.indicator_signal import _extract_indicator_refs

        dsl = """let my_rsi = rsi(14)
my_rsi > 50"""
        refs = _extract_indicator_refs([dsl, "rsi(14) > 70"])
        rsi_refs = [r for r in refs if r["col_name"] == "rsi(14)"]
        assert len(rsi_refs) == 1

    def test_let_binding_with_condition_line(self):
        from cquant.backtest_vector.strategies.indicator_signal import _extract_indicator_refs

        dsl = """let fast = sma(5)
let slow = sma(20)
fast crosses_above slow"""
        refs = _extract_indicator_refs([dsl])
        names = {r["col_name"] for r in refs}
        assert "sma(5)" in names
        assert "sma(20)" in names
