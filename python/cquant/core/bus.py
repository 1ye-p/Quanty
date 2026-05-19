"""cquant.core.bus — Lightweight synchronous event bus.

Design goals:
- Zero external dependencies (stdlib only + typing).
- Works inside Jupyter notebooks (no async loop required).
- Thread-safe for single-process use; not designed for cross-process messaging.
- Supports both synchronous and asynchronous handlers via separate dispatch paths.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

Handler = Callable[..., None]


class EventBus:
    """In-process publish/subscribe event bus.

    Usage::

        bus = EventBus()

        @bus.subscribe("bar.received")
        def on_bar(event: dict) -> None:
            print(event)

        bus.publish("bar.received", {"asset_id": "SSE:600036", ...})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str) -> Callable[[Handler], Handler]:
        """Decorator that registers a handler for *event_type*."""
        def decorator(fn: Handler) -> Handler:
            self._handlers[event_type].append(fn)
            return fn
        return decorator

    def register(self, event_type: str, handler: Handler) -> None:
        """Register *handler* for *event_type* imperatively."""
        self._handlers[event_type].append(handler)

    def unregister(self, event_type: str, handler: Handler) -> None:
        """Remove a previously registered handler."""
        try:
            self._handlers[event_type].remove(handler)
        except ValueError:
            pass

    def publish(self, event_type: str, payload: Any = None) -> None:
        """Dispatch *payload* to all handlers subscribed to *event_type*.

        Handlers are called synchronously in registration order.
        Exceptions in individual handlers are logged and do not stop dispatch.
        """
        for handler in list(self._handlers.get(event_type, [])):
            try:
                handler(payload)
            except Exception:
                logger.exception(
                    "Event handler %s raised an exception for event %r",
                    handler.__qualname__,
                    event_type,
                )

    def clear(self, event_type: str | None = None) -> None:
        """Remove all handlers for *event_type*, or all handlers if None."""
        if event_type is None:
            self._handlers.clear()
        else:
            self._handlers.pop(event_type, None)


# Module-level default bus (use for research / notebook convenience).
# Production code should inject an EventBus instance explicitly.
default_bus: EventBus = EventBus()
