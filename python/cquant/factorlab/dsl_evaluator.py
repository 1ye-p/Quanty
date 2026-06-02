"""Compile DSL AST into Polars expressions."""

from __future__ import annotations
from typing import Any

import polars as pl

from cquant.factorlab.dsl_parser import (
    ASTNode, NumberNode, ColumnNode, BinaryOpNode, UnaryOpNode, FunctionCallNode,
)
from cquant.factorlab.dsl_functions import FUNCTIONS, AVAILABLE_COLUMNS


class DSLError(Exception):
    pass


def _evaluate_func_arg(node: ASTNode) -> pl.Expr | int | float:
    """Evaluate a function argument — return scalar for NumberNode, Expr otherwise."""
    if isinstance(node, NumberNode):
        v = node.value
        return int(v) if v == int(v) else v
    return evaluate(node)


def evaluate(node: ASTNode) -> pl.Expr:
    """Compile an AST node into a Polars expression."""
    if isinstance(node, NumberNode):
        return pl.lit(node.value)

    if isinstance(node, ColumnNode):
        if node.name not in AVAILABLE_COLUMNS:
            raise DSLError(f"Unknown column: '{node.name}'. Available: {sorted(AVAILABLE_COLUMNS)}")
        return pl.col(node.name)

    if isinstance(node, UnaryOpNode):
        operand = evaluate(node.operand)
        if node.op == '-':
            return -operand
        raise DSLError(f"Unknown unary operator: {node.op}")

    if isinstance(node, BinaryOpNode):
        left = evaluate(node.left)
        right = evaluate(node.right)
        ops = {
            '+': lambda l, r: l + r,
            '-': lambda l, r: l - r,
            '*': lambda l, r: l * r,
            '/': lambda l, r: l / r,
            '^': lambda l, r: l ** r,
            '>': lambda l, r: (l > r).cast(pl.Int8),
            '<': lambda l, r: (l < r).cast(pl.Int8),
            '>=': lambda l, r: (l >= r).cast(pl.Int8),
            '<=': lambda l, r: (l <= r).cast(pl.Int8),
            '==': lambda l, r: (l == r).cast(pl.Int8),
            '!=': lambda l, r: (l != r).cast(pl.Int8),
        }
        if node.op not in ops:
            raise DSLError(f"Unknown operator: {node.op}")
        return ops[node.op](left, right)

    if isinstance(node, FunctionCallNode):
        if node.name not in FUNCTIONS:
            raise DSLError(f"Unknown function: '{node.name}'. Available: {sorted(FUNCTIONS.keys())}")
        fn, min_args, max_args, _ = FUNCTIONS[node.name]
        nargs = len(node.args)
        if nargs < min_args or nargs > max_args:
            raise DSLError(
                f"'{node.name}' expects {min_args}-{max_args} args, got {nargs}"
            )
        evaluated_args = [_evaluate_func_arg(a) for a in node.args]
        return fn(*evaluated_args)

    raise DSLError(f"Unknown AST node type: {type(node).__name__}")


def compile_expression(expression: str) -> pl.Expr:
    """Parse and compile a DSL expression string into a Polars expression."""
    from cquant.factorlab.dsl_parser import parse
    ast = parse(expression)
    return evaluate(ast)
