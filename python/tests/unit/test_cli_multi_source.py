"""Tests for CLI multi-source ingest routing."""
from __future__ import annotations

import pytest


class TestIngestSourceChoices:
    def test_tdx_source_accepted(self) -> None:
        from cquant.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "ingest", "--source", "tdx",
            "--start", "2025-01-01", "--end", "2025-12-31",
        ])
        assert args.source == "tdx"

    def test_akshare_source_accepted(self) -> None:
        from cquant.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "ingest", "--source", "akshare",
            "--start", "2025-01-01", "--end", "2025-12-31",
            "--symbols", "SSE:600036",
        ])
        assert args.source == "akshare"

    def test_tushare_source_accepted(self) -> None:
        from cquant.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "ingest", "--source", "tushare",
            "--start", "2025-01-01", "--end", "2025-12-31",
            "--symbols", "600036.SH",
        ])
        assert args.source == "tushare"

    def test_yfinance_source_accepted(self) -> None:
        from cquant.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "ingest", "--source", "yfinance",
            "--start", "2025-01-01", "--end", "2025-12-31",
            "--symbols", "AAPL",
        ])
        assert args.source == "yfinance"

    def test_unknown_source_rejected(self) -> None:
        from cquant.cli.main import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "ingest", "--source", "bloomberg",
                "--start", "2025-01-01", "--end", "2025-12-31",
            ])

    def test_symbols_argument_parsed_correctly(self) -> None:
        from cquant.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "ingest", "--source", "akshare",
            "--start", "2025-01-01", "--end", "2025-12-31",
            "--symbols", "SSE:600036,SSE:000001",
        ])
        assert args.symbols == "SSE:600036,SSE:000001"
