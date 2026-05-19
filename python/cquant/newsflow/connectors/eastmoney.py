"""cquant.newsflow.connectors.eastmoney — Polling connector for Eastmoney announcements."""

from __future__ import annotations

import logging
from typing import Any

from cquant.core.errors import IngestError
from cquant.newsflow.connectors.base import (
    NewsConnector, NewsSpec, RawNewsEnvelope,
    matches_spec, parse_vendor_datetime, utc_now,
)

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://np-anotice-stock.eastmoney.com/api/security/ann"


class EastmoneyConnector(NewsConnector):
    """Polling connector for Eastmoney exchange announcements."""

    source_name = "eastmoney"

    def __init__(
        self,
        endpoint: str = _DEFAULT_ENDPOINT,
        timeout: float = 10.0,
        client: Any | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._client = client

    async def backfill(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        page_size = min(max(spec.max_items, 1), 100)
        pages = max(1, (max(spec.max_items, 1) + page_size - 1) // page_size)
        return await self._fetch(spec, page_size=page_size, page_count=pages)

    async def poll(self, spec: NewsSpec) -> list[RawNewsEnvelope]:
        return await self._fetch(spec, page_size=min(max(spec.max_items, 1), 100), page_count=1)

    async def _fetch(self, spec: NewsSpec, *, page_size: int, page_count: int) -> list[RawNewsEnvelope]:
        if spec.max_items <= 0:
            return []
        own = self._client is None
        client = self._client or self._build_client()
        stock_list = ",".join(
            sorted({aid.split(":", 1)[-1] for aid in spec.asset_ids if ":" in aid})
        )
        results: list[RawNewsEnvelope] = []
        try:
            for page in range(1, page_count + 1):
                params: dict[str, Any] = {
                    "page_index": page, "page_size": page_size,
                    "ann_type": "A", "f_node": "0", "client_source": "web",
                }
                if stock_list:
                    params["stock_list"] = stock_list
                resp = await client.get(self._endpoint, params=params)
                resp.raise_for_status()
                items = resp.json().get("data", {}).get("list", [])
                if not isinstance(items, list):
                    raise IngestError("Eastmoney response did not contain data.list array")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    normalized = dict(item)
                    normalized.setdefault("headline", _first_str(item, "notice_title", "title", "art_title"))
                    normalized.setdefault("body", _first_str(item, "summary", "digest", "column_name"))
                    normalized.setdefault("url", _build_url(item))
                    env = RawNewsEnvelope(
                        source=self.source_name,
                        vendor_id=str(
                            item.get("art_code") or item.get("notice_code") or item.get("info_code")
                            or normalized.get("url") or normalized.get("headline")
                        ),
                        raw_payload=normalized,
                        received_at=utc_now(),
                        published_at=parse_vendor_datetime(
                            item.get("notice_date") or item.get("display_time") or item.get("eitime")
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
            logger.error("Eastmoney fetch failed: %s", exc)
            raise IngestError(f"Eastmoney fetch failed: {exc}") from exc
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


def _build_url(payload: dict[str, Any]) -> str:
    code = payload.get("art_code")
    return f"https://data.eastmoney.com/notices/detail/{code}.html" if isinstance(code, str) and code.strip() else ""
