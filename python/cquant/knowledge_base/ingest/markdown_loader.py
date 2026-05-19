"""cquant.knowledge_base.ingest.markdown_loader — Markdown / plain text loader."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from cquant.core.errors import IngestError
from cquant.knowledge_base.ingest.base import DocumentLoader
from cquant.knowledge_base.schemas.document import (
    DocumentMeta,
    IngestRequest,
    LoadedDocument,
)
from cquant.knowledge_base.store.filesystem import KBFilesystem

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class MarkdownLoader(DocumentLoader):
    """Load Markdown (.md) and plain text (.txt) files."""

    @property
    def source_type(self) -> str:
        return "markdown"

    def can_load(self, uri: str, mime_type: str | None = None) -> bool:
        return Path(uri).suffix.lower() in {".md", ".markdown", ".txt"}

    def load(self, request: IngestRequest) -> LoadedDocument:
        path = Path(request.uri)
        if not path.exists():
            raise IngestError(f"File not found: {path}")

        raw = path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _parse_frontmatter(raw)

        fs = KBFilesystem()
        doc_id, raw_path, content_hash = fs.stage_raw(
            request, raw.encode("utf-8"), suffix=path.suffix or ".md"
        )

        title = request.title or frontmatter.get("title", path.stem)
        source_name = request.source_name or frontmatter.get("author", "")

        meta = DocumentMeta(
            doc_id=doc_id,
            title=title,
            source_name=source_name,
            logical_type=request.logical_type,
            source_type=self.source_type,
            language=request.language,
            content_hash=content_hash,
            ingested_at=datetime.now(tz=timezone.utc),
        )
        return LoadedDocument(doc_id=doc_id, source_type=self.source_type,
                              raw_path=raw_path, text=body, meta=meta)


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter (if any) and return (meta_dict, body)."""
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw
    fm_text = match.group(1)
    body = raw[match.end():]
    meta: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body
