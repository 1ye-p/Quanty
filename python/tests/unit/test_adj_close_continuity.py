"""测试 adj_close 跳空连续性检测（警告日志）。"""
from __future__ import annotations

import logging
from datetime import date, datetime

import polars as pl
import pytest

from cquant.datahub.connectors.base import RawBatch
from cquant.datahub.pipelines.silver import SilverNormalizer


def _make_batch(rows: list[dict]) -> RawBatch:
    return RawBatch(
        source="csv_parquet",
        dataset="daily_bar",
        data=pl.DataFrame(rows),
        fetched_at=datetime.utcnow().isoformat() + "Z",
    )


class TestAdjCloseContiguityCheck:
    def test_normal_data_no_warning(self, caplog) -> None:
        normalizer = SilverNormalizer()
        batch = _make_batch([
            {
                "asset_id": "SSE:600036", "trade_date": date(2025, 1, 2),
                "open": 10.0, "high": 10.5, "low": 9.8,
                "close": 10.2, "volume": 1e6, "amount": 1e7,
                "adj_factor": 1.0, "is_suspended": False, "source": "test",
            },
            {
                "asset_id": "SSE:600036", "trade_date": date(2025, 1, 3),
                "open": 10.1, "high": 10.6, "low": 9.9,
                "close": 10.3, "volume": 1e6, "amount": 1e7,
                "adj_factor": 1.0, "is_suspended": False, "source": "test",
            },
        ])
        with caplog.at_level(logging.WARNING):
            normalizer.normalize(batch)
        adj_warnings = [r for r in caplog.records if "adj_close" in r.message.lower() and "跳空" in r.message]
        assert len(adj_warnings) == 0

    def test_suspicious_adj_factor_jump_triggers_warning(self, caplog) -> None:
        """adj_factor 突变应触发警告。"""
        normalizer = SilverNormalizer()
        # close 几乎不变，但 adj_factor 从 1.0 变为 0.5
        # → adj_close 从 10.2*1=10.2 变为 10.1*0.5=5.05，跌幅 ~50%
        batch = _make_batch([
            {
                "asset_id": "SSE:600036", "trade_date": date(2025, 1, 2),
                "open": 10.0, "high": 10.5, "low": 9.8,
                "close": 10.2, "volume": 1e6, "amount": 1e7,
                "adj_factor": 1.0, "is_suspended": False, "source": "test",
            },
            {
                "asset_id": "SSE:600036", "trade_date": date(2025, 1, 3),
                "open": 10.0, "high": 10.2, "low": 10.0,
                "close": 10.1, "volume": 1e6, "amount": 1e7,
                "adj_factor": 0.5,  # adj_factor 减半（模拟配股/送股）
                "is_suspended": False, "source": "test",
            },
        ])
        with caplog.at_level(logging.WARNING):
            normalizer.normalize(batch)
        adj_warnings = [r for r in caplog.records if "跳空" in r.message]
        assert len(adj_warnings) >= 1
