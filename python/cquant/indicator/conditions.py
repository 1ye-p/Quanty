"""Condition DSL — parse and evaluate strategy signal conditions on Polars DataFrames.

Supports a mini-DSL for defining trading signals::

    # Comparisons
    "rsi(14) > 70"
    "close > sma(20)"
    "volume > volume_sma(20) * 1.5"

    # Crossovers
    "sma(5) crosses_above sma(20)"
    "macd crosses_below signal"

    # Logical composition
    "rsi(14) < 30 AND close > sma(20)"
    "close > sma(50) OR rsi(14) < 25"
    "NOT rsi(14) > 80"

    # Temporal modifiers
    "rsi(14) < 30 for 5 bars"       -- true if held for 5 consecutive bars
    "close > sma(20) within 10 bars" -- true if occurred at least once in last 10 bars

    # Parentheses
    "(rsi(14) < 30 OR kdj_j < 20) AND close > sma(20)"
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any

import polars as pl


# ---------------------------------------------------------------------------
# AST Nodes
# ---------------------------------------------------------------------------

class Condition(ABC):
    """Base class for all condition AST nodes."""

    @abstractmethod
    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        """Return boolean Series indicating where condition is true."""
        ...


class Comparison(Condition):
    """Binary comparison: left op right.

    ``left`` and ``right`` are column names or numeric literals.
    ``op`` is one of: >, <, >=, <=, ==, !=
    """

    def __init__(self, left: str, op: str, right: str) -> None:
        self.left = left
        self.op = op
        self.right = right

    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        left_col = self._resolve(data, self.left, len(data))
        right_col = self._resolve(data, self.right, len(data))

        ops = {
            ">": left_col > right_col,
            "<": left_col < right_col,
            ">=": left_col >= right_col,
            "<=": left_col <= right_col,
            "==": left_col == right_col,
            "!=": left_col != right_col,
        }
        result = ops.get(self.op)
        if result is None:
            raise ValueError(f"Unsupported operator: {self.op!r}")
        return result

    @staticmethod
    def _resolve(data: pl.DataFrame, token: str, length: int | None = None) -> pl.Series:
        """Resolve a token to a Series (column or broadcast literal)."""
        if token in data.columns:
            return data[token]
        try:
            n = length if length is not None else len(data)
            return pl.Series([float(token)] * n)
        except ValueError:
            raise ValueError(
                f"Token {token!r} is not a column name or numeric literal"
            )

    def __repr__(self) -> str:
        return f"Comparison({self.left!r}, {self.op!r}, {self.right!r})"


class CrossOver(Condition):
    """Crossover condition: ``a crosses_above b`` or ``a crosses_below b``.

    ``crosses_above``: a was <= b at t-1 and a > b at t.
    ``crosses_below``: a was >= b at t-1 and a < b at t.
    """

    def __init__(self, left: str, direction: str, right: str) -> None:
        self.left = left
        self.direction = direction  # 'crosses_above' | 'crosses_below'
        self.right = right

    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        a = data[self.left]
        b = data[self.right]
        prev_a = a.shift(1)
        prev_b = b.shift(1)

        if self.direction == "crosses_above":
            return (prev_a <= prev_b) & (a > b)
        else:  # crosses_below
            return (prev_a >= prev_b) & (a < b)

    def __repr__(self) -> str:
        return f"CrossOver({self.left!r}, {self.direction!r}, {self.right!r})"


class LogicalAnd(Condition):
    """Logical AND of two conditions."""

    def __init__(self, left: Condition, right: Condition) -> None:
        self.left = left
        self.right = right

    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        return self.left.evaluate(data) & self.right.evaluate(data)

    def __repr__(self) -> str:
        return f"LogicalAnd({self.left!r}, {self.right!r})"


class LogicalOr(Condition):
    """Logical OR of two conditions."""

    def __init__(self, left: Condition, right: Condition) -> None:
        self.left = left
        self.right = right

    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        return self.left.evaluate(data) | self.right.evaluate(data)

    def __repr__(self) -> str:
        return f"LogicalOr({self.left!r}, {self.right!r})"


class LogicalNot(Condition):
    """Logical NOT of a condition."""

    def __init__(self, operand: Condition) -> None:
        self.operand = operand

    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        return ~self.operand.evaluate(data)

    def __repr__(self) -> str:
        return f"LogicalNot({self.operand!r})"


class Duration(Condition):
    """Temporal modifier: ``cond for N bars``.

    True at bar t if the inner condition was true for each of the last N bars
    (including bar t).
    """

    def __init__(self, operand: Condition, bars: int) -> None:
        self.operand = operand
        self.bars = bars

    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        raw = self.operand.evaluate(data).cast(pl.Int32)
        rolling_sum = raw.rolling_sum(window_size=self.bars)
        return rolling_sum >= self.bars

    def __repr__(self) -> str:
        return f"Duration({self.operand!r}, {self.bars})"


class Within(Condition):
    """Temporal modifier: ``cond within N bars``.

    True at bar t if the inner condition was true at least once in the last N
    bars (including bar t).
    """

    def __init__(self, operand: Condition, bars: int) -> None:
        self.operand = operand
        self.bars = bars

    def evaluate(self, data: pl.DataFrame) -> pl.Series:
        raw = self.operand.evaluate(data).cast(pl.Int32)
        rolling_max = raw.rolling_max(window_size=self.bars)
        return rolling_max >= 1

    def __repr__(self) -> str:
        return f"Within({self.operand!r}, {self.bars})"


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class _TokenType(Enum):
    IDENT = auto()       # column name or indicator name like rsi(14), sma(20)
    NUMBER = auto()      # numeric literal
    COMP_OP = auto()     # >, <, >=, <=, ==, !=
    CROSS_OP = auto()    # crosses_above, crosses_below
    AND = auto()
    OR = auto()
    NOT = auto()
    FOR = auto()
    WITHIN = auto()
    BARS = auto()
    LPAREN = auto()
    RPAREN = auto()
    EOF = auto()


class _Token:
    __slots__ = ("type", "value")

    def __init__(self, type_: _TokenType, value: str) -> None:
        self.type = type_
        self.value = value

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r})"


# Token patterns ordered so longer operators match first.
_TOKEN_PATTERNS: list[tuple[str, _TokenType | None]] = [
    (r"\s+", None),                          # whitespace — skip
    (r"crosses_above", _TokenType.CROSS_OP),
    (r"crosses_below", _TokenType.CROSS_OP),
    (r">=", _TokenType.COMP_OP),
    (r"<=", _TokenType.COMP_OP),
    (r"!=", _TokenType.COMP_OP),
    (r"==", _TokenType.COMP_OP),
    (r">", _TokenType.COMP_OP),
    (r"<", _TokenType.COMP_OP),
    (r"\(", _TokenType.LPAREN),
    (r"\)", _TokenType.RPAREN),
    (r"\bAND\b", _TokenType.AND),
    (r"\bOR\b", _TokenType.OR),
    (r"\bNOT\b", _TokenType.NOT),
    (r"\bfor\b", _TokenType.FOR),
    (r"\bwithin\b", _TokenType.WITHIN),
    (r"\bbars\b", _TokenType.BARS),
    (r"[0-9]+(?:\.[0-9]+)?", _TokenType.NUMBER),
    (r"[a-zA-Z_][a-zA-Z0-9_]*(?:\([^)]*\))?", _TokenType.IDENT),
]

_MASTER_RE = re.compile(
    "|".join(f"(?P<G{i}>{pat})" for i, (pat, _) in enumerate(_TOKEN_PATTERNS))
)


def _tokenize(dsl: str) -> list[_Token]:
    """Tokenize a DSL string."""
    tokens: list[_Token] = []
    pos = 0
    while pos < len(dsl):
        m = _MASTER_RE.match(dsl, pos)
        if m is None:
            raise SyntaxError(
                f"Unexpected character {dsl[pos]!r} at position {pos} in DSL: {dsl!r}"
            )
        # Find which group matched
        for i, (_, tok_type) in enumerate(_TOKEN_PATTERNS):
            val = m.group(f"G{i}")
            if val is not None:
                if tok_type is not None:
                    tokens.append(_Token(tok_type, val))
                break
        pos = m.end()
    tokens.append(_Token(_TokenType.EOF, ""))
    return tokens


# ---------------------------------------------------------------------------
# Recursive-descent parser
# ---------------------------------------------------------------------------

class _Parser:
    """Parse tokens into a Condition AST.

    Grammar (precedence low -> high)::

        expr     -> or_expr
        or_expr  -> and_expr ( OR and_expr )*
        and_expr -> unary ( AND unary )*
        unary    -> NOT unary | temporal
        temporal -> primary ( (FOR | WITHIN) NUMBER )?
        primary  -> comparison | crossover | '(' expr ')'
        comparison -> IDENT COMP_OP (IDENT | NUMBER)
        crossover  -> IDENT CROSS_OP IDENT
    """

    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # -- helpers --

    def _peek(self) -> _Token:
        return self._tokens[self._pos]

    def _advance(self) -> _Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, type_: _TokenType) -> _Token:
        tok = self._advance()
        if tok.type != type_:
            raise SyntaxError(
                f"Expected {type_.name}, got {tok.type.name} ({tok.value!r})"
            )
        return tok

    # -- grammar rules --

    def parse(self) -> Condition:
        cond = self._or_expr()
        self._expect(_TokenType.EOF)
        return cond

    def _or_expr(self) -> Condition:
        left = self._and_expr()
        while self._peek().type == _TokenType.OR:
            self._advance()
            right = self._and_expr()
            left = LogicalOr(left, right)
        return left

    def _and_expr(self) -> Condition:
        left = self._unary()
        while self._peek().type == _TokenType.AND:
            self._advance()
            right = self._unary()
            left = LogicalAnd(left, right)
        return left

    def _unary(self) -> Condition:
        if self._peek().type == _TokenType.NOT:
            self._advance()
            operand = self._unary()
            return LogicalNot(operand)
        return self._temporal()

    def _temporal(self) -> Condition:
        cond = self._primary()
        if self._peek().type in (_TokenType.FOR, _TokenType.WITHIN):
            tok = self._advance()
            num_tok = self._expect(_TokenType.NUMBER)
            bars = int(num_tok.value)
            if bars < 1:
                raise SyntaxError(f"Temporal modifier bars must be >= 1, got {bars}")
            # Optionally consume trailing "bars" keyword
            if self._peek().type == _TokenType.BARS:
                self._advance()
            if tok.type == _TokenType.FOR:
                return Duration(cond, bars)
            else:
                return Within(cond, bars)
        return cond

    def _primary(self) -> Condition:
        tok = self._peek()

        # Parenthesised sub-expression
        if tok.type == _TokenType.LPAREN:
            self._advance()
            cond = self._or_expr()
            self._expect(_TokenType.RPAREN)
            return cond

        # Must be comparison or crossover — starts with an IDENT
        self._expect(_TokenType.IDENT)
        left = tok.value

        op_tok = self._peek()

        # Crossover: IDENT crosses_above/below IDENT
        if op_tok.type == _TokenType.CROSS_OP:
            self._advance()
            right_tok = self._expect(_TokenType.IDENT)
            return CrossOver(left, op_tok.value, right_tok.value)

        # Comparison: IDENT comp_op (IDENT | NUMBER)
        if op_tok.type == _TokenType.COMP_OP:
            self._advance()
            rhs_tok = self._advance()
            if rhs_tok.type not in (_TokenType.IDENT, _TokenType.NUMBER):
                raise SyntaxError(
                    f"Expected identifier or number, got {rhs_tok.type.name} ({rhs_tok.value!r})"
                )
            return Comparison(left, op_tok.value, rhs_tok.value)

        raise SyntaxError(
            f"Expected operator after {left!r}, got {op_tok.type.name} ({op_tok.value!r})"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_condition(dsl: str) -> Condition:
    """Parse a condition DSL string into an AST.

    Args:
        dsl: Condition DSL string, e.g. ``"rsi(14) > 70"``.

    Returns:
        Root ``Condition`` node.

    Raises:
        SyntaxError: If the DSL is malformed.

    Examples::

        >>> parse_condition("rsi(14) > 70")
        Comparison('rsi(14)', '>', '70')

        >>> parse_condition("sma(5) crosses_above sma(20)")
        CrossOver('sma(5)', 'crosses_above', 'sma(20)')

        >>> parse_condition("rsi(14) < 30 AND close > sma(20)")
        LogicalAnd(Comparison('rsi(14)', '<', '30'), Comparison('close', '>', 'sma(20)'))
    """
    tokens = _tokenize(dsl)
    return _Parser(tokens).parse()


def evaluate_condition(data: pl.DataFrame, dsl: str) -> dict[str, Any]:
    """Parse and evaluate a condition DSL on a DataFrame.

    Supports multi-line DSL with let bindings::

        let fast_ma = ema(close, 10)
        let slow_ma = ema(close, 30)
        fast_ma crosses_above slow_ma

    Let bindings create column aliases from existing columns in the data.

    Args:
        data: DataFrame containing indicator columns.
        dsl: Condition DSL string (may contain let bindings).

    Returns:
        Dict with keys:
        - ``signals``: list[bool] — per-bar boolean results.
        - ``signal_dates``: list — dates where signal fired (if ``trade_date``
          column exists).
        - ``hit_count``: int — number of bars where condition was true.
        - ``total_bars``: int — total number of bars.
        - ``hit_rate``: float — hit_count / total_bars.
    """
    lines = dsl.strip().split('\n')

    # Process let bindings — create column aliases
    enriched_data = data.clone()
    condition_line = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('let '):
            rest = stripped[4:]
            if '=' not in rest:
                raise SyntaxError(f"Invalid let binding: {stripped!r}")
            name, expr_str = rest.split('=', 1)
            name = name.strip()
            expr_str = expr_str.strip()

            if not name or not expr_str:
                raise SyntaxError(f"Invalid let binding: {stripped!r}")

            # Validate variable name
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
                raise SyntaxError(f"Invalid variable name: {name!r}")

            # The expression should be a column name in data
            if expr_str in enriched_data.columns:
                enriched_data = enriched_data.with_columns(
                    pl.col(expr_str).alias(name)
                )
            else:
                raise ValueError(
                    f"Column {expr_str!r} not found in data for let binding"
                )
        else:
            condition_line = stripped

    if condition_line is None:
        raise SyntaxError("No condition expression found")

    # Parse and evaluate the condition line
    condition = parse_condition(condition_line)
    signals = condition.evaluate(enriched_data)
    hit_count = int(signals.sum())
    total_bars = len(data)

    result: dict[str, Any] = {
        "signals": signals.to_list(),
        "hit_count": hit_count,
        "total_bars": total_bars,
        "hit_rate": hit_count / total_bars if total_bars > 0 else 0.0,
    }

    if "trade_date" in data.columns:
        result["signal_dates"] = (
            data.filter(signals)["trade_date"].to_list()
        )
    else:
        result["signal_dates"] = []

    return result


def signals_as_mask(data: pl.DataFrame, dsl: str) -> pl.Series:
    """Convenience: parse + evaluate, returning the boolean Series directly.

    Supports multi-line DSL with let bindings.

    Args:
        data: DataFrame containing indicator columns.
        dsl: Condition DSL string (may contain let bindings).

    Returns:
        Boolean Series — True where the condition fires.
    """
    lines = dsl.strip().split('\n')

    # Process let bindings
    enriched_data = data.clone()
    condition_line = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('let '):
            rest = stripped[4:]
            if '=' not in rest:
                raise SyntaxError(f"Invalid let binding: {stripped!r}")
            name, expr_str = rest.split('=', 1)
            name = name.strip()
            expr_str = expr_str.strip()

            if not name or not expr_str:
                raise SyntaxError(f"Invalid let binding: {stripped!r}")

            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
                raise SyntaxError(f"Invalid variable name: {name!r}")

            if expr_str in enriched_data.columns:
                enriched_data = enriched_data.with_columns(
                    pl.col(expr_str).alias(name)
                )
            else:
                raise ValueError(
                    f"Column {expr_str!r} not found in data for let binding"
                )
        else:
            condition_line = stripped

    if condition_line is None:
        raise SyntaxError("No condition expression found")

    return parse_condition(condition_line).evaluate(enriched_data)


__all__ = [
    "Condition",
    "Comparison",
    "CrossOver",
    "LogicalAnd",
    "LogicalOr",
    "LogicalNot",
    "Duration",
    "Within",
    "parse_condition",
    "evaluate_condition",
    "signals_as_mask",
]
