"""cquant.registry.manifest — Plugin manifest model and loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class PluginManifest(BaseModel):
    """Declares a plugin's identity, capabilities, and compatibility."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    capabilities: list[str]          # e.g. ['data_connector', 'factor']
    entrypoints: dict[str, str]      # capability → 'module.path:function'
    markets: list[str] = []          # e.g. ['CN', 'US']
    asset_classes: list[str] = []
    compatibility: dict[str, str] = {}  # e.g. {'cquant': '>=0.1.0 <0.2.0'}
    description: str = ""
    author: str = ""
    tags: list[str] = []

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        """Load a plugin manifest from a JSON file."""
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        return cls(**data)
