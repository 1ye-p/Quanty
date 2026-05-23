"""测试 Alpha158 KBAR 因子（9个）。"""
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cquant.factorlab.factor import FactorContext
from cquant.factorlab.factors.kbar import KMID, KLEN, KMID2, KUP, KUP2, KLOW, KLOW2, KSFT, KSFT2


def _make_frame() -> pl.DataFrame:
    return pl.DataFrame({
        "asset_id": ["A"],
        "trade_date": [date(2025, 1, 1)],
        "open": [10.0],
        "high": [12.0],
        "low": [9.0],
        "close": [11.0],
        "volume": [1e6],
    })


def _ctx() -> FactorContext:
    return FactorContext(as_of_date=date(2025, 1, 1))


class TestAlpha158KBARFactors:
    def test_kmid_value(self) -> None:
        """KMID = (11 - 10) / 10 = 0.1"""
        result = KMID().compute(_make_frame(), _ctx())
        assert result[0] == pytest.approx(0.1, abs=1e-6)

    def test_klen_value(self) -> None:
        """KLEN = (12 - 9) / 10 = 0.3"""
        result = KLEN().compute(_make_frame(), _ctx())
        assert result[0] == pytest.approx(0.3, abs=1e-6)

    def test_kmid2_value(self) -> None:
        """KMID2 = (11 - 10) / (12 - 9) = 1/3"""
        result = KMID2().compute(_make_frame(), _ctx())
        assert result[0] == pytest.approx(1.0 / 3, abs=1e-4)

    def test_kup_value(self) -> None:
        """KUP = (12 - max(10,11)) / 10 = (12-11)/10 = 0.1"""
        result = KUP().compute(_make_frame(), _ctx())
        assert result[0] == pytest.approx(0.1, abs=1e-6)

    def test_klow_value(self) -> None:
        """KLOW = (min(10,11) - 9) / 10 = 1/10 = 0.1"""
        result = KLOW().compute(_make_frame(), _ctx())
        assert result[0] == pytest.approx(0.1, abs=1e-6)

    def test_ksft_value(self) -> None:
        """KSFT = (2*11 - 12 - 9) / 10 = 1/10 = 0.1"""
        result = KSFT().compute(_make_frame(), _ctx())
        assert result[0] == pytest.approx(0.1, abs=1e-6)

    def test_all_kbar_factors_have_correct_names(self) -> None:
        factors = [KMID(), KLEN(), KMID2(), KUP(), KUP2(), KLOW(), KLOW2(), KSFT(), KSFT2()]
        expected = ["KMID", "KLEN", "KMID2", "KUP", "KUP2", "KLOW", "KLOW2", "KSFT", "KSFT2"]
        for factor, name in zip(factors, expected):
            assert factor.name == name

    def test_all_kbar_factors_have_alpha158_tag(self) -> None:
        for factor in [KMID(), KLEN(), KMID2()]:
            assert "alpha158" in factor.tags
