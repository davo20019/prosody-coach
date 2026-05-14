"""Round-trip the new sessions.content_feedback column."""

from types import SimpleNamespace

import pytest


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point storage at a tmp SQLite file and reset module-level state."""
    db_path = tmp_path / "prosody.db"
    monkeypatch.setattr("storage.DB_PATH", db_path)
    import storage
    storage.init_db()
    return db_path


def _fake_analysis():
    return SimpleNamespace(
        pitch=SimpleNamespace(score=8, feedback="p"),
        volume=SimpleNamespace(score=8, feedback="v"),
        tempo=SimpleNamespace(score=8, estimated_wpm=140, feedback="t"),
        rhythm=SimpleNamespace(score=8, pvi=55, feedback="r"),
        pauses=SimpleNamespace(score=8, feedback="pa"),
        to_dict=lambda: {
            "duration": 5.0, "pitch_score": 8, "volume_score": 8,
            "tempo_score": 8, "rhythm_score": 8, "pause_score": 8,
            "overall_score": 8.0,
        },
    )


def test_save_and_load_content_feedback_round_trip(isolated_db):
    import storage

    payload = {
        "clarity": {"score": 8, "note": "easy to follow"},
        "conciseness": {"score": 6, "note": "some hedging"},
        "tone": {"score": 7, "note": "casual but appropriate"},
        "revision_rationale": "trims hedges",
    }
    sid = storage.save_session(_fake_analysis(), mode="analyze", content_feedback=payload)
    row = storage.get_session(sid)
    assert row["content_feedback"] == payload


def test_save_session_accepts_none_content_feedback(isolated_db):
    import storage

    sid = storage.save_session(_fake_analysis(), mode="analyze", content_feedback=None)
    row = storage.get_session(sid)
    assert row["content_feedback"] is None


def test_sessions_table_has_content_feedback_text_column(isolated_db):
    import sqlite3
    import storage

    with sqlite3.connect(isolated_db) as db:
        cols = {row[1]: row[2].upper() for row in db.execute("PRAGMA table_info(sessions)")}
    assert "content_feedback" in cols
    assert cols["content_feedback"] == "TEXT"
