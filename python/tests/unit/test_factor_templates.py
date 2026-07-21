"""Tests for factor_templates — preset portfolio factor configurations."""

from __future__ import annotations

import pytest

from cquant.factorlab.factor_templates import (
    FactorTemplate,
    PRESET_TEMPLATES,
    get_template,
    list_templates,
)


class TestListTemplates:
    """list_templates() behaviour."""

    def test_returns_all_4_presets(self):
        """Should return exactly 4 preset templates."""
        templates = list_templates()
        assert len(templates) == 4

    def test_returns_dicts(self):
        """Each element should be a dict (serialized form)."""
        for tpl in list_templates():
            assert isinstance(tpl, dict)

    def test_expected_ids_present(self):
        """The 4 preset ids must be value, growth, momentum, low_vol."""
        ids = {t["template_id"] for t in list_templates()}
        assert ids == {"value", "growth", "momentum", "low_vol"}


class TestGetTemplate:
    """get_template() behaviour."""

    def test_returns_correct_template_by_id(self):
        """Lookup by id should return the matching template dict."""
        tpl = get_template("value")
        assert tpl is not None
        assert tpl["template_id"] == "value"
        assert tpl["name"] == "价值型"
        assert "factor_weights" in tpl
        assert "pe_ttm" in tpl["factor_weights"]

    def test_returns_none_for_invalid_id(self):
        """Unknown id should return None."""
        assert get_template("nonexistent") is None

    def test_returns_none_for_empty_string(self):
        """Empty string id should return None."""
        assert get_template("") is None

    @pytest.mark.parametrize("tid", ["value", "growth", "momentum", "low_vol"])
    def test_all_presets_retrievable(self, tid: str):
        """Every preset id should be retrievable."""
        tpl = get_template(tid)
        assert tpl is not None
        assert tpl["template_id"] == tid


class TestFactorTemplateDataclass:
    """FactorTemplate dataclass serialization."""

    def test_to_dict_roundtrip(self):
        """to_dict() should produce a dict with all expected keys."""
        tpl = PRESET_TEMPLATES[0]
        d = tpl.to_dict()
        assert isinstance(d, dict)
        for key in ("template_id", "name", "description", "factor_weights", "top_n", "tags"):
            assert key in d

    def test_to_dict_preserves_values(self):
        """to_dict() values should match the dataclass fields."""
        tpl = get_template("growth")
        assert tpl is not None
        assert tpl["top_n"] == 10
        assert isinstance(tpl["factor_weights"], dict)
        assert len(tpl["factor_weights"]) > 0
        assert isinstance(tpl["tags"], list)
        assert len(tpl["tags"]) > 0

    def test_factor_weights_are_numeric(self):
        """All factor weights should be float values."""
        for preset in PRESET_TEMPLATES:
            for factor, weight in preset.factor_weights.items():
                assert isinstance(weight, float), (
                    f"Weight for {factor} in {preset.template_id} is not float"
                )
