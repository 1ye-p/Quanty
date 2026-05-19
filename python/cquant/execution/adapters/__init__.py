"""cquant.execution.adapters — Broker adapter implementations.

Provides:
- AdapterRegistry: discover and create broker adapters
- QMTAdapter: QMT (迅投) broker adapter skeleton
"""

from __future__ import annotations

import logging
from typing import Any

from cquant.execution.adapter import BrokerAdapter

logger = logging.getLogger(__name__)

# Registry of available adapters
_ADAPTERS: dict[str, type[BrokerAdapter]] = {}


def register_adapter(name: str, cls: type[BrokerAdapter]) -> None:
    """Register a broker adapter class."""
    _ADAPTERS[name] = cls


def create_adapter(name: str, **config: Any) -> BrokerAdapter:
    """Create a broker adapter by name.

    Args:
        name: Adapter name (e.g. 'qmt', 'paper')
        **config: Adapter-specific configuration

    Returns:
        BrokerAdapter instance

    Raises:
        ValueError: If adapter not found
    """
    # Lazy-load built-in adapters
    _load_builtin_adapters()

    cls = _ADAPTERS.get(name)
    if cls is None:
        available = ", ".join(sorted(_ADAPTERS.keys()))
        raise ValueError(f"Unknown broker adapter: '{name}'. Available: {available}")

    return cls(**config)


def list_adapters() -> list[str]:
    """List available adapter names."""
    _load_builtin_adapters()
    return sorted(_ADAPTERS.keys())


def _load_builtin_adapters() -> None:
    """Lazy-load built-in adapter implementations."""
    if _ADAPTERS:
        return

    # PaperBroker is not a BrokerAdapter, handle separately
    # QMT
    try:
        from cquant.execution.adapters.qmt_adapter import QMTAdapter
        register_adapter("qmt", QMTAdapter)
    except ImportError:
        logger.debug("QMT adapter not available (xtquant not installed)")
