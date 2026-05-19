"""cquant.newsflow.connectors.rss — Generic polling connector for RSS and Atom feeds."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any, Iterable

from cquant.core.errors import IngestError
from cquant.newsflow.connectors.base import (
    NewsConnector, NewsSpec, RawNewsEnvelope,
    matches_spec, parse_vendor_datetime, utc_now,
)

logger = logging.getLogger(__name__)


class RSSConnector(NewsConnector):
    """Generic RSS/Atom feed connector (polling-based, no Kafka required)."""

    def __init__(
        self,
        feed_url: str,
        source_name: str = "rss",
        timeout: float = 10.0,
        client: Any | None = None,
    ) -> None:
        self.source_name = source_name  # Allow override per feed
        self._feed_url = feed_url
        self._timeout = timeout
        self._client = client

    async def backfill(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        return await self._fetch(spec)

    async def poll(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        return await self._fetch(spec)

    async def _fetch(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        if spec.max_items <= 0:
            return []
        own = self._client is None
        client = self._client or self._build_client()
        try:
            resp = await client.get(self._feed_url)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            results: list[RawNewsEnvelope] = []
            for item in _iter_items(root):
                headline = _child_text(item, "title")
                body = _child_text(item, "description", "summary", "content")
                url = _child_text(item, "link", "id")
                guid = _child_text(item, "guid", "id")
                pub_raw = _child_text(item, "pubDate", "published", "updated")
                env = RawNewsEnvelope(
                    source=self.source_name,
                    vendor_id=guid or url or headline,
                    raw_payload={"headline": headline, "body": body, "url": url,
                                 "guid": guid, "published": pub_raw,
                                 "category": _child_text(item, "category")},
                    received_at=utc_now(),
                    published_at=parse_vendor_datetime(pub_raw),
                )
                if matches_spec(env, spec):
                    results.append(env)
                if len(results) >= spec.max_items:
                    return results[: spec.max_items]
            return results[: spec.max_items]
        except IngestError:
            raise
        except Exception as exc:
            logger.error("RSS fetch failed for %s: %s", self._feed_url, exc)
            raise IngestError(f"RSS fetch failed for {self._feed_url}: {exc}") from exc
        finally:
            if own:
                await client.aclose()

    def _build_client(self) -> Any:
        import httpx
        return httpx.AsyncClient(timeout=self._timeout, headers={"User-Agent": "cQuant/0.1 newsflow"})


def _iter_items(root: ET.Element) -> Iterable[ET.Element]:
    for el in root.iter():
        if _local(el.tag) in {"item", "entry"}:
            yield el


def _child_text(element: ET.Element, *names: str) -> str:
    candidates = set(names)
    for child in element:
        if _local(child.tag) not in candidates:
            continue
        text = (child.text or "").strip()
        if text:
            return text
        href = child.attrib.get("href", "").strip()
        if href:
            return href
    return ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
