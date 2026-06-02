"""Tests for DSL evaluator."""
import pytest
import polars as pl
from cquant.factorlab.dsl_evaluator import compile_expression, DSLError


@pytest.fixture
def sample_frame():
    return pl.DataFrame({
        "close": [10.0, 11.0, 12.0, 13.0, 14.0],
        "open": [9.5, 10.5, 11.5, 12.5, 13.5],
        "high": [10.5, 11.5, 12.5, 13.5, 14.5],
        "low": [9.0, 10.0, 11.0, 12.0, 13.0],
        "volume": [1000, 1200, 1100, 1300, 1400],
        "amount": [10000, 13200, 13200, 16900, 19600],
        "turnover": [0.01, 0.012, 0.011, 0.013, 0.014],
    })


class TestCompileExpression:
    def test_column_ref(self, sample_frame):
        expr = compile_expression("close")
        result = sample_frame.select(expr.alias("v"))["v"]
        assert result.to_list() == [10.0, 11.0, 12.0, 13.0, 14.0]

    def test_arithmetic(self, sample_frame):
        expr = compile_expression("close + open")
        result = sample_frame.select(expr.alias("v"))["v"]
        assert result.to_list() == [19.5, 21.5, 23.5, 25.5, 27.5]

    def test_lag(self, sample_frame):
        expr = compile_expression("lag(close, 1)")
        result = sample_frame.select(expr.alias("v"))["v"]
        assert result.to_list()[0] is None
        assert result.to_list()[1] == 10.0

    def test_ma(self, sample_frame):
        expr = compile_expression("ma(close, 3)")
        result = sample_frame.select(expr.alias("v"))["v"]
        assert result.to_list()[2] == pytest.approx(11.0)

    def test_rank(self, sample_frame):
        expr = compile_expression("rank(close)")
        result = sample_frame.select(expr.alias("v"))["v"]
        vals = result.to_list()
        assert all(v is not None for v in vals)
        assert vals == sorted(vals)

    def test_comparison_returns_int(self, sample_frame):
        expr = compile_expression("close > open")
        result = sample_frame.select(expr.alias("v"))["v"]
        assert result.to_list() == [1, 1, 1, 1, 1]

    def test_complex_expression(self, sample_frame):
        expr = compile_expression("(close - ma(close, 3)) / std(close, 3)")
        result = sample_frame.select(expr.alias("v"))["v"]
        assert len(result) == 5

    def test_unknown_column(self):
        with pytest.raises(DSLError, match="Unknown column"):
            compile_expression("foobar")

    def test_unknown_function(self):
        with pytest.raises(DSLError, match="Unknown function"):
            compile_expression("foobar(close)")

    def test_wrong_arg_count(self):
        with pytest.raises(DSLError, match="expects"):
            compile_expression("lag(close)")

    def test_negation(self, sample_frame):
        expr = compile_expression("-close")
        result = sample_frame.select(expr.alias("v"))["v"]
        assert result.to_list() == [-10.0, -11.0, -12.0, -13.0, -14.0]
