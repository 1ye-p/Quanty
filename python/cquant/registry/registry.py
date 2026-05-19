"""cquant.registry.registry — Plugin discovery and capability resolution."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Callable

from cquant.core.errors import PluginError
from cquant.registry.manifest import PluginManifest

logger = logging.getLogger(__name__)

# All supported capability type names (stable contract)
CAPABILITY_TYPES = frozenset(
    [
        "data_connector", "factor", "strategy", "model_trainer",
        "metric", "broker_adapter", "sentiment_agent",
        "risk_policy", "position_sizer", "risk_metric",
        "news_connector", "event_detector", "post_backtest_analyzer",
        "llm_provider", "advisor_tool",
        "knowledge_loader", "knowledge_processor",
        "embedding_provider", "knowledge_search_strategy",
        "market_calendar_provider",
    ]
)


class Registry:
    """In-process plugin registry.

    Discovers plugins from manifest JSON files in configured paths,
    loads their entrypoints, and resolves capabilities on demand.

    Usage::

        registry = Registry()
        registry.discover(["plugins/builtin"])
        connector_factory = registry.resolve("data_connector", "akshare")
        connector = connector_factory()
    """

    def __init__(self) -> None:
        self._manifests: dict[str, PluginManifest] = {}      # name → manifest
        self._entrypoint_cache: dict[tuple[str, str], Callable] = {}

    def discover(self, paths: list[str | Path]) -> list[PluginManifest]:
        """Scan *paths* for plugin.json manifest files and register them."""
        found: list[PluginManifest] = []
        for path in paths:
            p = Path(path)
            if not p.exists():
                logger.debug("Plugin path does not exist, skipping: %s", p)
                continue
            for manifest_file in p.rglob("plugin.json"):
                try:
                    manifest = PluginManifest.from_file(manifest_file)
                    self._validate_capabilities(manifest)
                    self._manifests[manifest.name] = manifest
                    found.append(manifest)
                    logger.debug("Registered plugin: %s v%s", manifest.name, manifest.version)
                except Exception as exc:
                    logger.error("Failed to load plugin manifest %s: %s", manifest_file, exc)
        return found

    def register(self, manifest: PluginManifest) -> None:
        """Register a manifest directly (for testing or programmatic use)."""
        self._validate_capabilities(manifest)
        self._manifests[manifest.name] = manifest

    def resolve(self, capability: str, plugin_name: str) -> Callable[..., Any]:
        """Return the callable entrypoint for *capability* from *plugin_name*."""
        cache_key = (capability, plugin_name)
        if cache_key in self._entrypoint_cache:
            return self._entrypoint_cache[cache_key]

        manifest = self._manifests.get(plugin_name)
        if manifest is None:
            raise PluginError(f"Plugin '{plugin_name}' not registered")
        if capability not in manifest.capabilities:
            raise PluginError(
                f"Plugin '{plugin_name}' does not declare capability '{capability}'"
            )
        entrypoint_str = manifest.entrypoints.get(capability)
        if not entrypoint_str:
            raise PluginError(
                f"Plugin '{plugin_name}' missing entrypoint for capability '{capability}'"
            )

        fn = self._load_entrypoint(entrypoint_str)
        self._entrypoint_cache[cache_key] = fn
        return fn

    def list_by_capability(self, capability: str) -> list[PluginManifest]:
        """Return all registered plugins that declare *capability*."""
        return [m for m in self._manifests.values() if capability in m.capabilities]

    def all_manifests(self) -> list[PluginManifest]:
        return list(self._manifests.values())

    @staticmethod
    def _load_entrypoint(entrypoint: str) -> Callable:
        """Import and return the callable from 'module.path:function_name'."""
        if ":" not in entrypoint:
            raise PluginError(f"Invalid entrypoint format: '{entrypoint}'. Expected 'module:attr'")
        module_path, attr = entrypoint.rsplit(":", 1)
        try:
            module = importlib.import_module(module_path)
            return getattr(module, attr)
        except (ImportError, AttributeError) as exc:
            raise PluginError(f"Failed to load entrypoint '{entrypoint}': {exc}") from exc

    @staticmethod
    def _validate_capabilities(manifest: PluginManifest) -> None:
        unknown = set(manifest.capabilities) - CAPABILITY_TYPES
        if unknown:
            raise PluginError(
                f"Plugin '{manifest.name}' declares unknown capability types: {unknown}. "
                f"Valid types: {sorted(CAPABILITY_TYPES)}"
            )
