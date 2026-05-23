"""cquant.newsflow.normalize — Normalize raw envelopes to the Silver news schema."""

from __future__ import annotations

import html
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

import polars as pl

from cquant.newsflow.connectors.base import RawNewsEnvelope, ensure_utc
from cquant.newsflow.sentiment import score_sentiment

NEWS_EVENT_SCHEMA: dict[str, pl.DataType] = {
    "event_id": pl.Utf8,
    "source": pl.Utf8,
    "vendor_id": pl.Utf8,
    "headline": pl.Utf8,
    "body": pl.Utf8,
    "published_at": pl.Datetime(time_unit="us", time_zone="UTC"),
    "available_at": pl.Datetime(time_unit="us", time_zone="UTC"),
    "ingested_at": pl.Datetime(time_unit="us", time_zone="UTC"),
    "asset_ids_mentioned": pl.List(pl.Utf8),
    "event_type": pl.Utf8,
    "sentiment_score": pl.Float64,
    "language": pl.Utf8,
    "region": pl.Utf8,
    "dedupe_key": pl.Utf8,
}

# Per-source propagation latency estimates (published_at + latency <= available_at)
_DEFAULT_LATENCY: dict[str, timedelta] = {
    "sina": timedelta(minutes=2),
    "eastmoney": timedelta(minutes=1),
    "rss": timedelta(minutes=5),
}

_CN_TICKER_RE = re.compile(r"(?<!\d)([036]\d{5})(?!\d)")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TAG_RE = re.compile(r"<[^>]+>")


class NewsNormalizer:
    """Transform raw envelopes into the silver_news_events schema."""

    def __init__(self, latency_by_source: Mapping[str, timedelta] | None = None) -> None:
        self._latency = dict(_DEFAULT_LATENCY)
        if latency_by_source:
            self._latency.update(latency_by_source)

    def normalize(self, envelopes: Iterable[RawNewsEnvelope]) -> pl.DataFrame:
        rows = [self._one(e) for e in envelopes]
        if not rows:
            return pl.DataFrame(schema=NEWS_EVENT_SCHEMA)
        return (
            pl.DataFrame(rows, schema=NEWS_EVENT_SCHEMA, strict=False)
            .select(list(NEWS_EVENT_SCHEMA))
            .sort(["available_at", "source", "vendor_id"])
        )

    def _one(self, env: RawNewsEnvelope) -> dict[str, Any]:
        p = env.raw_payload
        headline = _clean(_first_str(p, "headline", "title", "notice_title", "art_title"))
        body = _clean(_first_str(p, "body", "content", "summary", "digest", "description", "brief"))
        published_at = ensure_utc(env.published_at)
        ingested_at = ensure_utc(env.received_at) or datetime.now(tz=timezone.utc)
        latency = self._latency.get(env.source, timedelta())
        available_at = _available(published_at, ingested_at, latency)
        dedupe_key = build_dedupe_key(env.source, env.vendor_id)
        return {
            "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, dedupe_key)),
            "source": env.source,
            "vendor_id": env.vendor_id,
            "headline": headline,
            "body": body,
            "published_at": published_at,
            "available_at": available_at,
            "ingested_at": ingested_at,
            "asset_ids_mentioned": _extract_asset_ids(headline),
            "event_type": _event_type(env.source, p),
            "sentiment_score": score_sentiment(headline, _language(headline, body)),
            "language": _language(headline, body),
            "region": _region(env.source),
            "dedupe_key": dedupe_key,
        }


def build_dedupe_key(source: str, vendor_id: str) -> str:
    return f"{source}::{vendor_id}"


def _available(published_at: datetime | None, received_at: datetime, latency: timedelta) -> datetime:
    if published_at is None:
        return received_at
    return max(published_at + latency, received_at)


def _extract_asset_ids(headline: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for m in _CN_TICKER_RE.finditer(headline):
        code = m.group(1)
        aid = ("SSE" if code.startswith("6") else "SZSE") + ":" + code
        if aid not in seen:
            seen.add(aid)
            result.append(aid)
    return result


def _clean(value: str) -> str:
    if not value:
        return ""
    return " ".join(_TAG_RE.sub(" ", html.unescape(value)).split())


def _first_str(payload: dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _event_type(source: str, payload: dict[str, Any]) -> str:
    explicit = payload.get("event_type")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if source == "eastmoney":
        return "announcement"
    if source.startswith("rss"):
        return "rss_item"
    return "news"


def _language(headline: str, body: str) -> str:
    return "zh-CN" if _CJK_RE.search(f"{headline} {body}") else "en"


def _region(source: str) -> str:
    return "CN" if source in {"sina", "eastmoney"} else "GLOBAL"
