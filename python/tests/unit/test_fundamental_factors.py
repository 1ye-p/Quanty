"""Tests for fundamental factors: value, quality, growth, size."""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import polars as pl
import pytest

from cquant.factorlab.factor import FactorContext
from cquant.factorlab.factors.value import PETTM, PB, DividendYield
from cquant.factorlab.factors.quality import ROE, ROA, GrossMargin
from cquant.factorlab.factors.growth import RevenueGrowth, EarningsGrowth
from cquant.factorlab.factors.size import MarketCap, LogMarketCap


@pytest.fixture
def frame() -> pl.DataFrame:
    """Minimal price frame with 5 assets, single date."""
    return pl.DataFrame(
        {
            "asset_id": ["A", "B", "C", "D", "E"],
            "trade_date": [date(2025, 6, 1)] * 5,
            "close": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )


@pytest.fixture
def frame_multi_date() -> pl.DataFrame:
    """Price frame with 5 assets across 3 dates (15 rows)."""
    assets = ["A", "B", "C", "D", "E"]
    dates = [date(2025, 6, 1), date(2025, 6, 2), date(2025, 6, 3)]
    rows = []
    for d in dates:
        for a in assets:
            rows.append({"asset_id": a, "trade_date": d, "close": 10.0})
    return pl.DataFrame(rows)


@pytest.fixture
def fundamentals() -> pl.DataFrame:
    """Fundamental data for 5 assets."""
    return pl.DataFrame(
        {
            "asset_id": ["A", "B", "C", "D", "E"],
            "pe_ttm": [15.0, 25.0, 35.0, 45.0, 55.0],
            "pb": [1.5, 2.5, 3.5, 4.5, 5.5],
            "dividend_yield": [0.03, 0.02, 0.01, 0.04, 0.05],
            "roe": [0.15, 0.20, 0.10, 0.25, 0.18],
            "roa": [0.08, 0.12, 0.05, 0.15, 0.09],
            "gross_margin": [0.40, 0.50, 0.30, 0.60, 0.45],
            "revenue_growth_yoy": [0.10, 0.20, -0.05, 0.30, 0.15],
            "earnings_growth_yoy": [0.12, 0.25, -0.10, 0.35, 0.18],
            "market_cap": [1e9, 2e9, 3e9, 4e9, 5e9],
        }
    )


@pytest.fixture
def ctx(fundamentals: pl.DataFrame) -> FactorContext:
    return FactorContext(
        as_of_date=date(2025, 6, 1),
        extra={"fundamentals": fundamentals},
    )


@pytest.fixture
def ctx_no_fund() -> FactorContext:
    return FactorContext(as_of_date=date(2025, 6, 1))


# ── Value factors ──────────────────────────────────────────────


def test_pe_ttm(frame: pl.DataFrame, ctx: FactorContext) -> None:
    factor = PETTM()
    result = factor.compute(frame, ctx)
    assert result.name == "pe_ttm"
    assert len(result) == 5
    assert result.to_list() == [15.0, 25.0, 35.0, 45.0, 55.0]


def test_pe_ttm_no_fundamentals(frame: pl.DataFrame, ctx_no_fund: FactorContext) -> None:
    result = PETTM().compute(frame, ctx_no_fund)
    assert result.name == "pe_ttm"
    assert len(result) == 5
    assert all(v is None for v in result.to_list())


def test_pe_ttm_multi_date(
    frame_multi_date: pl.DataFrame, ctx: FactorContext
) -> None:
    result = PETTM().compute(frame_multi_date, ctx)
    assert len(result) == 15  # 5 assets * 3 dates
    # Each asset's value should repeat across dates
    values = result.to_list()
    for i in range(3):
        chunk = values[i * 5 : (i + 1) * 5]
        assert chunk == [15.0, 25.0, 35.0, 45.0, 55.0]


def test_pb(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = PB().compute(frame, ctx)
    assert result.name == "pb"
    assert len(result) == 5
    assert result.to_list() == [1.5, 2.5, 3.5, 4.5, 5.5]


def test_dividend_yield(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = DividendYield().compute(frame, ctx)
    assert result.name == "dividend_yield"
    assert len(result) == 5
    assert result.to_list() == [0.03, 0.02, 0.01, 0.04, 0.05]


# ── Quality factors ────────────────────────────────────────────


def test_roe(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = ROE().compute(frame, ctx)
    assert result.name == "roe"
    assert len(result) == 5
    assert result.to_list() == [0.15, 0.20, 0.10, 0.25, 0.18]


def test_roa(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = ROA().compute(frame, ctx)
    assert result.name == "roa"
    assert len(result) == 5
    assert result.to_list() == [0.08, 0.12, 0.05, 0.15, 0.09]


def test_gross_margin(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = GrossMargin().compute(frame, ctx)
    assert result.name == "gross_margin"
    assert len(result) == 5
    assert result.to_list() == [0.40, 0.50, 0.30, 0.60, 0.45]


# ── Growth factors ─────────────────────────────────────────────


def test_revenue_growth(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = RevenueGrowth().compute(frame, ctx)
    assert result.name == "revenue_growth_yoy"
    assert len(result) == 5
    assert result.to_list() == [0.10, 0.20, -0.05, 0.30, 0.15]


def test_earnings_growth(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = EarningsGrowth().compute(frame, ctx)
    assert result.name == "earnings_growth_yoy"
    assert len(result) == 5
    assert result.to_list() == [0.12, 0.25, -0.10, 0.35, 0.18]


# ── Size factors ───────────────────────────────────────────────


def test_market_cap(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = MarketCap().compute(frame, ctx)
    assert result.name == "market_cap"
    assert len(result) == 5
    assert result.to_list() == [1e9, 2e9, 3e9, 4e9, 5e9]


def test_log_market_cap(frame: pl.DataFrame, ctx: FactorContext) -> None:
    result = LogMarketCap().compute(frame, ctx)
    assert result.name == "ln_market_cap"
    assert len(result) == 5
    expected = [math.log(v) for v in [1e9, 2e9, 3e9, 4e9, 5e9]]
    for actual, exp in zip(result.to_list(), expected):
        assert abs(actual - exp) < 1e-10


def test_log_market_cap_no_fundamentals(
    frame: pl.DataFrame, ctx_no_fund: FactorContext
) -> None:
    result = LogMarketCap().compute(frame, ctx_no_fund)
    assert result.name == "ln_market_cap"
    assert len(result) == 5
    assert all(v is None for v in result.to_list())


# ── Multi-date correctness (regression for join cardinality bug) ──


def test_all_factors_multi_date_length(
    frame_multi_date: pl.DataFrame, ctx: FactorContext
) -> None:
    """All fundamental factors must return len(frame) on multi-date frames."""
    factors = [
        PETTM(), PB(), DividendYield(),
        ROE(), ROA(), GrossMargin(),
        RevenueGrowth(), EarningsGrowth(),
        MarketCap(), LogMarketCap(),
    ]
    for f in factors:
        result = f.compute(frame_multi_date, ctx)
        assert len(result) == 15, f"{f.name} returned {len(result)} rows, expected 15"
