"""Tests for DSL parser."""
import pytest
from cquant.factorlab.dsl_parser import (
    parse, tokenize, NumberNode, ColumnNode, BinaryOpNode,
    UnaryOpNode, FunctionCallNode,
)


class TestTokenize:
    def test_numbers(self):
        tokens = tokenize("3.14")
        assert tokens[0].value == "3.14"

    def test_identifiers(self):
        tokens = tokenize("close")
        assert tokens[0].value == "close"

    def test_operators(self):
        tokens = tokenize("a + b * c")
        types = [t.type.name for t in tokens if t.type.name != 'EOF']
        assert types == ['IDENT', 'PLUS', 'IDENT', 'STAR', 'IDENT']

    def test_comparison(self):
        tokens = tokenize("a >= b")
        assert tokens[0].type.name == 'IDENT'
        assert tokens[1].type.name == 'GTE'


class TestParse:
    def test_number(self):
        ast = parse("42")
        assert isinstance(ast, NumberNode)
        assert ast.value == 42.0

    def test_column(self):
        ast = parse("close")
        assert isinstance(ast, ColumnNode)
        assert ast.name == "close"

    def test_binary_add(self):
        ast = parse("close + open")
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == '+'

    def test_precedence(self):
        ast = parse("a + b * c")
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == '+'
        assert isinstance(ast.right, BinaryOpNode)
        assert ast.right.op == '*'

    def test_unary_neg(self):
        ast = parse("-close")
        assert isinstance(ast, UnaryOpNode)
        assert ast.op == '-'

    def test_function_call(self):
        ast = parse("ma(close, 20)")
        assert isinstance(ast, FunctionCallNode)
        assert ast.name == "ma"
        assert len(ast.args) == 2

    def test_nested_function(self):
        ast = parse("rank(close / lag(close, 5) - 1)")
        assert isinstance(ast, FunctionCallNode)
        assert ast.name == "rank"

    def test_comparison_op(self):
        ast = parse("close > open")
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == '>'

    def test_parenthesized(self):
        ast = parse("(close + open) / 2")
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == '/'
        assert isinstance(ast.left, BinaryOpNode)

    def test_complex_expression(self):
        expr = "(close - ma(close, 20)) / std(close, 20)"
        ast = parse(expr)
        assert isinstance(ast, BinaryOpNode)
        assert ast.op == '/'

    def test_syntax_error(self):
        with pytest.raises(SyntaxError):
            parse("close +")

    def test_unknown_char(self):
        with pytest.raises(SyntaxError):
            parse("close $ open")
