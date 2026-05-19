"""Unit tests for cquant.registry."""

import pytest

from cquant.core.errors import PluginError
from cquant.registry.manifest import PluginManifest
from cquant.registry.registry import Registry


def _make_manifest(**overrides) -> PluginManifest:
    defaults = {
        "name": "test-plugin",
        "version": "0.1.0",
        "capabilities": ["data_connector"],
        "entrypoints": {"data_connector": "cquant.datahub.connectors.base:DataConnector"},
    }
    defaults.update(overrides)
    return PluginManifest(**defaults)


def test_register_and_list() -> None:
    registry = Registry()
    manifest = _make_manifest()
    registry.register(manifest)
    assert "test-plugin" in [m.name for m in registry.all_manifests()]


def test_list_by_capability() -> None:
    registry = Registry()
    registry.register(_make_manifest(name="a", capabilities=["data_connector"]))
    registry.register(_make_manifest(name="b", capabilities=["factor"]))

    data_connectors = registry.list_by_capability("data_connector")
    assert len(data_connectors) == 1
    assert data_connectors[0].name == "a"


def test_unknown_capability_raises() -> None:
    with pytest.raises(PluginError, match="unknown capability"):
        Registry()._validate_capabilities(
            PluginManifest(
                name="bad",
                version="0.1.0",
                capabilities=["not_a_real_capability"],
                entrypoints={},
            )
        )


def test_resolve_unknown_plugin_raises() -> None:
    registry = Registry()
    with pytest.raises(PluginError, match="not registered"):
        registry.resolve("data_connector", "nonexistent-plugin")
