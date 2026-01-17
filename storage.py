"""SQLite storage for tracking progress over time."""

import sqlite3
import json
from datetime import datetime, date, timedelta
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
                ai_tips TEXT,
                grammar_issues TEXT,
                suggested_revision TEXT,
                confidence_score INTEGER,
                confidence_feedback TEXT,
                filler_word_count INTEGER,
                filler_words_detail TEXT,
                pronunciation_issues TEXT,
                fluency_score INTEGER,
                fluency_feedback TEXT
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
            "ai_summary", "ai_tips",
            "grammar_issues", "suggested_revision",
            "confidence_score", "confidence_feedback",
            "filler_word_count", "filler_words_detail",
            "pronunciation_issues", "fluency_score", "fluency_feedback"
        ]
        for col in new_columns:
            try:
                db.execute(f"ALTER TABLE sessions ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Sound tracking table for spaced repetition
        db.execute("""
            CREATE TABLE IF NOT EXISTS sound_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sound TEXT UNIQUE NOT NULL,
                ipa TEXT,
                example_word TEXT,
                first_seen TEXT NOT NULL,
                times_encountered INTEGER DEFAULT 1,
                times_practiced INTEGER DEFAULT 0,
                times_correct INTEGER DEFAULT 0,
                last_practiced TEXT,
                interval_days REAL DEFAULT 1.0,
                next_review TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sound_tracking_next_review
            ON sound_tracking(next_review)
        """)

        # Word tracking table for mispronounced words
        db.execute("""
            CREATE TABLE IF NOT EXISTS word_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE NOT NULL,
                ipa TEXT,
                related_sound TEXT,
                first_seen TEXT NOT NULL,
                times_mispronounced INTEGER DEFAULT 1,
                times_practiced INTEGER DEFAULT 0,
                times_correct INTEGER DEFAULT 0,
                last_practiced TEXT,
                interval_days REAL DEFAULT 1.0,
                next_review TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_word_tracking_next_review
            ON word_tracking(next_review)
        """)


def save_session(
    analysis,
    mode: str = "analyze",
    prompt_id: Optional[str] = None,
    transcript: Optional[str] = None,
    ai_summary: Optional[str] = None,
    ai_tips: Optional[list[str]] = None,
    grammar_issues: Optional[list[dict]] = None,
    suggested_revision: Optional[str] = None,
    confidence_score: Optional[int] = None,
    confidence_feedback: Optional[str] = None,
    filler_word_count: Optional[int] = None,
    filler_words_detail: Optional[str] = None,
    pronunciation_issues: Optional[list[dict]] = None,
    fluency_score: Optional[int] = None,
    fluency_feedback: Optional[str] = None,
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
        grammar_issues: List of grammar issues from AI
        suggested_revision: AI suggested revision of speech
        confidence_score: Vocal confidence score (1-10)
        confidence_feedback: Explanation of confidence assessment
        filler_word_count: Count of filler words
        filler_words_detail: Details about filler words used
        pronunciation_issues: List of pronunciation issues
        fluency_score: Fluency score (1-10)
        fluency_feedback: Explanation of fluency assessment

    Returns:
        Session ID
    """
    init_db()

    data = analysis.to_dict()
    tips_json = json.dumps(ai_tips) if ai_tips else None
    grammar_json = json.dumps(grammar_issues) if grammar_issues else None
    pron_json = json.dumps(pronunciation_issues) if pronunciation_issues else None

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO sessions (
                created_at, duration, pitch_score, volume_score,
                tempo_score, rhythm_score, pause_score, overall_score,
                mode, prompt_id, transcript,
                pitch_feedback, volume_feedback, tempo_feedback,
                rhythm_feedback, pause_feedback,
                ai_summary, ai_tips,
                grammar_issues, suggested_revision,
                confidence_score, confidence_feedback,
                filler_word_count, filler_words_detail,
                pronunciation_issues, fluency_score, fluency_feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                grammar_json,
                suggested_revision,
                confidence_score,
                confidence_feedback,
                filler_word_count,
                filler_words_detail,
                pron_json,
                fluency_score,
                fluency_feedback,
            ),
        )
        session_id = cursor.lastrowid

    # Track pronunciation issues for spaced repetition (sounds)
    if pronunciation_issues:
        for issue in pronunciation_issues:
            sound = issue.get("sound", "")
            ipa = issue.get("ipa", "")
            example = issue.get("example", "")
            if sound:
                track_sound(sound, ipa, example)

            # Also track the specific mispronounced word
            if example:
                # Extract word from example (format: "word /IPA/" or just "word")
                import re
                word_match = re.match(r'^([a-zA-Z]+)', example)
                if word_match:
                    word = word_match.group(1)
                    track_word(word, ipa, sound)

    # Track mispronounced words from grammar issues (format: "said X" -> "should be Y")
    if grammar_issues:
        for issue in grammar_issues:
            corrected = issue.get("corrected", "")
            explanation = issue.get("explanation", "")
            # Extract the corrected word if it's a pronunciation issue
            if corrected and ("pronounc" in explanation.lower() or "sound" in explanation.lower()):
                import re
                word_match = re.match(r'^([a-zA-Z]+)', corrected.strip())
                if word_match:
                    word = word_match.group(1)
                    track_word(word, "", "")

    return session_id


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
            # Parse JSON fields back to lists
            if result.get("ai_tips"):
                result["ai_tips"] = json.loads(result["ai_tips"])
            if result.get("grammar_issues"):
                result["grammar_issues"] = json.loads(result["grammar_issues"])
            if result.get("pronunciation_issues"):
                result["pronunciation_issues"] = json.loads(result["pronunciation_issues"])
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


def get_user_weaknesses(limit: int = 10) -> dict:
    """
    Analyze recent sessions to identify user's weak areas for tailored training.

    Args:
        limit: Number of recent sessions to analyze

    Returns:
        Dictionary with identified weaknesses and recommendations
    """
    init_db()

    with get_db() as db:
        # Get session count
        count = db.execute("SELECT COUNT(*) as count FROM sessions").fetchone()["count"]

        if count < 3:
            return {"sufficient_data": False, "session_count": count}

        # Get recent sessions
        rows = db.execute(
            """
            SELECT
                pitch_score, volume_score, tempo_score, rhythm_score, pause_score,
                confidence_score, fluency_score, filler_word_count,
                pronunciation_issues
            FROM sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        # Calculate average scores
        prosody_scores = {
            "pitch": [],
            "volume": [],
            "tempo": [],
            "rhythm": [],
            "pause": [],
        }
        confidence_scores = []
        fluency_scores = []
        filler_counts = []
        all_pronunciation_issues = []

        for row in rows:
            prosody_scores["pitch"].append(row["pitch_score"])
            prosody_scores["volume"].append(row["volume_score"])
            prosody_scores["tempo"].append(row["tempo_score"])
            prosody_scores["rhythm"].append(row["rhythm_score"])
            prosody_scores["pause"].append(row["pause_score"])

            if row["confidence_score"]:
                try:
                    confidence_scores.append(int(row["confidence_score"]))
                except (ValueError, TypeError):
                    pass
            if row["fluency_score"]:
                try:
                    fluency_scores.append(int(row["fluency_score"]))
                except (ValueError, TypeError):
                    pass
            if row["filler_word_count"]:
                try:
                    filler_counts.append(int(row["filler_word_count"]))
                except (ValueError, TypeError):
                    pass
            if row["pronunciation_issues"]:
                issues = json.loads(row["pronunciation_issues"])
                all_pronunciation_issues.extend(issues)

        # Calculate averages
        avg_prosody = {k: sum(v) / len(v) if v else 0 for k, v in prosody_scores.items()}
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        avg_fluency = sum(fluency_scores) / len(fluency_scores) if fluency_scores else 0
        avg_fillers = sum(filler_counts) / len(filler_counts) if filler_counts else 0

        # Identify weak prosody areas (score < 6)
        weak_prosody = [(k, round(v, 1)) for k, v in avg_prosody.items() if v < 6]
        weak_prosody.sort(key=lambda x: x[1])  # Sort by score ascending

        # Count recurring pronunciation issues
        sound_counts = {}
        for issue in all_pronunciation_issues:
            sound = issue.get("sound", "unknown")
            sound_counts[sound] = sound_counts.get(sound, 0) + 1

        # Get top pronunciation issues (appeared more than once)
        recurring_sounds = [(sound, count) for sound, count in sound_counts.items() if count > 1]
        recurring_sounds.sort(key=lambda x: x[1], reverse=True)

        # Determine difficulty level based on overall performance
        overall_avg = sum(avg_prosody.values()) / len(avg_prosody)
        if overall_avg >= 7:
            difficulty = "advanced"
        elif overall_avg >= 5:
            difficulty = "intermediate"
        else:
            difficulty = "beginner"

        # Build focus areas
        focus_areas = []

        # Add weakest prosody areas (top 2)
        for area, score in weak_prosody[:2]:
            focus_areas.append({
                "type": "prosody",
                "area": area,
                "score": score,
                "description": f"Improve {area} (avg: {score}/10)"
            })

        # Add pronunciation issues (top 3)
        for sound, count in recurring_sounds[:3]:
            focus_areas.append({
                "type": "pronunciation",
                "sound": sound,
                "occurrences": count,
                "description": f"Practice '{sound}' sound ({count} occurrences)"
            })

        # Add confidence if low
        if avg_confidence and avg_confidence < 6:
            focus_areas.append({
                "type": "confidence",
                "score": round(avg_confidence, 1),
                "description": f"Build vocal confidence (avg: {round(avg_confidence, 1)}/10)"
            })

        # Add fluency if low
        if avg_fluency and avg_fluency < 6:
            focus_areas.append({
                "type": "fluency",
                "score": round(avg_fluency, 1),
                "description": f"Improve fluency (avg: {round(avg_fluency, 1)}/10)"
            })

        # Add filler words if high
        if avg_fillers > 3:
            focus_areas.append({
                "type": "filler_words",
                "avg_count": round(avg_fillers, 1),
                "description": f"Reduce filler words (avg: {round(avg_fillers, 1)} per session)"
            })

        return {
            "sufficient_data": True,
            "session_count": count,
            "difficulty": difficulty,
            "focus_areas": focus_areas,
            "avg_prosody": {k: round(v, 1) for k, v in avg_prosody.items()},
            "avg_confidence": round(avg_confidence, 1) if avg_confidence else None,
            "avg_fluency": round(avg_fluency, 1) if avg_fluency else None,
            "avg_fillers": round(avg_fillers, 1) if avg_fillers else None,
            "recurring_sounds": recurring_sounds[:5],
        }


# =============================================================================
# Spaced Repetition for Pronunciation
# =============================================================================

def track_sound(sound: str, ipa: str = "", example_word: str = "") -> None:
    """
    Track a pronunciation issue for spaced repetition.

    If the sound already exists, increment times_encountered.
    If new, add it with next_review set to tomorrow.

    Args:
        sound: The sound that needs practice (e.g., "th", "v", "short i")
        ipa: IPA representation (e.g., "/θ/")
        example_word: Example word containing this sound
    """
    init_db()

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    with get_db() as db:
        # Check if sound already exists
        existing = db.execute(
            "SELECT id, times_encountered FROM sound_tracking WHERE sound = ?",
            (sound,)
        ).fetchone()

        if existing:
            # Increment encounter count
            db.execute(
                """
                UPDATE sound_tracking
                SET times_encountered = times_encountered + 1
                WHERE sound = ?
                """,
                (sound,)
            )
        else:
            # Add new sound
            db.execute(
                """
                INSERT INTO sound_tracking (
                    sound, ipa, example_word, first_seen,
                    times_encountered, next_review
                ) VALUES (?, ?, ?, ?, 1, ?)
                """,
                (sound, ipa, example_word, today, tomorrow)
            )


def get_due_sounds(limit: int = 10) -> list[dict]:
    """
    Get sounds that are due for review today or earlier.

    Args:
        limit: Maximum number of sounds to return

    Returns:
        List of sound dictionaries ordered by priority (most overdue first)
    """
    init_db()

    today = date.today().isoformat()

    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                sound, ipa, example_word, times_encountered,
                times_practiced, times_correct, interval_days, next_review
            FROM sound_tracking
            WHERE next_review <= ?
            ORDER BY next_review ASC, times_encountered DESC
            LIMIT ?
            """,
            (today, limit)
        ).fetchall()

        return [dict(row) for row in rows]


def get_all_tracked_sounds() -> list[dict]:
    """Get all tracked sounds with their stats."""
    init_db()

    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                sound, ipa, example_word, first_seen,
                times_encountered, times_practiced, times_correct,
                interval_days, next_review
            FROM sound_tracking
            ORDER BY times_encountered DESC
            """
        ).fetchall()

        return [dict(row) for row in rows]


def update_sound_after_practice(sound: str, was_correct: bool) -> None:
    """
    Update a sound's spaced repetition schedule after practice.

    Uses a simplified SM-2 algorithm:
    - Correct: double the interval (max 30 days)
    - Incorrect: reset interval to 1 day

    Args:
        sound: The sound that was practiced
        was_correct: Whether the user pronounced it correctly
    """
    init_db()

    today = date.today().isoformat()

    with get_db() as db:
        # Get current interval
        row = db.execute(
            "SELECT interval_days, times_practiced, times_correct FROM sound_tracking WHERE sound = ?",
            (sound,)
        ).fetchone()

        if not row:
            return

        current_interval = row["interval_days"]
        times_practiced = row["times_practiced"]
        times_correct = row["times_correct"]

        if was_correct:
            # Double the interval, max 30 days
            new_interval = min(current_interval * 2, 30.0)
            times_correct += 1
        else:
            # Reset to 1 day
            new_interval = 1.0

        times_practiced += 1
        next_review = (date.today() + timedelta(days=new_interval)).isoformat()

        db.execute(
            """
            UPDATE sound_tracking
            SET interval_days = ?,
                next_review = ?,
                last_practiced = ?,
                times_practiced = ?,
                times_correct = ?
            WHERE sound = ?
            """,
            (new_interval, next_review, today, times_practiced, times_correct, sound)
        )


def get_sound_stats() -> dict:
    """
    Get aggregate statistics about tracked sounds.

    Returns:
        Dictionary with sound tracking stats
    """
    init_db()

    today = date.today().isoformat()

    with get_db() as db:
        # Total sounds tracked
        total = db.execute(
            "SELECT COUNT(*) as count FROM sound_tracking"
        ).fetchone()["count"]

        if total == 0:
            return {
                "total_sounds": 0,
                "due_today": 0,
                "mastered": 0,
                "needs_work": 0,
            }

        # Sounds due today
        due = db.execute(
            "SELECT COUNT(*) as count FROM sound_tracking WHERE next_review <= ?",
            (today,)
        ).fetchone()["count"]

        # Mastered sounds (interval >= 14 days)
        mastered = db.execute(
            "SELECT COUNT(*) as count FROM sound_tracking WHERE interval_days >= 14"
        ).fetchone()["count"]

        # Needs work (interval <= 2 days and practiced at least once)
        needs_work = db.execute(
            """
            SELECT COUNT(*) as count FROM sound_tracking
            WHERE interval_days <= 2 AND times_practiced > 0
            """
        ).fetchone()["count"]

        # Most problematic sounds
        problem_sounds = db.execute(
            """
            SELECT sound, ipa, times_encountered, times_correct, times_practiced
            FROM sound_tracking
            WHERE times_practiced > 0
            ORDER BY (CAST(times_correct AS REAL) / times_practiced) ASC
            LIMIT 3
            """
        ).fetchall()

        return {
            "total_sounds": total,
            "due_today": due,
            "mastered": mastered,
            "needs_work": needs_work,
            "problem_sounds": [dict(row) for row in problem_sounds],
        }


# =============================================================================
# Spaced Repetition for Mispronounced Words
# =============================================================================

def track_word(word: str, ipa: str = "", related_sound: str = "") -> None:
    """
    Track a mispronounced word for spaced repetition.

    Args:
        word: The word that was mispronounced (e.g., "strength", "strategic")
        ipa: IPA pronunciation (e.g., "/strɛŋkθ/")
        related_sound: The sound category this relates to (e.g., "th", "consonant cluster")
    """
    init_db()

    # Clean the word - extract just the word if it has IPA
    import re
    clean_word = word.strip().lower()
    # Remove IPA notation if present
    clean_word = re.sub(r'/[^/]+/', '', clean_word).strip()
    # Remove quotes
    clean_word = clean_word.strip('"\'')

    if not clean_word or len(clean_word) < 2:
        return

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    with get_db() as db:
        existing = db.execute(
            "SELECT id, times_mispronounced FROM word_tracking WHERE word = ?",
            (clean_word,)
        ).fetchone()

        if existing:
            db.execute(
                """
                UPDATE word_tracking
                SET times_mispronounced = times_mispronounced + 1,
                    ipa = COALESCE(NULLIF(?, ''), ipa),
                    related_sound = COALESCE(NULLIF(?, ''), related_sound)
                WHERE word = ?
                """,
                (ipa, related_sound, clean_word)
            )
        else:
            db.execute(
                """
                INSERT INTO word_tracking (
                    word, ipa, related_sound, first_seen,
                    times_mispronounced, next_review
                ) VALUES (?, ?, ?, ?, 1, ?)
                """,
                (clean_word, ipa, related_sound, today, tomorrow)
            )


def get_due_words(limit: int = 10) -> list[dict]:
    """
    Get words that are due for review today or earlier.

    Returns:
        List of word dictionaries ordered by priority (most overdue first)
    """
    init_db()

    today = date.today().isoformat()

    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                word, ipa, related_sound, times_mispronounced,
                times_practiced, times_correct, interval_days, next_review
            FROM word_tracking
            WHERE next_review <= ?
            ORDER BY next_review ASC, times_mispronounced DESC
            LIMIT ?
            """,
            (today, limit)
        ).fetchall()

        return [dict(row) for row in rows]


def update_word_after_practice(word: str, was_correct: bool) -> None:
    """
    Update a word's spaced repetition schedule after practice.

    Args:
        word: The word that was practiced
        was_correct: Whether the user pronounced it correctly
    """
    init_db()

    clean_word = word.strip().lower()
    today = date.today().isoformat()

    with get_db() as db:
        row = db.execute(
            "SELECT interval_days, times_practiced, times_correct FROM word_tracking WHERE word = ?",
            (clean_word,)
        ).fetchone()

        if not row:
            return

        current_interval = row["interval_days"]
        times_practiced = row["times_practiced"]
        times_correct = row["times_correct"]

        if was_correct:
            new_interval = min(current_interval * 2, 30.0)
            times_correct += 1
        else:
            new_interval = 1.0

        times_practiced += 1
        next_review = (date.today() + timedelta(days=new_interval)).isoformat()

        db.execute(
            """
            UPDATE word_tracking
            SET interval_days = ?,
                next_review = ?,
                last_practiced = ?,
                times_practiced = ?,
                times_correct = ?
            WHERE word = ?
            """,
            (new_interval, next_review, today, times_practiced, times_correct, clean_word)
        )


def get_word_stats() -> dict:
    """Get aggregate statistics about tracked words."""
    init_db()

    today = date.today().isoformat()

    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) as count FROM word_tracking"
        ).fetchone()["count"]

        if total == 0:
            return {
                "total_words": 0,
                "due_today": 0,
                "mastered": 0,
                "needs_work": 0,
            }

        due = db.execute(
            "SELECT COUNT(*) as count FROM word_tracking WHERE next_review <= ?",
            (today,)
        ).fetchone()["count"]

        mastered = db.execute(
            "SELECT COUNT(*) as count FROM word_tracking WHERE interval_days >= 14"
        ).fetchone()["count"]

        needs_work = db.execute(
            """
            SELECT COUNT(*) as count FROM word_tracking
            WHERE interval_days <= 2 AND times_practiced > 0
            """
        ).fetchone()["count"]

        problem_words = db.execute(
            """
            SELECT word, ipa, times_mispronounced, times_correct, times_practiced
            FROM word_tracking
            WHERE times_mispronounced >= 2
            ORDER BY times_mispronounced DESC
            LIMIT 5
            """
        ).fetchall()

        return {
            "total_words": total,
            "due_today": due,
            "mastered": mastered,
            "needs_work": needs_work,
            "problem_words": [dict(row) for row in problem_words],
        }
