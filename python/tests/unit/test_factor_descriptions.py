"""Tests for FactorDescriptionManager and factor description data."""
from __future__ import annotations

import polars as pl
import pytest

from cquant.factorlab.factor_descriptions import FactorDescriptionManager


@pytest.fixture()
def mgr() -> FactorDescriptionManager:
    """In-memory manager for each test."""
    m = FactorDescriptionManager(":memory:")
    yield m
    m.close()


# ── Basic CRUD ──────────────────────────────────────────────────────────────


class TestWriteAndRead:
    def test_write_single_row(self, mgr: FactorDescriptionManager) -> None:
        df = pl.DataFrame({
            "factor_name": ["KMID"],
            "category": ["kbar"],
            "display_name": ["K线中间位置"],
            "description": ["收盘价相对开盘价的涨跌幅"],
            "formula": ["(close - open) / open"],
            "economic_meaning": ["多空力量对比"],
            "use_case": ["日内动量信号"],
        })
        mgr.write_descriptions(df)
        assert mgr.count() == 1

        result = mgr.read_descriptions(["KMID"])
        assert result.height == 1
        assert result["factor_name"][0] == "KMID"
        assert result["category"][0] == "kbar"

    def test_write_upsert(self, mgr: FactorDescriptionManager) -> None:
        """Writing the same factor_name twice should overwrite."""
        df1 = pl.DataFrame({
            "factor_name": ["KMID"],
            "category": ["kbar"],
            "display_name": ["旧名称"],
            "description": ["旧描述"],
            "formula": ["old"],
            "economic_meaning": ["old"],
            "use_case": ["old"],
        })
        df2 = pl.DataFrame({
            "factor_name": ["KMID"],
            "category": ["kbar"],
            "display_name": ["新名称"],
            "description": ["新描述"],
            "formula": ["new"],
            "economic_meaning": ["new"],
            "use_case": ["new"],
        })
        mgr.write_descriptions(df1)
        mgr.write_descriptions(df2)
        assert mgr.count() == 1

        result = mgr.read_descriptions(["KMID"])
        assert result["display_name"][0] == "新名称"

    def test_read_multiple(self, mgr: FactorDescriptionManager) -> None:
        df = pl.DataFrame({
            "factor_name": ["A", "B", "C"],
            "category": ["x", "x", "y"],
            "display_name": ["A名", "B名", "C名"],
            "description": ["d", "d", "d"],
            "formula": ["f", "f", "f"],
            "economic_meaning": ["e", "e", "e"],
            "use_case": ["u", "u", "u"],
        })
        mgr.write_descriptions(df)
        result = mgr.read_descriptions(["A", "C"])
        assert result.height == 2
        assert set(result["factor_name"].to_list()) == {"A", "C"}

    def test_read_nonexistent(self, mgr: FactorDescriptionManager) -> None:
        result = mgr.read_descriptions(["NOPE"])
        assert result.height == 0

    def test_read_empty_list(self, mgr: FactorDescriptionManager) -> None:
        result = mgr.read_descriptions([])
        assert result.height == 0


class TestReadByCategory:
    def test_filter_by_category(self, mgr: FactorDescriptionManager) -> None:
        df = pl.DataFrame({
            "factor_name": ["KMID", "ROC5", "VMA5"],
            "category": ["kbar", "rolling_roc", "volume"],
            "display_name": ["a", "b", "c"],
            "description": ["d", "d", "d"],
            "formula": ["f", "f", "f"],
            "economic_meaning": ["e", "e", "e"],
            "use_case": ["u", "u", "u"],
        })
        mgr.write_descriptions(df)
        result = mgr.read_by_category("kbar")
        assert result.height == 1
        assert result["factor_name"][0] == "KMID"


class TestDelete:
    def test_delete_existing(self, mgr: FactorDescriptionManager) -> None:
        df = pl.DataFrame({
            "factor_name": ["A", "B"],
            "category": ["x", "x"],
            "display_name": ["A", "B"],
            "description": ["d", "d"],
            "formula": ["f", "f"],
            "economic_meaning": ["e", "e"],
            "use_case": ["u", "u"],
        })
        mgr.write_descriptions(df)
        mgr.delete_descriptions(["A"])
        assert mgr.count() == 1
        assert mgr.read_descriptions(["A"]).height == 0
        assert mgr.read_descriptions(["B"]).height == 1

    def test_delete_empty_list(self, mgr: FactorDescriptionManager) -> None:
        mgr.delete_descriptions([])  # should not raise


class TestReadAll:
    def test_read_all_ordered(self, mgr: FactorDescriptionManager) -> None:
        df = pl.DataFrame({
            "factor_name": ["B", "A"],
            "category": ["y", "x"],
            "display_name": ["B", "A"],
            "description": ["d", "d"],
            "formula": ["f", "f"],
            "economic_meaning": ["e", "e"],
            "use_case": ["u", "u"],
        })
        mgr.write_descriptions(df)
        result = mgr.read_all()
        assert result.height == 2
        # Should be ordered by category, factor_name
        assert result["factor_name"].to_list() == ["A", "B"]


# ── Context Manager ─────────────────────────────────────────────────────────


class TestContextManager:
    def test_context_manager(self) -> None:
        with FactorDescriptionManager(":memory:") as mgr:
            assert mgr.count() == 0


# ── Default Data Loading ────────────────────────────────────────────────────


class TestLoadDefaults:
    def test_load_default_descriptions(self, mgr: FactorDescriptionManager) -> None:
        count = mgr.load_default_descriptions()
        # Should have loaded a large number of factor descriptions
        assert count > 100
        assert mgr.count() == count

    def test_kbar_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["KMID", "KLEN", "KMID2", "KUP", "KUP2", "KLOW", "KLOW2"])
        assert result.height == 7
        assert result["category"].to_list() == ["kbar"] * 7

    def test_roc_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["ROC5", "ROC10", "ROC20", "ROC30", "ROC60"])
        assert result.height == 5

    def test_ma_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["MA5", "MA10", "MA20", "MA30", "MA60"])
        assert result.height == 5

    def test_std_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["STD5", "STD10", "STD20", "STD30", "STD60"])
        assert result.height == 5

    def test_regression_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["BETA5", "RSQR10", "RESI20"])
        assert result.height == 3

    def test_quantile_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["QTLU5", "QTLD10", "RANK20"])
        assert result.height == 3

    def test_extrema_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["IMAX5", "IMIN10", "IMXD20"])
        assert result.height == 3

    def test_correlation_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["CORR5", "CORD10"])
        assert result.height == 2

    def test_counting_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["CNTP5", "CNTN10", "CNTD20"])
        assert result.height == 3

    def test_rsi_like_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["SUMP5", "SUMN10", "SUMD20"])
        assert result.height == 3

    def test_volume_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_descriptions(["VMA5", "VSTD10", "WVMA20", "VSUMP30", "VSUMN60", "VSUMD5"])
        assert result.height == 6

    def test_alpha360_factors_present(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        # Alpha360 should have 60 * 6 = 360 entries
        result = mgr.read_by_category("alpha360")
        assert result.height == 360
        # Spot check a few
        spot = mgr.read_descriptions(["close_1", "open_5", "volume_60", "vwap_30"])
        assert spot.height == 4

    def test_all_descriptions_have_required_fields(self, mgr: FactorDescriptionManager) -> None:
        mgr.load_default_descriptions()
        result = mgr.read_all()
        for col in ["factor_name", "category", "display_name", "description", "formula", "economic_meaning", "use_case"]:
            assert col in result.columns, f"Missing column: {col}"
            # No nulls in factor_name or category
            if col in ("factor_name", "category"):
                assert result[col].null_count() == 0, f"Nulls found in {col}"


# ── Data Module ─────────────────────────────────────────────────────────────


class TestDataModule:
    def test_alpha158_descriptions_list(self) -> None:
        from cquant.factorlab.factor_descriptions_data import ALPHA158_DESCRIPTIONS

        assert len(ALPHA158_DESCRIPTIONS) > 100
        # Check first entry structure
        entry = ALPHA158_DESCRIPTIONS[0]
        for key in ["factor_name", "category", "display_name", "description", "formula", "economic_meaning", "use_case"]:
            assert key in entry, f"Missing key: {key}"

    def test_alpha360_descriptions_list(self) -> None:
        from cquant.factorlab.factor_descriptions_data import ALPHA360_DESCRIPTIONS

        assert len(ALPHA360_DESCRIPTIONS) == 360
        # Check first entry
        entry = ALPHA360_DESCRIPTIONS[0]
        assert entry["category"] == "alpha360"
