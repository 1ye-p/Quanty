"""cquant.newsflow.ingest — Async fan-in orchestration for polling-based news sources."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Coroutine, Iterable, Sequence

import polars as pl

from cquant.core.errors import CatalogError, IngestError
from cquant.datahub.catalog import Catalog
from cquant.newsflow.connectors.base import NewsConnector, NewsSpec, RawNewsEnvelope
from cquant.newsflow.normalize import NEWS_EVENT_SCHEMA, NewsNormalizer, build_dedupe_key
from cquant.newsflow.pit import PITGate

logger = logging.getLogger(__name__)
_COLS = list(NEWS_EVENT_SCHEMA)


class NewsIngestionOrchestrator:
    """Coordinate connector fan-in, dedup, normalization, and DuckDB writes.

    Usage (sync, Jupyter-friendly)::

        orchestrator = NewsIngestionOrchestrator(catalog, [SinaFinanceConnector()])
        df = orchestrator.poll(NewsSpec(source="sina", keywords=["茅台"]))
        visible = orchestrator.filter_as_of(df, as_of_ts=datetime(2025, 3, 1, tzinfo=timezone.utc))
    """

    def __init__(
        self,
        catalog: Catalog,
        connectors: Iterable[NewsConnector],
        normalizer: NewsNormalizer | None = None,
        pit_gate: PITGate | None = None,
    ) -> None:
        seen: dict[str, NewsConnector] = {}
        for c in connectors:
            if c.source_name in seen:
                raise ValueError(f"Duplicate news connector source_name: '{c.source_name}'")
            seen[c.source_name] = c
        self._catalog = catalog
        self._connectors = seen
        self._normalizer = normalizer or NewsNormalizer()
        self._pit_gate = pit_gate or PITGate()

    # ── Sync wrappers (Jupyter / CLI friendly) ─────────────────────────────────

    def backfill(self, specs: Sequence[NewsSpec] | NewsSpec) -> pl.DataFrame:
        return _run_sync(lambda: self.backfill_async(_coerce(specs)))

    async def backfill_async(self, specs: Sequence[NewsSpec] | NewsSpec) -> pl.DataFrame:
        return await self._ingest(_coerce(specs), mode="backfill")

    def poll(self, specs: Sequence[NewsSpec] | NewsSpec) -> pl.DataFrame:
        return _run_sync(lambda: self.poll_async(_coerce(specs)))

    async def poll_async(self, specs: Sequence[NewsSpec] | NewsSpec) -> pl.DataFrame:
        return await self._ingest(_coerce(specs), mode="poll")

    def filter_as_of(self, frame: pl.DataFrame, as_of_ts: datetime) -> pl.DataFrame:
        return self._pit_gate.filter(frame, as_of_ts)

    # ── Core async pipeline ────────────────────────────────────────────────────

    async def _ingest(self, specs: Sequence[NewsSpec], *, mode: str) -> pl.DataFrame:
        if not specs:
            return pl.DataFrame(schema=NEWS_EVENT_SCHEMA)

        self._catalog.initialize()
        batches = await asyncio.gather(*(_fetch_one(spec, mode, self._connectors) for spec in specs))
        envelopes = [e for batch in batches for e in batch]
        deduped = _dedup(envelopes)
        fresh = self._drop_existing(deduped)
        if not fresh:
            return pl.DataFrame(schema=NEWS_EVENT_SCHEMA)

        frame = self._normalizer.normalize(fresh)
        if not frame.is_empty():
            self._write(frame)
        return frame

    def _drop_existing(self, envelopes: list[RawNewsEnvelope]) -> list[RawNewsEnvelope]:
        keys = [build_dedupe_key(e.source, e.vendor_id) for e in envelopes]
        existing = self._existing_keys(keys)
        return [e for e in envelopes if build_dedupe_key(e.source, e.vendor_id) not in existing]

    def _existing_keys(self, keys: list[str]) -> set[str]:
        out: set[str] = set()
        for start in range(0, len(keys), 500):
            chunk = keys[start: start + 500]
            ph = ", ".join("?" * len(chunk))
            df = self._catalog.query(
                f"SELECT dedupe_key FROM silver_news_events WHERE dedupe_key IN ({ph})", chunk
            )
            if "dedupe_key" in df.columns:
                out.update(str(v) for v in df["dedupe_key"].to_list())
        return out

    def _write(self, frame: pl.DataFrame) -> None:
        conn = self._catalog._get_conn()
        stage = "_news_stage"
        cols = ", ".join(_COLS)
        conn.register(stage, frame.to_arrow())
        try:
            conn.execute(
                f"INSERT INTO silver_news_events ({cols}) SELECT {cols} FROM {stage}"
            )
        except Exception as exc:
            raise CatalogError(f"Failed to write silver_news_events: {exc}") from exc
        finally:
            try:
                conn.unregister(stage)
            except Exception:
                pass


async def _fetch_one(
    spec: NewsSpec,
    mode: str,
    connectors: dict[str, NewsConnector],
) -> list[RawNewsEnvelope]:
    connector = connectors.get(spec.source)
    if connector is None:
        raise IngestError(f"No news connector registered for source '{spec.source}'")
    return await (connector.backfill(spec) if mode == "backfill" else connector.poll(spec))


def _dedup(envelopes: list[RawNewsEnvelope]) -> list[RawNewsEnvelope]:
    seen: set[str] = set()
    out: list[RawNewsEnvelope] = []
    for e in sorted(envelopes, key=lambda x: (x.source, x.vendor_id, x.received_at)):
        k = build_dedupe_key(e.source, e.vendor_id)
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def _coerce(specs: Sequence[NewsSpec] | NewsSpec) -> list[NewsSpec]:
    return [specs] if isinstance(specs, NewsSpec) else list(specs)


def _run_sync(factory: Callable[[], Coroutine[object, object, pl.DataFrame]]) -> pl.DataFrame:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(factory())).result()
