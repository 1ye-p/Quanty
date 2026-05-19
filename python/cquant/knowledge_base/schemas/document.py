"""cquant.knowledge_base.schemas.document — Document and ingest data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class IngestRequest:
    """A request to ingest one document into the knowledge base."""

    uri: str                                         # Local file path or URL
    logical_type: Literal["research", "strategy", "notes", "data"] = "research"
    source_name: str = ""                            # Institution / author
    title: str = ""
    language: str = "zh-CN"
    extra: dict = field(default_factory=dict)        # Connector-specific params


@dataclass
class LoadedDocument:
    """Raw document content after loading, before LLM processing."""

    doc_id: str
    source_type: str                # 'pdf' | 'url' | 'markdown' | 'tabular'
    raw_path: str                   # Path under knowledge/raw_ingested/
    text: str                       # Extracted plain text
    meta: "DocumentMeta"
    ingest_run_id: str = ""


@dataclass
class DocumentMeta:
    """Provenance metadata for a document."""

    doc_id: str
    title: str = ""
    source_name: str = ""
    logical_type: str = "research"
    source_type: str = "pdf"
    canonical_url: str = ""
    language: str = "zh-CN"
    content_hash: str = ""
    ingested_at: datetime | None = None
    published_at: datetime | None = None
    tags: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class DocumentVersion:
    """One processing version of a document."""

    version_id: str
    doc_id: str
    extracted_text_path: str = ""
    parser_name: str = ""
    parser_version: str = "1.0"
    is_current: bool = True


@dataclass
class IngestResult:
    """Result of a completed ingest operation."""

    doc_id: str
    version_id: str
    run_id: str
    status: str              # 'ok' | 'duplicate' | 'error'
    error: str = ""
    chunk_count: int = 0
    summary_generated: bool = False
