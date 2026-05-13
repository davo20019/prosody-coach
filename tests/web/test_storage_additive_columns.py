import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "progress.db"
    monkeypatch.setattr("storage.DB_PATH", db_path)
    import storage
    storage.init_db()
    yield db_path


def _analysis_stub():
    return SimpleNamespace(
        pitch=SimpleNamespace(score=7, feedback="p"),
        volume=SimpleNamespace(score=7, feedback="v"),
        tempo=SimpleNamespace(score=7, estimated_wpm=140, feedback="t"),
        rhythm=SimpleNamespace(score=7, pvi=55, feedback="r"),
        pauses=SimpleNamespace(score=7, feedback="pa"),
        to_dict=lambda: {
            "duration": 5.0, "pitch_score": 7, "volume_score": 7,
            "tempo_score": 7, "rhythm_score": 7, "pause_score": 7,
            "overall_score": 7.0,
        },
    )


def test_sessions_table_has_provider_columns(fresh_db):
    with sqlite3.connect(fresh_db) as db:
        cols = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
    assert "coach_provider" in cols
    assert "coach_status" in cols
    assert "coach_error" in cols


def test_save_session_persists_provider_fields(fresh_db):
    import storage
    sid = storage.save_session(
        _analysis_stub(),
        coach_provider="gemini",
        coach_status="ok",
        coach_error=None,
    )
    row = storage.get_session(sid)
    assert row["coach_provider"] == "gemini"
    assert row["coach_status"] == "ok"
    assert row["coach_error"] is None


def test_save_session_records_failed_coaching(fresh_db):
    import storage
    sid = storage.save_session(
        _analysis_stub(),
        coach_provider="local",
        coach_status="failed",
        coach_error="whisper-cli not found",
    )
    row = storage.get_session(sid)
    assert row["coach_status"] == "failed"
    assert row["coach_error"] == "whisper-cli not found"
