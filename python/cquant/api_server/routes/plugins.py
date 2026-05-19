"""Plugin registry routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("")
async def list_plugins() -> dict:
    """List all registered plugins and their capabilities."""
    from cquant.registry import Registry
    registry = Registry()
    registry.discover(["plugins/builtin", "configs/plugins"])
    return {
        "items": [
            {
                "name": m.name,
                "version": m.version,
                "capabilities": m.capabilities,
                "markets": m.markets,
                "description": m.description,
            }
            for m in registry.all_manifests()
        ]
    }
