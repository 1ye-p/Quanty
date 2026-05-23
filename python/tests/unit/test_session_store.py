"""Tests for AI advisor session persistence."""
from __future__ import annotations

import pytest

from cquant.ai_advisor.agents.base import AgentTurn
from cquant.ai_advisor.orchestrator import AdvisorSession
from cquant.ai_advisor.session_store import SessionStore


@pytest.fixture()
def store(tmp_path):
    return SessionStore(db_path=tmp_path / "sessions.db")


def _make_session(n_turns: int = 2) -> AdvisorSession:
    session = AdvisorSession(session_id="test-session-001")
    for i in range(n_turns):
        session.history.append(AgentTurn(
            role="user" if i % 2 == 0 else "assistant",
            content=f"Turn {i}",
            artifacts=[f"artifact_{i}"] if i % 2 == 1 else [],
        ))
    return session


class TestSessionStore:
    def test_save_and_load_roundtrip(self, store: SessionStore) -> None:
        session = _make_session(4)
        store.save(session)
        loaded = store.load("test-session-001")
        assert loaded is not None
        assert loaded.session_id == "test-session-001"
        assert len(loaded.history) == 4

    def test_loaded_history_content_matches(self, store: SessionStore) -> None:
        session = _make_session(2)
        store.save(session)
        loaded = store.load("test-session-001")
        assert loaded.history[0].role == "user"
        assert loaded.history[0].content == "Turn 0"
        assert loaded.history[1].role == "assistant"
        assert loaded.history[1].content == "Turn 1"
        assert loaded.history[1].artifacts == ["artifact_1"]

    def test_load_nonexistent_returns_none(self, store: SessionStore) -> None:
        assert store.load("nonexistent-session") is None

    def test_list_sessions_empty_initially(self, store: SessionStore) -> None:
        assert store.list_sessions() == []

    def test_list_sessions_after_save(self, store: SessionStore) -> None:
        store.save(_make_session())
        s2 = AdvisorSession(session_id="session-002")
        store.save(s2)
        sessions = store.list_sessions()
        assert set(sessions) == {"test-session-001", "session-002"}

    def test_save_is_idempotent(self, store: SessionStore) -> None:
        session = _make_session(2)
        store.save(session)
        store.save(session)
        assert store.list_sessions().count("test-session-001") == 1

    def test_delete_removes_session(self, store: SessionStore) -> None:
        store.save(_make_session())
        store.delete("test-session-001")
        assert store.load("test-session-001") is None
        assert "test-session-001" not in store.list_sessions()

    def test_save_updates_existing_session(self, store: SessionStore) -> None:
        session = _make_session(1)
        store.save(session)
        session.history.append(AgentTurn(role="user", content="New turn"))
        store.save(session)
        loaded = store.load("test-session-001")
        assert len(loaded.history) == 2
