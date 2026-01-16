"""SQLite storage for tracking progress over time."""

import sqlite3
import json
from datetime import datetime
from typing import Optional
from config import DB_PATH


def get_db() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema."""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
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
                pitch_feedback TEXT,
                volume_feedback TEXT,
                tempo_feedback TEXT,
                rhythm_feedback TEXT,
                pause_feedback TEXT,
                ai_summary TEXT,
                ai_tips TEXT
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_created_at
            ON sessions(created_at)
        """)

        # Migrate existing databases - add new columns if missing
        new_columns = [
            "pitch_feedback", "volume_feedback", "tempo_feedback",
            "rhythm_feedback", "pause_feedback",
            "ai_summary", "ai_tips"
        ]
        for col in new_columns:
            try:
                db.execute(f"ALTER TABLE sessions ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists


def save_session(
    analysis,
    mode: str = "analyze",
    prompt_id: Optional[str] = None,
    transcript: Optional[str] = None,
    ai_summary: Optional[str] = None,
    ai_tips: Optional[list[str]] = None,
) -> int:
    """
    Save an analysis session to the database.

    Args:
        analysis: ProsodyAnalysis object
        mode: 'analyze' or 'practice'
        prompt_id: ID of the practice prompt (if practice mode)
        transcript: AI transcription (if available)
        ai_summary: AI overall feedback/summary
        ai_tips: List of AI coaching tips

    Returns:
        Session ID
    """
    init_db()

    data = analysis.to_dict()
    tips_json = json.dumps(ai_tips) if ai_tips else None

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO sessions (
                created_at, duration, pitch_score, volume_score,
                tempo_score, rhythm_score, pause_score, overall_score,
                mode, prompt_id, transcript,
                pitch_feedback, volume_feedback, tempo_feedback,
                rhythm_feedback, pause_feedback,
                ai_summary, ai_tips
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                data["duration"],
                data["pitch_score"],
                data["volume_score"],
                data["tempo_score"],
                data["rhythm_score"],
                data["pause_score"],
                data["overall_score"],
                mode,
                prompt_id,
                transcript,
                analysis.pitch.feedback,
                analysis.volume.feedback,
                analysis.tempo.feedback,
                analysis.rhythm.feedback,
                analysis.pauses.feedback,
                ai_summary,
                tips_json,
            ),
        )
        return cursor.lastrowid


def get_history(limit: int = 10, mode: Optional[str] = None) -> list[dict]:
    """
    Get recent sessions.

    Args:
        limit: Maximum number of sessions to return
        mode: Filter by mode ('analyze' or 'practice')

    Returns:
        List of session dictionaries
    """
    init_db()

    with get_db() as db:
        if mode:
            rows = db.execute(
                """
                SELECT * FROM sessions
                WHERE mode = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (mode, limit),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT * FROM sessions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]


def get_stats(days: int = 30) -> dict:
    """
    Get aggregate statistics for progress tracking.

    Args:
        days: Number of days to include in stats

    Returns:
        Dictionary with stats
    """
    init_db()

    with get_db() as db:
        # Total sessions
        total = db.execute(
            "SELECT COUNT(*) as count FROM sessions"
        ).fetchone()["count"]

        if total == 0:
            return {
                "total_sessions": 0,
                "total_practice_time": 0,
                "averages": None,
                "recent_trend": None,
            }

        # Average scores (all time)
        averages = db.execute(
            """
            SELECT
                AVG(pitch_score) as pitch,
                AVG(volume_score) as volume,
                AVG(tempo_score) as tempo,
                AVG(rhythm_score) as rhythm,
                AVG(pause_score) as pause,
                AVG(overall_score) as overall,
                SUM(duration) as total_duration
            FROM sessions
            """
        ).fetchone()

        # Recent sessions (last N days) vs older
        recent = db.execute(
            """
            SELECT AVG(overall_score) as avg_score
            FROM sessions
            WHERE created_at >= datetime('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()

        older = db.execute(
            """
            SELECT AVG(overall_score) as avg_score
            FROM sessions
            WHERE created_at < datetime('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()

        # Calculate trend
        trend = None
        if recent["avg_score"] and older["avg_score"]:
            trend = recent["avg_score"] - older["avg_score"]

        return {
            "total_sessions": total,
            "total_practice_time": round(averages["total_duration"] / 60, 1),  # minutes
            "averages": {
                "pitch": round(averages["pitch"], 1),
                "volume": round(averages["volume"], 1),
                "tempo": round(averages["tempo"], 1),
                "rhythm": round(averages["rhythm"], 1),
                "pause": round(averages["pause"], 1),
                "overall": round(averages["overall"], 1),
            },
            "recent_trend": round(trend, 2) if trend else None,
        }


def get_session(session_id: int) -> Optional[dict]:
    """Get a single session by ID."""
    init_db()

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if row:
            result = dict(row)
            # Parse JSON tips back to list
            if result.get("ai_tips"):
                result["ai_tips"] = json.loads(result["ai_tips"])
            return result
        return None


def get_best_and_worst() -> dict:
    """Get best and worst performing components."""
    init_db()

    with get_db() as db:
        row = db.execute(
            """
            SELECT
                AVG(pitch_score) as pitch,
                AVG(volume_score) as volume,
                AVG(tempo_score) as tempo,
                AVG(rhythm_score) as rhythm,
                AVG(pause_score) as pause
            FROM sessions
            """
        ).fetchone()

        if not row or row["pitch"] is None:
            return {"best": None, "worst": None}

        scores = {
            "pitch": row["pitch"],
            "volume": row["volume"],
            "tempo": row["tempo"],
            "rhythm": row["rhythm"],
            "pause": row["pause"],
        }

        best = max(scores, key=scores.get)
        worst = min(scores, key=scores.get)

        return {
            "best": (best, round(scores[best], 1)),
            "worst": (worst, round(scores[worst], 1)),
        }
