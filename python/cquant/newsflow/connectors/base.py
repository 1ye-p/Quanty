"""cquant.newsflow.connectors.base — News connector contracts and shared helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

_TEXT_KEYS = (
    "headline", "title", "notice_title", "art_title", "name",
    "body", "content", "summary", "digest", "description", "brief", "url",
)


@dataclass
class NewsSpec:
    """Specification for a news fetch request."""

    source: str
    keywords: list[str] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    max_items: int = 100


@dataclass
class RawNewsEnvelope:
    """Raw vendor-native news payload, before normalization."""

    source: str
    vendor_id: str
    raw_payload: dict[str, Any]
    received_at: datetime           # When cQuant received the item (UTC)
    published_at: datetime | None   # Vendor's claimed publish time (may be None)


class NewsConnector(ABC):
    """Abstract base for polling-based news connectors."""

    source_name: str = ""

    @abstractmethod
    async def backfill(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        """Fetch a bounded historical slice according to *spec*."""

    @abstractmethod
    async def poll(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        """Fetch only the newest items currently visible from the source."""

    def can_handle(self, spec: NewsSpec) -> bool:
        return spec.source == self.source_name


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(tz=timezone.utc)


def ensure_utc(ts: datetime | None) -> datetime | None:
    """Coerce a naive or offset-aware timestamp to UTC."""
    if ts is None:
        return None
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)


def parse_vendor_datetime(value: Any) -> datetime | None:
    """Parse common vendor timestamp formats into UTC-aware datetimes."""
    if isinstance(value, datetime):
        return ensure_utc(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d%H%M%S"):
        try:
            return ensure_utc(datetime.strptime(raw, fmt))
        except ValueError:
            continue
    try:
        return ensure_utc(parsedate_to_datetime(raw))
    except (TypeError, ValueError):
        return None


def payload_text(payload: dict[str, Any]) -> str:
    """Return best-effort searchable text from a raw payload."""
    parts = [payload[k].strip() for k in _TEXT_KEYS if isinstance(payload.get(k), str) and payload[k].strip()]
    if not parts:
        parts = [v.strip() for v in payload.values() if isinstance(v, str) and v.strip()]
    return " ".join(parts)


def matches_spec(envelope: RawNewsEnvelope, spec: NewsSpec) -> bool:
    """Return True if *envelope* satisfies the date / keyword / asset filters in *spec*."""
    if envelope.published_at is not None:
        d = envelope.published_at.date()
        if spec.start_date and d < spec.start_date:
            return False
        if spec.end_date and d > spec.end_date:
            return False
    searchable = payload_text(envelope.raw_payload).casefold()
    if spec.keywords:
        kws = [k.casefold() for k in spec.keywords if k.strip()]
        if kws and not any(k in searchable for k in kws):
            return False
    if spec.asset_ids:
        tokens = {aid.casefold() for aid in spec.asset_ids if aid.strip()}
        tokens |= {aid.split(":", 1)[-1].casefold() for aid in spec.asset_ids if ":" in aid}
        if tokens and not any(t in searchable for t in tokens):
            return False
    return True
