"""测试 Alpha158 因子集（≥50 个）。"""
from __future__ import annotations

import pytest


class TestQlibFactorSet:
    def test_factor_set_importable(self) -> None:
        from cquant.qlib_bridge.factor_set import QlibFactorSet
        assert QlibFactorSet is not None

    def test_available_factor_names_is_list(self) -> None:
        from cquant.qlib_bridge.factor_set import QlibFactorSet
        names = QlibFactorSet.available_factor_names()
        assert isinstance(names, list)

    def test_alpha158_definitions_returns_list(self) -> None:
        from cquant.qlib_bridge.factor_set import QlibFactorSet
        defs = QlibFactorSet.alpha158_definitions()
        assert isinstance(defs, list)


class TestAlpha158Factors:
    def test_alpha158_module_importable(self) -> None:
        from cquant.factorlab.factors.alpha158 import ALPHA158_FACTORS
        assert isinstance(ALPHA158_FACTORS, list)

    def test_alpha158_factors_count_ge_50(self) -> None:
        from cquant.factorlab.factors.alpha158 import ALPHA158_FACTORS
        assert len(ALPHA158_FACTORS) >= 50, f"Alpha158 因子数量 {len(ALPHA158_FACTORS)} < 50"

    def test_all_alpha158_factors_have_alpha158_tag(self) -> None:
        from cquant.factorlab.factors.alpha158 import ALPHA158_FACTORS
        for factor in ALPHA158_FACTORS:
            assert "alpha158" in factor.tags, f"{factor.name} 缺少 'alpha158' 标签"

    def test_alpha158_factors_registered_in_builtin(self) -> None:
        from cquant.factorlab.factors import BUILTIN_FACTORS
        from cquant.factorlab.factors.alpha158 import ALPHA158_FACTORS
        builtin_names = {f.name for f in BUILTIN_FACTORS}
        for factor in ALPHA158_FACTORS:
            assert factor.name in builtin_names, f"{factor.name} 未注册到 BUILTIN_FACTORS"
