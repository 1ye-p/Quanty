"""Unit tests for CLI module.

Tests exchange detection logic and subcommand availability.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from cquant.cli.main import _detect_exchange


class TestExchangeDetection:
    """Tests for exchange detection logic."""

    def test_shanghai_main_board(self):
        assert _detect_exchange("600036") == "SSE"

    def test_shanghai_etf(self):
        assert _detect_exchange("510300") == "SSE"

    def test_shenzhen_main_board(self):
        assert _detect_exchange("000001") == "SZSE"

    def test_shenzhen_gem(self):
        assert _detect_exchange("300750") == "SZSE"

    def test_shenzhen_etf(self):
        assert _detect_exchange("159915") == "SZSE"

    def test_beijing_exchange(self):
        assert _detect_exchange("830799") == "BSE"

    def test_star_market(self):
        """科创板 (688xxx) should be SSE."""
        assert _detect_exchange("688001") == "SSE"

    def test_unknown_prefix(self):
        assert _detect_exchange("999999") == "UNKNOWN"


class TestCLISubcommands:
    """Tests for CLI subcommands."""

    def test_help_command(self):
        result = subprocess.run(
            [sys.executable, "-m", "cquant.cli.main", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "cquant" in result.stdout.lower()
