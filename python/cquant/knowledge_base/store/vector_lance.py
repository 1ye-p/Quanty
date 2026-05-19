"""cquant.knowledge_base.store.vector_lance — LanceDB vector store implementation.

LanceDB is Arrow-native and zero-dependency for local use.
Falls back gracefully if lancedb is not installed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cquant.core.errors import CQuantError
from cquant.knowledge_base.store.vector_base import VectorHit, VectorQuery, VectorRow, VectorStore

logger = logging.getLogger(__name__)

_COLLECTION = "kb_chunks"


class LanceVectorStore(VectorStore):
    """LanceDB-backed vector store under knowledge/vector/lancedb/."""

    def __init__(self, db_path: str | Path = "knowledge/vector/lancedb") -> None:
        self._db_path = Path(db_path)
        self._db: Any | None = None
        self._table: Any | None = None
        self._init()

    @property
    def backend(self) -> str:
        return "lancedb"

    @property
    def available(self) -> bool:
        return self._db is not None

    def _init(self) -> None:
        try:
            import lancedb
        except ImportError:
            logger.warning(
                "lancedb not installed; LanceVectorStore running in no-op mode. "
                "Install with: conda run -n cQuanty pip install lancedb"
            )
            return
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_path))

    def _get_table(self, dim: int) -> Any:
        import lancedb
        import pyarrow as pa

        schema = pa.schema([
            pa.field("vector_key", pa.string()),
            pa.field("doc_id", pa.string()),
            pa.field("chunk_id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ])

        if _COLLECTION in self._db.table_names():
            return self._db.open_table(_COLLECTION)
        return self._db.create_table(_COLLECTION, schema=schema)

    def upsert(self, rows: list[VectorRow]) -> None:
        if not self.available or not rows:
            return
        import pyarrow as pa

        dim = len(rows[0].embedding)
        table = self._get_table(dim)
        data = pa.table({
            "vector_key": [r.vector_key for r in rows],
            "doc_id":      [r.doc_id for r in rows],
            "chunk_id":    [r.chunk_id for r in rows],
            "text":        [r.text for r in rows],
            "vector":      [r.embedding for r in rows],
        })
        table.merge_insert("vector_key").when_matched_update_all().when_not_matched_insert_all().execute(data)

    def search(self, query: VectorQuery) -> list[VectorHit]:
        if not self.available:
            return []
        try:
            table = self._get_table(len(query.embedding))
            results = (
                table.search(query.embedding)
                .limit(query.top_k)
                .to_list()
            )
            hits = []
            for row in results:
                hits.append(VectorHit(
                    vector_key=row["vector_key"],
                    doc_id=row["doc_id"],
                    chunk_id=row["chunk_id"],
                    score=float(row.get("_distance", 0.0)),
                    text=row.get("text", ""),
                ))
            return hits
        except Exception as exc:
            logger.warning("LanceDB search failed: %s", exc)
            return []

    def similar_to_document(self, doc_id: str, top_k: int = 10) -> list[VectorHit]:
        """Return documents most similar to *doc_id* by centroid vector search."""
        if not self.available:
            return []
        try:
            import numpy as np
            if _COLLECTION not in self._db.table_names():
                return []
            table = self._db.open_table(_COLLECTION)
            rows = table.to_arrow().to_pylist()
            vecs = [r["vector"] for r in rows if r.get("doc_id") == doc_id]
            if not vecs:
                return []
            centroid = np.asarray(vecs, dtype=np.float32).mean(axis=0).tolist()
            results = table.search(centroid).limit(top_k + len(vecs)).to_list()

            hits: list[VectorHit] = []
            seen: set[str] = set()
            for row in results:
                cid = row.get("doc_id", "")
                if not cid or cid == doc_id or cid in seen:
                    continue
                seen.add(cid)
                hits.append(VectorHit(
                    vector_key=row["vector_key"],
                    doc_id=cid,
                    chunk_id=row["chunk_id"],
                    score=float(1.0 - row.get("_distance", 0.0)),
                    text=row.get("text", ""),
                ))
                if len(hits) >= top_k:
                    break
            return hits
        except Exception as exc:
            logger.warning("LanceDB similar_to_document failed for %s: %s", doc_id, exc)
            return []

    def delete_document(self, doc_id: str) -> None:
        if not self.available:
            return
        try:
            if _COLLECTION in self._db.table_names():
                table = self._db.open_table(_COLLECTION)
                table.delete(f"doc_id = '{doc_id}'")
        except Exception as exc:
            logger.warning("LanceDB delete failed for doc_id=%s: %s", doc_id, exc)
