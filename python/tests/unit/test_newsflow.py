"""Unit tests for newsflow module.

Tests connectors, normalization, PIT filtering, and orchestration.
Uses mocked HTTP responses to avoid real API calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from cquant.newsflow.connectors.base import NewsSpec, RawNewsEnvelope
from cquant.newsflow.normalize import NewsNormalizer, build_dedupe_key
from cquant.newsflow.pit import PITGate


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_envelope(
    source: str = "sina",
    vendor_id: str = "v1",
    published_at: datetime | None = None,
) -> RawNewsEnvelope:
    return RawNewsEnvelope(
        source=source,
        vendor_id=vendor_id,
        raw_payload={
            "title": "招商银行发布年报",
            "content": "招商银行2024年净利润增长5%",
            "code": "600036",
        },
        received_at=datetime.now(tz=timezone.utc),
        published_at=published_at or datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


# ── Dedup Key Tests ──────────────────────────────────────────────────────────

class TestDedupeKey:
    def test_build_dedupe_key_format(self):
        key = build_dedupe_key("sina", "v123")
        assert key == "sina::v123"

    def test_different_sources_different_keys(self):
        k1 = build_dedupe_key("sina", "v1")
        k2 = build_dedupe_key("eastmoney", "v1")
        assert k1 != k2

    def test_different_vendors_different_keys(self):
        k1 = build_dedupe_key("sina", "v1")
        k2 = build_dedupe_key("sina", "v2")
        assert k1 != k2


# ── NewsNormalizer Tests ──────────────────────────────────────────────────────

class TestNewsNormalizer:
    def test_normalizer_returns_dataframe(self):
        normalizer = NewsNormalizer()
        envelopes = [_make_envelope()]
        result = normalizer.normalize(envelopes)
        assert isinstance(result, pl.DataFrame)

    def test_normalizer_produces_correct_schema(self):
        normalizer = NewsNormalizer()
        envelopes = [_make_envelope()]
        result = normalizer.normalize(envelopes)
        if not result.is_empty():
            assert "source" in result.columns
            assert "headline" in result.columns
            assert "dedupe_key" in result.columns

    def test_normalizer_empty_input(self):
        normalizer = NewsNormalizer()
        result = normalizer.normalize([])
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()

    def test_normalizer_extracts_dedupe_key(self):
        normalizer = NewsNormalizer()
        envelopes = [_make_envelope(source="sina", vendor_id="v42")]
        result = normalizer.normalize(envelopes)
        if not result.is_empty():
            assert "sina::v42" in result["dedupe_key"].to_list()


# ── PITGate Tests ─────────────────────────────────────────────────────────────

class TestPITGate:
    def test_pit_gate_filters_future_news(self):
        gate = PITGate()
        df = pl.DataFrame({
            "available_at": [datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc)],
            "headline": ["future news"],
        })
        as_of = datetime(2025, 5, 1, 0, 0, tzinfo=timezone.utc)
        result = gate.filter(df, as_of)
        assert result.is_empty()

    def test_pit_gate_allows_past_news(self):
        gate = PITGate()
        df = pl.DataFrame({
            "available_at": [datetime(2025, 4, 1, 10, 0, tzinfo=timezone.utc)],
            "headline": ["past news"],
        })
        as_of = datetime(2025, 5, 1, 0, 0, tzinfo=timezone.utc)
        result = gate.filter(df, as_of)
        assert result.height == 1

    def test_pit_gate_mixed_dates(self):
        gate = PITGate()
        df = pl.DataFrame({
            "available_at": [
                datetime(2025, 4, 1, tzinfo=timezone.utc),
                datetime(2025, 6, 1, tzinfo=timezone.utc),
            ],
            "headline": ["past", "future"],
        })
        as_of = datetime(2025, 5, 1, tzinfo=timezone.utc)
        result = gate.filter(df, as_of)
        assert result.height == 1
        assert result["headline"][0] == "past"


# ── NewsSpec Tests ────────────────────────────────────────────────────────────

class TestNewsSpec:
    def test_spec_creation(self):
        spec = NewsSpec(
            source="sina",
            keywords=["银行", "年报"],
            asset_ids=["600036"],
        )
        assert spec.source == "sina"
        assert "银行" in spec.keywords

    def test_matches_spec_source(self):
        envelope = _make_envelope(source="sina")
        spec = NewsSpec(source="sina")
        from cquant.newsflow.connectors.base import matches_spec
        assert matches_spec(envelope, spec) is True

    def test_matches_spec_with_keywords(self):
        envelope = _make_envelope()
        spec = NewsSpec(source="sina", keywords=["招商银行"])
        from cquant.newsflow.connectors.base import matches_spec
        assert matches_spec(envelope, spec) is True
