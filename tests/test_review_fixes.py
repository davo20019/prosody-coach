import sqlite3
import tomllib
from pathlib import Path
from types import SimpleNamespace


def _analysis_stub():
    return SimpleNamespace(
        pitch=SimpleNamespace(feedback="pitch ok"),
        volume=SimpleNamespace(feedback="volume ok"),
        tempo=SimpleNamespace(feedback="tempo ok"),
        rhythm=SimpleNamespace(feedback="rhythm ok"),
        pauses=SimpleNamespace(feedback="pauses ok"),
        to_dict=lambda: {
            "duration": 1.2,
            "pitch_score": 7,
            "volume_score": 8,
            "tempo_score": 6,
            "rhythm_score": 5,
            "pause_score": 9,
            "overall_score": 7.0,
        },
    )


def test_gitignore_excludes_saved_flac_recordings():
    gitignore = Path(".gitignore").read_text()

    assert "data/recordings/*.flac" in gitignore


def test_project_metadata_declares_runtime_audio_dependencies():
    metadata = tomllib.loads(Path("pyproject.toml").read_text())
    deps = {dep.split(">=", 1)[0] for dep in metadata["project"]["dependencies"]}

    assert "soundfile" in deps
    assert "bournemouth-forced-aligner" in deps


def test_api_speed_benchmark_is_opt_in_for_pytest():
    import test_optimizations

    markers = getattr(test_optimizations.test_api_speed, "pytestmark", [])
    reasons = [marker.kwargs.get("reason", "") for marker in markers]

    assert any("RUN_API_BENCHMARKS=1" in reason for reason in reasons)


def test_save_session_persists_recording_path(tmp_path, monkeypatch):
    import storage

    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "progress.db")
    recording_path = tmp_path / "recordings" / "sample.flac"

    session_id = storage.save_session(
        _analysis_stub(),
        mode="analyze",
        recording_path=recording_path,
    )

    session = storage.get_session(session_id)

    assert session["recording_path"] == str(recording_path)


def test_session_migration_uses_integer_types_for_numeric_ai_fields(tmp_path, monkeypatch):
    import storage

    db_path = tmp_path / "progress.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                duration REAL NOT NULL,
                pitch_score INTEGER NOT NULL,
                volume_score INTEGER NOT NULL,
                tempo_score INTEGER NOT NULL,
                rhythm_score INTEGER NOT NULL,
                pause_score INTEGER NOT NULL,
                overall_score REAL NOT NULL,
                mode TEXT NOT NULL DEFAULT 'analyze',
                prompt_id TEXT,
                transcript TEXT,
                confidence_score TEXT
            )
            """
        )
        db.execute(
            """
            INSERT INTO sessions (
                created_at, duration, pitch_score, volume_score, tempo_score,
                rhythm_score, pause_score, overall_score, mode, confidence_score
            ) VALUES ('2026-01-01T00:00:00', 3.0, 1, 2, 3, 4, 5, 3.0, 'analyze', '7')
            """
        )

    monkeypatch.setattr(storage, "DB_PATH", db_path)
    storage.init_db()

    with sqlite3.connect(db_path) as db:
        columns = {row[1]: row[2].upper() for row in db.execute("PRAGMA table_info(sessions)")}
        count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    assert columns["confidence_score"] == "INTEGER"
    assert columns["recording_path"] == "TEXT"
    assert count == 1


def test_parse_pronunciation_issue_separates_example_from_ipa():
    from coach import parse_coaching_response

    response = """
TRANSCRIPT:
I think so.

GRAMMAR_ISSUES:
None

SUGGESTED_REVISION:
I think so.

COACHING_TIPS:
- Keep practicing.

VOCAL_CONFIDENCE:
7 | steady

FILLER_WORDS:
0 | None detected

PRONUNCIATION_ISSUES:
th | think /θɪŋk/ | Put your tongue between your teeth.

FLUENCY:
7 | smooth

AI_PROSODY:
- PITCH: 7/10 | varied

OVERALL:
Good.
"""

    result = parse_coaching_response(response)

    assert result.pronunciation_issues == [
        {
            "sound": "th",
            "example": "think",
            "ipa": "θɪŋk",
            "tip": "Put your tongue between your teeth.",
        }
    ]


def test_realtime_audio_blob_uses_raw_pcm_bytes():
    from google.genai import types
    from realtime import RealtimeRhythmSession

    blob = RealtimeRhythmSession._audio_blob_from_pcm(b"abc")

    assert isinstance(blob, types.Blob)
    assert blob.data == b"abc"
    assert blob.mime_type.startswith("audio/pcm")
