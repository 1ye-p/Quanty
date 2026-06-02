"""YAML market config loader."""

from __future__ import annotations

from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "markets"

_cache: dict[str, dict] = {}


def load_market_config(market: str) -> dict:
    """Load market config from configs/markets/{market}.yml."""
    market = market.upper()
    if market in _cache:
        return _cache[market]
    path = _CONFIG_DIR / f"{market.lower()}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Market config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    _cache[market] = config
    return config


def clear_config_cache() -> None:
    """Clear the config cache (for testing)."""
    _cache.clear()
