"""cquant.knowledge_base.ingest.url_loader — Web URL loader.

Uses httpx for fetching and trafilatura for main content extraction.
Records received_at as available_at (no latency assumption for manual imports).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from cquant.core.errors import IngestError
from cquant.knowledge_base.ingest.base import DocumentLoader
from cquant.knowledge_base.schemas.document import (
    DocumentMeta,
    IngestRequest,
    LoadedDocument,
)
from cquant.knowledge_base.store.filesystem import KBFilesystem

logger = logging.getLogger(__name__)


class URLLoader(DocumentLoader):
    """Load web pages and extract main article content."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    @property
    def source_type(self) -> str:
        return "url"

    def can_load(self, uri: str, mime_type: str | None = None) -> bool:
        return uri.startswith("http://") or uri.startswith("https://")

    def load(self, request: IngestRequest) -> LoadedDocument:
        html, final_url = self._fetch(request.uri)
        text = self._extract(html)
        if not text.strip():
            raise IngestError(f"No readable content extracted from: {request.uri}")

        fs = KBFilesystem()
        doc_id, raw_path, content_hash = fs.stage_raw(
            request, html.encode("utf-8", errors="replace"), suffix=".html"
        )

        meta = DocumentMeta(
            doc_id=doc_id,
            title=request.title or _title_from_url(final_url),
            source_name=request.source_name or _domain(final_url),
            logical_type=request.logical_type,
            source_type=self.source_type,
            canonical_url=final_url,
            language=request.language,
            content_hash=content_hash,
            ingested_at=datetime.now(tz=timezone.utc),
        )
        return LoadedDocument(doc_id=doc_id, source_type=self.source_type,
                              raw_path=raw_path, text=text, meta=meta)

    def _fetch(self, url: str) -> tuple[str, str]:
        try:
            import httpx
        except ImportError as exc:
            raise IngestError("httpx is required: conda run -n cQuanty pip install httpx") from exc

        headers = {"User-Agent": "cQuant/0.1 knowledge-base"}
        with httpx.Client(timeout=self._timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text, str(response.url)

    @staticmethod
    def _extract(html: str) -> str:
        try:
            import trafilatura
            text = trafilatura.extract(html, include_comments=False, include_tables=True)
            return text or ""
        except ImportError:
            # Fallback: strip tags with stdlib
            import re
            return re.sub(r"<[^>]+>", " ", html)


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc or url


def _title_from_url(url: str) -> str:
    from urllib.parse import urlparse
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1] if path else url
