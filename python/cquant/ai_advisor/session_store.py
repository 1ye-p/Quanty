"""cquant.ai_advisor.session_store — SQLite-backed session persistence."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS advisor_sessions (
    session_id   TEXT PRIMARY KEY,
    history_json TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
)
"""


class SessionStore:
    """Persist AdvisorSession objects to SQLite.

    Usage::

        store = SessionStore("data/advisor_sessions.db")
        store.save(session)
        session = store.load(session_id)
        all_ids = store.list_sessions()
        store.delete(session_id)
    """

    def __init__(self, db_path: str | Path = "data/advisor_sessions.db") -> None:
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @property
    def db_path(self) -> Path:
        """Public path to the SQLite database file."""
        return self._db_path

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_DDL)

    @staticmethod
    def _serialize_history(history: list) -> str:
        return json.dumps([
            {"role": t.role, "content": t.content, "artifacts": t.artifacts}
            for t in history
        ])

    @staticmethod
    def _deserialize_history(history_json: str) -> list:
        from cquant.ai_advisor.agents.base import AgentTurn
        turns = json.loads(history_json)
        return [
            AgentTurn(
                role=t["role"],
                content=t["content"],
                artifacts=t.get("artifacts", []),
            )
            for t in turns
        ]

    def save(self, session) -> None:
        """Persist *session* (INSERT or UPDATE)."""
        now = datetime.now(tz=timezone.utc).isoformat()
        history_json = self._serialize_history(session.history)
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            existing = conn.execute(
                "SELECT created_at FROM advisor_sessions WHERE session_id = ?",
                [session.session_id],
            ).fetchone()
            created_at = existing[0] if existing else now
            conn.execute(
                "INSERT OR REPLACE INTO advisor_sessions "
                "(session_id, history_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                [session.session_id, history_json, created_at, now],
            )

    def load(self, session_id: str):
        """Return an AdvisorSession for *session_id*, or None if not found."""
        from cquant.ai_advisor.orchestrator import AdvisorSession
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            row = conn.execute(
                "SELECT history_json FROM advisor_sessions WHERE session_id = ?",
                [session_id],
            ).fetchone()
        if row is None:
            return None
        session = AdvisorSession(session_id=session_id)
        session.history = self._deserialize_history(row[0])
        return session

    def list_sessions(self) -> list[str]:
        """Return all session IDs ordered by most recently updated."""
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            rows = conn.execute(
                "SELECT session_id FROM advisor_sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [row[0] for row in rows]

    def delete(self, session_id: str) -> None:
        """Delete a session by ID. No-op if not found."""
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            conn.execute(
                "DELETE FROM advisor_sessions WHERE session_id = ?",
                [session_id],
            )
