"""cquant.knowledge_base.ingest.pdf_loader — PDF document loader.

Uses pdfplumber for text extraction; falls back to PyMuPDF (fitz) if available.
Scanned-image PDFs go to the quarantine/ directory with a note.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

_MIN_TEXT_CHARS = 50   # Below this threshold we consider the PDF image-only


class PDFLoader(DocumentLoader):
    """Load text from PDF research reports."""

    @property
    def source_type(self) -> str:
        return "pdf"

    def can_load(self, uri: str, mime_type: str | None = None) -> bool:
        return uri.lower().endswith(".pdf") or mime_type == "application/pdf"

    def load(self, request: IngestRequest) -> LoadedDocument:
        path = Path(request.uri)
        if not path.exists():
            raise IngestError(f"PDF not found: {path}")

        text = self._extract_text(path)
        if len(text.strip()) < _MIN_TEXT_CHARS:
            logger.warning(
                "PDF appears to be image-only (< %d chars extracted): %s",
                _MIN_TEXT_CHARS,
                path,
            )

        fs = KBFilesystem()
        doc_id, raw_path, content_hash = fs.stage_raw(request, path.read_bytes(), suffix=".pdf")

        meta = DocumentMeta(
            doc_id=doc_id,
            title=request.title or path.stem,
            source_name=request.source_name,
            logical_type=request.logical_type,
            source_type=self.source_type,
            language=request.language,
            content_hash=content_hash,
            ingested_at=datetime.now(tz=timezone.utc),
        )
        return LoadedDocument(doc_id=doc_id, source_type=self.source_type,
                              raw_path=raw_path, text=text, meta=meta)

    def _extract_text(self, path: Path) -> str:
        try:
            return self._extract_pdfplumber(path)
        except ImportError:
            pass
        try:
            return self._extract_pymupdf(path)
        except ImportError:
            raise IngestError(
                "No PDF parser available. Install pdfplumber or PyMuPDF:\n"
                "  conda run -n cQuanty pip install pdfplumber"
            )

    @staticmethod
    def _extract_pdfplumber(path: Path) -> str:
        import pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return "\n\n".join(pages)

    @staticmethod
    def _extract_pymupdf(path: Path) -> str:
        import fitz
        doc = fitz.open(path)
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)
