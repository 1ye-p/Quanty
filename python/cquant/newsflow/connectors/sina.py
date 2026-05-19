"""cquant.newsflow.connectors.sina — Polling connector for Sina Finance news."""

from __future__ import annotations

import logging
from typing import Any

from cquant.core.errors import IngestError
from cquant.newsflow.connectors.base import (
    NewsConnector, NewsSpec, RawNewsEnvelope,
    matches_spec, parse_vendor_datetime, utc_now,
)

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://feed.mix.sina.com.cn/api/roll/get"


class SinaFinanceConnector(NewsConnector):
    """Polling connector for Sina Finance roll/news endpoints."""

    source_name = "sina"

    def __init__(
        self,
        endpoint: str = _DEFAULT_ENDPOINT,
        pageid: str = "155",
        lid: str = "1686",
        timeout: float = 10.0,
        client: Any | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._pageid = pageid
        self._lid = lid
        self._timeout = timeout
        self._client = client

    async def backfill(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        page_size = min(max(spec.max_items, 1), 50)
        pages = max(1, (max(spec.max_items, 1) + page_size - 1) // page_size)
        return await self._fetch(spec, page_size=page_size, page_count=pages)

    async def poll(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        return await self._fetch(spec, page_size=min(max(spec.max_items, 1), 50), page_count=1)

    async def _fetch(self, spec: NewsSpec, *, page_size: int, page_count: int) -> list[RawNewsEnvelope]:
        if spec.max_items <= 0:
            return []
        own = self._client is None
        client = self._client or self._build_client()
        results: list[RawNewsEnvelope] = []
        try:
            for page in range(1, page_count + 1):
                resp = await client.get(
                    self._endpoint,
                    params={"pageid": self._pageid, "lid": self._lid,
                            "k": " ".join(spec.keywords), "num": page_size, "page": page},
                )
                resp.raise_for_status()
                items = resp.json().get("result", {}).get("data", [])
                if not isinstance(items, list):
                    raise IngestError("Sina response did not contain result.data list")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    normalized = dict(item)
                    normalized.setdefault("headline", _first_str(item, "title", "intro", "keywords"))
                    normalized.setdefault("body", _first_str(item, "summary", "intro", "description"))
                    normalized.setdefault("url", _first_str(item, "url", "wapurl", "mobile_url"))
                    env = RawNewsEnvelope(
                        source=self.source_name,
                        vendor_id=str(
                            item.get("oid") or item.get("docid") or item.get("id")
                            or normalized.get("url") or normalized.get("headline")
                        ),
                        raw_payload=normalized,
                        received_at=utc_now(),
                        published_at=parse_vendor_datetime(
                            item.get("ctime") or item.get("intime") or item.get("pub_time")
                        ),
                    )
                    if matches_spec(env, spec):
                        results.append(env)
                    if len(results) >= spec.max_items:
                        return results[: spec.max_items]
                if len(items) < page_size:
                    break
            return results[: spec.max_items]
        except IngestError:
            raise
        except Exception as exc:
            logger.error("Sina Finance fetch failed: %s", exc)
            raise IngestError(f"Sina Finance fetch failed: {exc}") from exc
        finally:
            if own:
                await client.aclose()

    def _build_client(self) -> Any:
        import httpx
        return httpx.AsyncClient(timeout=self._timeout, headers={"User-Agent": "cQuant/0.1 newsflow"})


def _first_str(payload: dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""
