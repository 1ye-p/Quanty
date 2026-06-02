"""Market rules registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cquant.market_calendar.rules.base import TradingRules

_registry: dict[str, type[TradingRules]] = {}


def register_rules(market: str):
    """Decorator to register a TradingRules class for a market."""
    def decorator(cls: type[TradingRules]) -> type[TradingRules]:
        _registry[market.upper()] = cls
        return cls
    return decorator


def get_market_rules(market: str, config: dict) -> TradingRules:
    """Get a TradingRules instance for the given market."""
    market = market.upper()
    cls = _registry.get(market)
    if not cls:
        raise ValueError(f"No rules registered for market: {market}")
    return cls(config=config)


def list_registered_markets() -> list[str]:
    """List all registered market codes."""
    return list(_registry.keys())
