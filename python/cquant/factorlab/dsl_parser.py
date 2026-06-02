"""Recursive-descent parser for Factor DSL expressions."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    NUMBER = auto()
    IDENT = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    CARET = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()
    EQ = auto()
    NEQ = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    pos: int


@dataclass
class NumberNode:
    value: float

@dataclass
class ColumnNode:
    name: str

@dataclass
class BinaryOpNode:
    op: str
    left: Any
    right: Any

@dataclass
class UnaryOpNode:
    op: str
    operand: Any

@dataclass
class FunctionCallNode:
    name: str
    args: list[Any]

ASTNode = NumberNode | ColumnNode | BinaryOpNode | UnaryOpNode | FunctionCallNode


def tokenize(expression: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(expression)

    while i < n:
        ch = expression[i]

        if ch in ' \t\n\r':
            i += 1
            continue

        if ch == '+':
            tokens.append(Token(TokenType.PLUS, '+', i)); i += 1
        elif ch == '-':
            tokens.append(Token(TokenType.MINUS, '-', i)); i += 1
        elif ch == '*':
            tokens.append(Token(TokenType.STAR, '*', i)); i += 1
        elif ch == '/':
            tokens.append(Token(TokenType.SLASH, '/', i)); i += 1
        elif ch == '^':
            tokens.append(Token(TokenType.CARET, '^', i)); i += 1
        elif ch == '(':
            tokens.append(Token(TokenType.LPAREN, '(', i)); i += 1
        elif ch == ')':
            tokens.append(Token(TokenType.RPAREN, ')', i)); i += 1
        elif ch == ',':
            tokens.append(Token(TokenType.COMMA, ',', i)); i += 1
        elif ch == '>':
            if i + 1 < n and expression[i + 1] == '=':
                tokens.append(Token(TokenType.GTE, '>=', i)); i += 2
            else:
                tokens.append(Token(TokenType.GT, '>', i)); i += 1
        elif ch == '<':
            if i + 1 < n and expression[i + 1] == '=':
                tokens.append(Token(TokenType.LTE, '<=', i)); i += 2
            else:
                tokens.append(Token(TokenType.LT, '<', i)); i += 1
        elif ch == '=':
            if i + 1 < n and expression[i + 1] == '=':
                tokens.append(Token(TokenType.EQ, '==', i)); i += 2
            else:
                raise SyntaxError(f"Unexpected '=' at position {i}. Did you mean '=='?")
        elif ch == '!':
            if i + 1 < n and expression[i + 1] == '=':
                tokens.append(Token(TokenType.NEQ, '!=', i)); i += 2
            else:
                raise SyntaxError(f"Unexpected '!' at position {i}")
        elif ch.isdigit() or (ch == '.' and i + 1 < n and expression[i + 1].isdigit()):
            start = i
            while i < n and (expression[i].isdigit() or expression[i] == '.'):
                i += 1
            tokens.append(Token(TokenType.NUMBER, expression[start:i], start))
        elif ch.isalpha() or ch == '_':
            start = i
            while i < n and (expression[i].isalnum() or expression[i] == '_'):
                i += 1
            tokens.append(Token(TokenType.IDENT, expression[start:i], start))
        else:
            raise SyntaxError(f"Unexpected character '{ch}' at position {i}")

    tokens.append(Token(TokenType.EOF, '', i))
    return tokens


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, ttype: TokenType) -> Token:
        tok = self.advance()
        if tok.type != ttype:
            raise SyntaxError(
                f"Expected {ttype.name} but got {tok.type.name} '{tok.value}' at position {tok.pos}"
            )
        return tok

    def parse(self) -> ASTNode:
        node = self.parse_comparison()
        if self.peek().type != TokenType.EOF:
            tok = self.peek()
            raise SyntaxError(f"Unexpected token '{tok.value}' at position {tok.pos}")
        return node

    def parse_comparison(self) -> ASTNode:
        left = self.parse_arithmetic()
        tok = self.peek()
        if tok.type in (TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE, TokenType.EQ, TokenType.NEQ):
            op = self.advance().value
            right = self.parse_arithmetic()
            return BinaryOpNode(op, left, right)
        return left

    def parse_arithmetic(self) -> ASTNode:
        node = self.parse_term()
        while self.peek().type in (TokenType.PLUS, TokenType.MINUS):
            op = self.advance().value
            right = self.parse_term()
            node = BinaryOpNode(op, node, right)
        return node

    def parse_term(self) -> ASTNode:
        node = self.parse_factor()
        while self.peek().type in (TokenType.STAR, TokenType.SLASH):
            op = self.advance().value
            right = self.parse_factor()
            node = BinaryOpNode(op, node, right)
        return node

    def parse_factor(self) -> ASTNode:
        node = self.parse_unary()
        if self.peek().type == TokenType.CARET:
            self.advance()
            right = self.parse_unary()
            return BinaryOpNode('^', node, right)
        return node

    def parse_unary(self) -> ASTNode:
        if self.peek().type == TokenType.MINUS:
            self.advance()
            operand = self.parse_unary()
            return UnaryOpNode('-', operand)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        tok = self.peek()

        if tok.type == TokenType.NUMBER:
            self.advance()
            return NumberNode(float(tok.value))

        if tok.type == TokenType.IDENT:
            self.advance()
            if self.peek().type == TokenType.LPAREN:
                self.advance()
                args = self.parse_args()
                self.expect(TokenType.RPAREN)
                return FunctionCallNode(tok.value, args)
            return ColumnNode(tok.value)

        if tok.type == TokenType.LPAREN:
            self.advance()
            node = self.parse_comparison()
            self.expect(TokenType.RPAREN)
            return node

        raise SyntaxError(
            f"Unexpected token '{tok.value}' at position {tok.pos}"
        )

    def parse_args(self) -> list[ASTNode]:
        args: list[ASTNode] = []
        if self.peek().type == TokenType.RPAREN:
            return args
        args.append(self.parse_comparison())
        while self.peek().type == TokenType.COMMA:
            self.advance()
            args.append(self.parse_comparison())
        return args


def parse(expression: str) -> ASTNode:
    """Parse a DSL expression string into an AST."""
    tokens = tokenize(expression)
    return Parser(tokens).parse()
