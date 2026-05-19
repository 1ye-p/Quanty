"""cquant.knowledge_base.ingest.tabular_loader — CSV / Excel loader.

Normalizes to UTF-8 CSV + generates a human-readable column summary as the
"text" content for embedding and search.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from cquant.core.errors import IngestError
from cquant.knowledge_base.ingest.base import DocumentLoader
from cquant.knowledge_base.schemas.document import (
    DocumentMeta,
    IngestRequest,
    LoadedDocument,
)
from cquant.knowledge_base.store.filesystem import KBFilesystem

_SUPPORTED = {".csv", ".tsv", ".xlsx", ".xls"}


class TabularLoader(DocumentLoader):
    """Load CSV and Excel files and generate a text summary for the knowledge base."""

    @property
    def source_type(self) -> str:
        return "tabular"

    def can_load(self, uri: str, mime_type: str | None = None) -> bool:
        return Path(uri).suffix.lower() in _SUPPORTED

    def load(self, request: IngestRequest) -> LoadedDocument:
        path = Path(request.uri)
        if not path.exists():
            raise IngestError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            df = self._load_excel(path)
        else:
            df = pl.read_csv(path, try_parse_dates=True)

        text = _dataframe_summary(df, title=request.title or path.stem)
        csv_bytes = df.write_csv().encode("utf-8")

        fs = KBFilesystem()
        doc_id, raw_path, content_hash = fs.stage_raw(request, csv_bytes, suffix=".csv")

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

    @staticmethod
    def _load_excel(path: Path) -> pl.DataFrame:
        try:
            import openpyxl
            import pandas as pd
            df_pd = pd.read_excel(path)
            return pl.from_pandas(df_pd)
        except ImportError:
            raise IngestError(
                "openpyxl is required for Excel files: pip install openpyxl"
            )


def _dataframe_summary(df: pl.DataFrame, title: str) -> str:
    """Generate a text description of a DataFrame for embedding."""
    lines = [f"Table: {title}", f"Rows: {df.height}, Columns: {df.width}", ""]
    lines.append("Columns:")
    for col in df.columns:
        dtype = str(df[col].dtype)
        sample = df[col].head(3).to_list()
        lines.append(f"  {col} ({dtype}): {sample}")
    return "\n".join(lines)
