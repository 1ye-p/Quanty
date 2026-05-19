"""cquant.knowledge_base.process.chunking — Section-aware text chunking."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """One chunk of text extracted from a document."""

    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    section_path: str = ""
    char_start: int = 0
    char_end: int = 0
    token_count: int = 0


class TextChunker:
    """Split document text into overlapping chunks for embedding.

    Strategy:
    1. Try to split on markdown headings (##, ###) for section-aware chunks.
    2. Fall back to fixed-size windows with overlap.
    """

    def __init__(
        self,
        chunk_size: int = 512,       # Target tokens per chunk (approximated as chars/4)
        overlap: int = 64,           # Overlap tokens between consecutive chunks
    ) -> None:
        self._chunk_chars = chunk_size * 4    # Approximate: 1 token ≈ 4 chars
        self._overlap_chars = overlap * 4

    def chunk(self, doc_id: str, text: str) -> list[Chunk]:
        """Return a list of Chunks for *text*."""
        if not text.strip():
            return []

        sections = _split_by_heading(text)
        if len(sections) > 1:
            return self._chunks_from_sections(doc_id, sections)
        return self._fixed_window_chunks(doc_id, text, section_path="")

    def _chunks_from_sections(
        self, doc_id: str, sections: list[tuple[str, str]]
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        idx = 0
        for heading, body in sections:
            if not body.strip():
                continue
            for chunk in self._fixed_window_chunks(doc_id, body, section_path=heading, start_index=idx):
                chunks.append(chunk)
                idx += 1
        return chunks

    def _fixed_window_chunks(
        self,
        doc_id: str,
        text: str,
        section_path: str = "",
        start_index: int = 0,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        pos = 0
        idx = start_index
        while pos < len(text):
            end = min(pos + self._chunk_chars, len(text))
            # Try to break at sentence boundary
            if end < len(text):
                boundary = _nearest_sentence_end(text, end)
                end = boundary if boundary > pos else end

            chunk_text = text[pos:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    chunk_index=idx,
                    text=chunk_text,
                    section_path=section_path,
                    char_start=pos,
                    char_end=end,
                    token_count=len(chunk_text) // 4,
                ))
                idx += 1

            pos = end - self._overlap_chars if end < len(text) else len(text)
        return chunks


def _split_by_heading(text: str) -> list[tuple[str, str]]:
    """Split text on markdown headings. Returns [(heading, body), ...]."""
    pattern = re.compile(r"^(#{1,4}\s+.+)$", re.MULTILINE)
    parts = pattern.split(text)
    if len(parts) <= 1:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    if parts[0].strip():
        sections.append(("", parts[0]))
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((heading, body))
    return sections


def _nearest_sentence_end(text: str, pos: int) -> int:
    """Find the nearest sentence-ending punctuation near *pos*."""
    for punct in ("。", "！", "？", ". ", "! ", "? ", "\n\n"):
        idx = text.rfind(punct, max(0, pos - 100), pos)
        if idx != -1:
            return idx + len(punct)
    return pos
