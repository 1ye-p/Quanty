"""cquant.knowledge_base.store.filesystem — Raw and processed artifact persistence.

Directory layout under knowledge/:
  raw_ingested/{source_type}/{source_slug}/{year}/{doc_id}/source.*
  processed/{stage}/{doc_id}/v{n}/{artifact}
  by_type/{logical_type}/{year}/{doc_id}.pointer.json
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cquant.knowledge_base.schemas.document import IngestRequest


class KBFilesystem:
    """Manages knowledge/ directory layout and file staging."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            # Default: knowledge/ relative to project root
            self._root = Path("knowledge")
        else:
            self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def stage_raw(
        self,
        request: IngestRequest,
        content: bytes,
        suffix: str = "",
    ) -> tuple[str, str, str]:
        """Write raw content to the immutable raw_ingested tree.

        Returns (doc_id, relative_raw_path, sha256_hex).
        """
        content_hash = hashlib.sha256(content).hexdigest()
        source_slug = _slugify(request.source_name or "unknown")
        year = datetime.now(tz=timezone.utc).strftime("%Y")
        doc_id = f"{source_slug}__{year}__{content_hash[:8]}"
        source_type = request.extra.get("source_type", _guess_source_type(request.uri))

        raw_dir = self._root / "raw_ingested" / source_type / source_slug / year / doc_id
        raw_dir.mkdir(parents=True, exist_ok=True)

        filename = f"source{suffix}"
        raw_file = raw_dir / filename
        raw_file.write_bytes(content)

        meta_file = raw_dir / "source.meta.json"
        if not meta_file.exists():
            meta: dict[str, Any] = {
                "doc_id": doc_id,
                "source_name": request.source_name,
                "title": request.title,
                "logical_type": request.logical_type,
                "language": request.language,
                "uri": request.uri,
                "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        hash_file = raw_dir / "source.hash.json"
        hash_file.write_text(
            json.dumps({"sha256": content_hash, "size_bytes": len(content)}),
            encoding="utf-8",
        )

        rel_path = str(raw_file.relative_to(self._root.parent)) if self._root.parent != Path(".") \
            else str(raw_file)
        return doc_id, rel_path, content_hash

    def write_processed(
        self,
        doc_id: str,
        version_id: str,
        stage: str,
        filename: str,
        content: str | bytes,
    ) -> str:
        """Write a processed artifact. Returns absolute path string."""
        out_dir = self._root / "processed" / stage / doc_id / f"v{version_id[:8]}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / filename
        if isinstance(content, str):
            out_file.write_text(content, encoding="utf-8")
        else:
            out_file.write_bytes(content)
        return str(out_file)

    def write_pointer(self, doc_id: str, logical_type: str, year: str, meta: dict) -> None:
        """Write a pointer file under by_type/."""
        ptr_dir = self._root / "by_type" / logical_type / year
        ptr_dir.mkdir(parents=True, exist_ok=True)
        ptr_file = ptr_dir / f"{doc_id}.pointer.json"
        ptr_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9_]", "_", text.lower())[:40].strip("_") or "unknown"


def _guess_source_type(uri: str) -> str:
    lower = uri.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.startswith("http"):
        return "url"
    if lower.endswith((".csv", ".xlsx", ".xls")):
        return "tabular"
    return "markdown"
