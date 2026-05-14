# Content Feedback and Polished Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render LLM content feedback (clarity / conciseness / tone), grammar fixes, and a polished version of free-speech recordings on the `/practice` results card.

**Architecture:** Extend the existing Gemini coach prompt with one new `CONTENT_FEEDBACK:` section, parse it into a new optional `content_feedback` dict on `CoachingResult`, persist as JSON in a new `sessions.content_feedback` column, and render a "Content" partial in `analysis_card.html` gated on `mode == "analyze"`. The existing `suggested_revision` and `grammar_issues` (already produced and stored but never displayed) get rendered in the same partial.

**Tech Stack:** Python, FastAPI, Jinja2, SQLite, Google Gemini, pytest.

**Spec:** `docs/superpowers/specs/2026-05-14-content-feedback-and-polished-revision-design.md`

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `coach.py` | Modify | Add `CONTENT_FEEDBACK` section to both standalone + with-prosody prompts; add `content_feedback` field on `CoachingResult`; add `_parse_content_feedback` helper; wire into `parse_coaching_response` |
| `coach_pipeline.py` | Modify | Surface `content_feedback` in `_normalize_coaching` output |
| `storage.py` | Modify | Add `content_feedback` column to `SESSION_COLUMN_DEFINITIONS`; accept + serialize the field in `save_session`; JSON-decode it in `get_session` |
| `web/routes/practice.py` | Modify | Pass `content_feedback` to `save_session`; pass `mode`, `grammar_issues`, `suggested_revision`, `content_feedback` to the analysis card template |
| `web/templates/partials/content_feedback.html` | Create | New partial — renders critique rows, grammar fixes, polished version |
| `web/templates/partials/analysis_card.html` | Modify | Include the new partial when `mode == "analyze"` and any of the three blocks have data |
| `tests/test_content_feedback_parser.py` | Create | Unit-test `_parse_content_feedback` and `parse_coaching_response` integration |
| `tests/web/test_coach_pipeline.py` | Modify | Assert `_normalize_coaching` exposes `content_feedback` |
| `tests/web/test_routes_practice.py` | Modify | Two end-to-end render assertions (analyze mode shows, practice mode hides) |
| `tests/test_storage_content_feedback.py` | Create | Round-trip the column through `save_session` / `get_session` |

---

## Task 1: Add `content_feedback` field to `CoachingResult`

**Files:**
- Modify: `coach.py` (the `CoachingResult` dataclass around line 41-57)

- [ ] **Step 1: Open `coach.py` and locate the `CoachingResult` dataclass.**

The dataclass currently ends with `ai_prosody: dict = None` around line 57. The new field goes immediately after, before the closing of the dataclass.

- [ ] **Step 2: Add the `content_feedback` field**

Edit `coach.py` to add a new optional attribute after `ai_prosody`:

```python
@dataclass
class CoachingResult:
    """Results from AI coaching analysis."""
    transcript: str
    grammar_issues: list[dict]
    suggested_revision: str
    coaching_tips: list[str]
    overall_feedback: str
    confidence_score: int = 0
    confidence_feedback: str = ""
    filler_word_count: int = 0
    filler_words_detail: str = ""
    pronunciation_issues: list[dict] = None
    fluency_score: int = 0
    fluency_feedback: str = ""
    ai_prosody: dict = None
    # NEW: content critique (clarity/conciseness/tone) + revision rationale.
    # None when reading a fixed prompt or when the model omitted the section.
    content_feedback: Optional[dict] = None
```

If `Optional` isn't imported in `coach.py`, add `from typing import Optional` to the existing imports block at the top of the file (search for `from typing import` — if it exists, append `Optional` to its import list; otherwise add a new import line).

- [ ] **Step 3: Verify the file still imports**

Run: `python -c "import coach; print(coach.CoachingResult)"`
Expected: prints `<class 'coach.CoachingResult'>` with no traceback.

- [ ] **Step 4: Commit**

```bash
git add coach.py
git commit -m "Add content_feedback field to CoachingResult"
```

---

## Task 2: Implement `_parse_content_feedback` (TDD — failing test first)

**Files:**
- Create: `tests/test_content_feedback_parser.py`
- Modify: `coach.py` (new helper function near `parse_coaching_response` around line 647)

- [ ] **Step 1: Write the failing test file**

Create `tests/test_content_feedback_parser.py` with:

```python
"""Tests for _parse_content_feedback — the CONTENT_FEEDBACK section parser.

The parser must:
  * Return None for empty input or the literal "None".
  * Parse CLARITY/CONCISENESS/TONE lines into {"score": int, "note": str}.
  * Parse RATIONALE into "revision_rationale" (str).
  * Skip malformed lines without raising.
  * Clamp scores to 1..10.
  * Return None when nothing valid was parsed (so the UI gate stays simple).
"""

import pytest

from coach import _parse_content_feedback


def test_returns_none_for_empty_string():
    assert _parse_content_feedback("") is None


def test_returns_none_for_whitespace():
    assert _parse_content_feedback("   \n\n  ") is None


def test_returns_none_for_literal_none():
    assert _parse_content_feedback("None") is None
    assert _parse_content_feedback("none") is None
    assert _parse_content_feedback("  None  \n") is None


def test_parses_all_four_lines():
    text = (
        "CLARITY: 8 | easy to follow\n"
        "CONCISENESS: 6 | hedges and filler\n"
        "TONE: 7 | a bit casual for a meeting\n"
        "RATIONALE: trims hedges and fixes subject/verb agreement"
    )
    result = _parse_content_feedback(text)
    assert result == {
        "clarity": {"score": 8, "note": "easy to follow"},
        "conciseness": {"score": 6, "note": "hedges and filler"},
        "tone": {"score": 7, "note": "a bit casual for a meeting"},
        "revision_rationale": "trims hedges and fixes subject/verb agreement",
    }


def test_clamps_score_above_10():
    text = "CLARITY: 12 | clear"
    result = _parse_content_feedback(text)
    assert result == {"clarity": {"score": 10, "note": "clear"}}


def test_clamps_score_below_1():
    text = "CLARITY: 0 | nope"
    result = _parse_content_feedback(text)
    assert result == {"clarity": {"score": 1, "note": "nope"}}


def test_missing_rationale_returns_other_entries():
    text = (
        "CLARITY: 8 | good\n"
        "CONCISENESS: 6 | padding\n"
        "TONE: 7 | fine"
    )
    result = _parse_content_feedback(text)
    assert "revision_rationale" not in result
    assert result["clarity"] == {"score": 8, "note": "good"}
    assert result["tone"] == {"score": 7, "note": "fine"}


def test_malformed_line_is_skipped():
    text = (
        "CLARITY: 8 | good\n"
        "this line has no pipe\n"
        "CONCISENESS not a colon\n"
        "TONE: 7 | fine"
    )
    result = _parse_content_feedback(text)
    assert result == {
        "clarity": {"score": 8, "note": "good"},
        "tone": {"score": 7, "note": "fine"},
    }


def test_case_insensitive_keys():
    text = "clarity: 8 | good\nRationale: nicer wording"
    result = _parse_content_feedback(text)
    assert result["clarity"] == {"score": 8, "note": "good"}
    assert result["revision_rationale"] == "nicer wording"


def test_returns_none_when_no_lines_match():
    text = "junk\nmore junk"
    assert _parse_content_feedback(text) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_content_feedback_parser.py -v`
Expected: ImportError or `AttributeError: module 'coach' has no attribute '_parse_content_feedback'` — every test errors at import.

- [ ] **Step 3: Implement `_parse_content_feedback` in `coach.py`**

Locate the `parse_coaching_response` function (around line 647). Add this helper *above* `parse_coaching_response`:

```python
import re as _re_cf  # local alias to keep imports near use; `re` is already imported at top

_CONTENT_FEEDBACK_LINE = _re_cf.compile(
    r"^\s*(CLARITY|CONCISENESS|TONE)\s*:\s*(\d+)\s*\|\s*(.+?)\s*$",
    _re_cf.IGNORECASE,
)
_RATIONALE_LINE = _re_cf.compile(
    r"^\s*RATIONALE\s*:\s*(.+?)\s*$",
    _re_cf.IGNORECASE,
)


def _parse_content_feedback(text: str) -> Optional[dict]:
    """Parse the CONTENT_FEEDBACK section into a dict (or None).

    Recognized lines:
      CLARITY: <score> | <note>
      CONCISENESS: <score> | <note>
      TONE: <score> | <note>
      RATIONALE: <single-line text>

    Returns None for empty input, the literal "None", or when nothing valid
    parses. Scores are clamped to 1..10. Unrecognized lines are silently
    dropped (forward-compatible).
    """
    if not text:
        return None
    stripped = text.strip()
    if not stripped or stripped.lower() == "none":
        return None

    result: dict = {}
    for raw_line in stripped.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        m = _CONTENT_FEEDBACK_LINE.match(line)
        if m:
            key = m.group(1).lower()
            score = max(1, min(10, int(m.group(2))))
            note = m.group(3).strip()
            result[key] = {"score": score, "note": note}
            continue
        r = _RATIONALE_LINE.match(line)
        if r:
            result["revision_rationale"] = r.group(1).strip()

    return result or None
```

Note: `coach.py` already imports `re` at the top of the file; the local `_re_cf` alias above keeps the helper grouped, but if you prefer, replace `_re_cf` with the existing module-level `re` and remove the local import line — both work.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_content_feedback_parser.py -v`
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add coach.py tests/test_content_feedback_parser.py
git commit -m "Add _parse_content_feedback helper with regex-based parsing"
```

---

## Task 3: Wire `_parse_content_feedback` into `parse_coaching_response`

**Files:**
- Modify: `coach.py` (`parse_coaching_response` around line 647-865)
- Modify: `tests/test_content_feedback_parser.py` (add integration test)

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_content_feedback_parser.py`:

```python
def test_parse_coaching_response_populates_content_feedback():
    from coach import parse_coaching_response

    response = """
TRANSCRIPT:
I think we should probably wait.

GRAMMAR_ISSUES:
None

SUGGESTED_REVISION:
Let's wait.

CONTENT_FEEDBACK:
CLARITY: 8 | clear point
CONCISENESS: 5 | "probably" hedges the recommendation
TONE: 7 | fine for casual contexts
RATIONALE: removes hedge, makes the recommendation direct

COACHING_TIPS:
- Project more confidence.

VOCAL_CONFIDENCE:
6 | some hedging

FILLER_WORDS:
0 | None detected

PRONUNCIATION_ISSUES:
None - pronunciation was clear

FLUENCY:
8 | smooth

AI_PROSODY:
- PITCH: 7/10 | natural

OVERALL:
Good clarity, soften the hedging.
"""

    result = parse_coaching_response(response)
    assert result.content_feedback == {
        "clarity": {"score": 8, "note": "clear point"},
        "conciseness": {"score": 5, "note": '"probably" hedges the recommendation'},
        "tone": {"score": 7, "note": "fine for casual contexts"},
        "revision_rationale": "removes hedge, makes the recommendation direct",
    }


def test_parse_coaching_response_content_feedback_none_when_section_absent():
    from coach import parse_coaching_response

    response = """
TRANSCRIPT:
hi.

GRAMMAR_ISSUES:
None

SUGGESTED_REVISION:
hi.

COACHING_TIPS:
- ok

VOCAL_CONFIDENCE:
7 | ok

FILLER_WORDS:
0 | None

PRONUNCIATION_ISSUES:
None - pronunciation was clear

FLUENCY:
7 | smooth

AI_PROSODY:
- PITCH: 7/10 | ok

OVERALL:
ok
"""

    result = parse_coaching_response(response)
    assert result.content_feedback is None


def test_parse_coaching_response_content_feedback_literal_none():
    from coach import parse_coaching_response

    response = """
TRANSCRIPT:
abc.

GRAMMAR_ISSUES:
None

SUGGESTED_REVISION:
abc.

CONTENT_FEEDBACK:
None

COACHING_TIPS:
- ok

VOCAL_CONFIDENCE:
7 | ok

FILLER_WORDS:
0 | None

PRONUNCIATION_ISSUES:
None - pronunciation was clear

FLUENCY:
7 | smooth

AI_PROSODY:
- PITCH: 7/10 | ok

OVERALL:
ok
"""

    result = parse_coaching_response(response)
    assert result.content_feedback is None
```

- [ ] **Step 2: Run the integration tests to verify they fail**

Run: `pytest tests/test_content_feedback_parser.py::test_parse_coaching_response_populates_content_feedback -v`
Expected: FAIL. Either `content_feedback` is missing as a constructor arg, or the section key is missing from the sections dict.

- [ ] **Step 3: Add `CONTENT_FEEDBACK:` to the `sections` dict and pass to `CoachingResult`**

In `coach.py` `parse_coaching_response` (around line 649), update the `sections` initializer to include the new key:

```python
sections = {
    "TRANSCRIPT:": "",
    "GRAMMAR_ISSUES:": "",
    "SUGGESTED_REVISION:": "",
    "CONTENT_FEEDBACK:": "",
    "COACHING_TIPS:": "",
    "VOCAL_CONFIDENCE:": "",
    "FILLER_WORDS:": "",
    "PRONUNCIATION_ISSUES:": "",
    "FLUENCY:": "",
    "AI_PROSODY:": "",
    "OVERALL:": "",
}
```

Then in the final `return CoachingResult(...)` (around line 851), add the new field:

```python
return CoachingResult(
    transcript=sections["TRANSCRIPT:"].strip(),
    grammar_issues=grammar_issues,
    suggested_revision=sections["SUGGESTED_REVISION:"].strip(),
    coaching_tips=coaching_tips[:5],
    overall_feedback=sections["OVERALL:"].strip(),
    confidence_score=confidence_score,
    confidence_feedback=confidence_feedback,
    filler_word_count=filler_word_count,
    filler_words_detail=filler_words_detail,
    pronunciation_issues=pronunciation_issues,
    fluency_score=fluency_score,
    fluency_feedback=fluency_feedback,
    ai_prosody=ai_prosody if ai_prosody else None,
    content_feedback=_parse_content_feedback(sections["CONTENT_FEEDBACK:"]),
)
```

- [ ] **Step 4: Run all parser tests to verify they pass**

Run: `pytest tests/test_content_feedback_parser.py tests/test_review_fixes.py::test_parse_pronunciation_issue_separates_example_from_ipa -v`
Expected: all PASS. The existing pronunciation parser test must still pass — proves we didn't regress the sections-dict ordering.

- [ ] **Step 5: Commit**

```bash
git add coach.py tests/test_content_feedback_parser.py
git commit -m "Wire CONTENT_FEEDBACK section into parse_coaching_response"
```

---

## Task 4: Add `CONTENT_FEEDBACK` to the LLM prompts

**Files:**
- Modify: `coach.py` — three prompt builders:
  - `build_coaching_prompt` (around line 419)
  - `build_coaching_prompt_standalone` (around line 497)
  - `build_practice_prompt` (around line 336)

- [ ] **Step 1: Add CONTENT_FEEDBACK to `build_coaching_prompt`**

In `coach.py`, find `build_coaching_prompt` (around line 419). After the `SUGGESTED_REVISION:` block and *before* the `COACHING_TIPS:` block, insert:

```
CONTENT_FEEDBACK:
[Critique the *content* of what was said, independent of pronunciation/prosody.]
[If the speaker was reading a fixed prompt (not their own words), write: None]
[Otherwise output each line exactly:]
CLARITY: <1-10> | <one sentence: is the idea easy to follow?>
CONCISENESS: <1-10> | <one sentence: any padding, repetition, or rambling?>
TONE: <1-10> | <one sentence: register/tone appropriate? too stiff/too casual?>
RATIONALE: <one sentence on why your SUGGESTED_REVISION is an improvement>

```

(Mind the trailing blank line so the next section header stays on its own line.)

- [ ] **Step 2: Add CONTENT_FEEDBACK to `build_coaching_prompt_standalone`**

Same insertion in `build_coaching_prompt_standalone` (around line 497) between `SUGGESTED_REVISION:` and `COACHING_TIPS:`.

- [ ] **Step 3: Add CONTENT_FEEDBACK to `build_practice_prompt`**

In `build_practice_prompt` (around line 336) the SUGGESTED_REVISION block tells the model what to do when the user read the text correctly. Add the same CONTENT_FEEDBACK block between `SUGGESTED_REVISION:` and `COACHING_TIPS:` — but the "fixed prompt" cue means the model should return `None` here in normal operation. The block is added for prompt symmetry so all three prompts produce parseable output even if a future tweak makes the model emit critique anyway.

- [ ] **Step 4: Sanity-check the prompts compile**

Run:

```bash
python -c "
from coach import build_coaching_prompt_standalone, build_practice_prompt
import types, dataclasses
fake = types.SimpleNamespace(
    pitch=types.SimpleNamespace(score=8, feedback='p'),
    volume=types.SimpleNamespace(score=8, feedback='v'),
    tempo=types.SimpleNamespace(score=8, estimated_wpm=140, feedback='t'),
    rhythm=types.SimpleNamespace(score=8, pvi=55, feedback='r'),
    pauses=types.SimpleNamespace(score=8, feedback='pa'),
)
print('CONTENT_FEEDBACK:' in build_coaching_prompt_standalone())
print('CONTENT_FEEDBACK:' in build_practice_prompt(fake, 'hello'))
"
```

Expected: prints `True` twice.

- [ ] **Step 5: Run the full parser test suite again — prompts must not break parsing**

Run: `pytest tests/test_content_feedback_parser.py tests/test_review_fixes.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add coach.py
git commit -m "Add CONTENT_FEEDBACK section to coach prompts"
```

---

## Task 5: Surface `content_feedback` through the pipeline

**Files:**
- Modify: `coach_pipeline.py` (`_normalize_coaching` around line 73)
- Modify: `tests/web/test_coach_pipeline.py`

- [ ] **Step 1: Write the failing pipeline test**

Append to `tests/web/test_coach_pipeline.py`:

```python
def test_normalize_coaching_surfaces_content_feedback():
    """A CoachingResult.content_feedback dict should propagate into the flat coach dict."""
    from coach import CoachingResult
    from coach_pipeline import _normalize_coaching

    cr = CoachingResult(
        transcript="t",
        grammar_issues=[],
        suggested_revision="rev",
        coaching_tips=["tip"],
        overall_feedback="ok",
        content_feedback={
            "clarity": {"score": 8, "note": "good"},
            "revision_rationale": "tighter phrasing",
        },
    )
    out = _normalize_coaching(cr)
    assert out["content_feedback"] == {
        "clarity": {"score": 8, "note": "good"},
        "revision_rationale": "tighter phrasing",
    }


def test_normalize_coaching_defaults_content_feedback_to_none():
    """When the coach didn't populate the field, dict value is None (not missing)."""
    from coach import CoachingResult
    from coach_pipeline import _normalize_coaching

    cr = CoachingResult(
        transcript="t",
        grammar_issues=[],
        suggested_revision="rev",
        coaching_tips=[],
        overall_feedback="",
    )
    out = _normalize_coaching(cr)
    assert "content_feedback" in out
    assert out["content_feedback"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/web/test_coach_pipeline.py::test_normalize_coaching_surfaces_content_feedback -v`
Expected: FAIL — the key `"content_feedback"` is not in the returned dict.

- [ ] **Step 3: Add the key to `_normalize_coaching`**

In `coach_pipeline.py`, locate `_normalize_coaching` (around line 73-97). Add one new line inside the returned dict (alongside the other `getattr(...)` lines), conventionally placed after `suggested_revision`:

```python
return {
    "transcript": getattr(coaching, "transcript", None),
    "tips": list(getattr(coaching, "coaching_tips", []) or []),
    "summary": getattr(coaching, "overall_feedback", None),
    "grammar_issues": list(getattr(coaching, "grammar_issues", []) or []),
    "suggested_revision": getattr(coaching, "suggested_revision", None),
    "content_feedback": getattr(coaching, "content_feedback", None),
    "confidence_score": getattr(coaching, "confidence_score", None),
    "confidence_feedback": getattr(coaching, "confidence_feedback", None),
    "filler_word_count": getattr(coaching, "filler_word_count", None),
    "filler_words_detail": getattr(coaching, "filler_words_detail", None),
    "pronunciation_issues": list(getattr(coaching, "pronunciation_issues", []) or []),
    "fluency_score": getattr(coaching, "fluency_score", None),
    "fluency_feedback": getattr(coaching, "fluency_feedback", None),
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/web/test_coach_pipeline.py -v`
Expected: all tests PASS (the two new tests plus all existing tests in the file).

- [ ] **Step 5: Commit**

```bash
git add coach_pipeline.py tests/web/test_coach_pipeline.py
git commit -m "Surface content_feedback through coach pipeline"
```

---

## Task 6: Add `content_feedback` to storage

**Files:**
- Modify: `storage.py` (column definitions around line 12-46; `save_session` around line 314-460; `get_session` JSON-decode logic around line 616)
- Create: `tests/test_storage_content_feedback.py`

- [ ] **Step 1: Write the failing round-trip test**

Create `tests/test_storage_content_feedback.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_storage_content_feedback.py -v`
Expected: every test FAILS — column doesn't exist; `save_session` doesn't accept the kwarg.

- [ ] **Step 3: Add the column to `SESSION_COLUMN_DEFINITIONS`**

In `storage.py` (around line 12-46), add one entry inside the `SESSION_COLUMN_DEFINITIONS` dict — conventionally placed near the other coach text fields, right after `"suggested_revision": "TEXT"`:

```python
SESSION_COLUMN_DEFINITIONS = {
    # ... existing entries unchanged ...
    "grammar_issues": "TEXT",
    "suggested_revision": "TEXT",
    "content_feedback": "TEXT",
    "confidence_score": "INTEGER",
    # ... rest unchanged ...
}
```

The existing `_ensure_sessions_schema` automatically `ALTER TABLE ADD COLUMN`s any missing entry on next `init_db()`, so old DBs migrate transparently.

- [ ] **Step 4: Update `save_session` to accept and persist the field**

In `storage.py` `save_session` (around line 314):

1. Add the new parameter to the signature (alphabetically/logically grouped is fine; place it after `suggested_revision`):

```python
def save_session(
    analysis,
    mode: str = "analyze",
    prompt_id: Optional[str] = None,
    recording_path: Optional[str | Path] = None,
    transcript: Optional[str] = None,
    ai_summary: Optional[str] = None,
    ai_tips: Optional[list[str]] = None,
    grammar_issues: Optional[list[dict]] = None,
    suggested_revision: Optional[str] = None,
    content_feedback: Optional[dict] = None,
    confidence_score: Optional[int] = None,
    # ... rest unchanged ...
) -> int:
```

2. In the body, JSON-encode it next to the other `*_json` variables (around line 365):

```python
grammar_json = json.dumps(grammar_issues) if grammar_issues else None
content_feedback_json = json.dumps(content_feedback) if content_feedback else None
pron_json = json.dumps(pronunciation_issues) if pronunciation_issues else None
```

3. Add `content_feedback` to the INSERT column list and parameter tuple (around lines 377-425). The column list currently reads `... grammar_issues, suggested_revision, confidence_score, ...`. Update:

```python
            INSERT INTO sessions (
                created_at, duration, pitch_score, volume_score,
                tempo_score, rhythm_score, pause_score, overall_score,
                mode, prompt_id, transcript, recording_path,
                pitch_feedback, volume_feedback, tempo_feedback,
                rhythm_feedback, pause_feedback,
                ai_summary, ai_tips,
                grammar_issues, suggested_revision, content_feedback,
                confidence_score, confidence_feedback,
                filler_word_count, filler_words_detail,
                pronunciation_issues, fluency_score, fluency_feedback,
                coach_provider, coach_status, coach_error,
                framework_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

That's 33 placeholders (was 32). And in the value tuple, insert `content_feedback_json` right after `suggested_revision`:

```python
            (
                datetime.now().isoformat(),
                data["duration"],
                data["pitch_score"],
                data["volume_score"],
                data["tempo_score"],
                data["rhythm_score"],
                data["pause_score"],
                overall_score_value,
                mode,
                prompt_id,
                transcript,
                str(recording_path) if recording_path else None,
                analysis.pitch.feedback,
                analysis.volume.feedback,
                analysis.tempo.feedback,
                analysis.rhythm.feedback,
                analysis.pauses.feedback,
                ai_summary,
                tips_json,
                grammar_json,
                suggested_revision,
                content_feedback_json,
                confidence_score,
                confidence_feedback,
                filler_word_count,
                filler_words_detail,
                pron_json,
                fluency_score,
                fluency_feedback,
                coach_provider,
                coach_status,
                coach_error,
                framework_data_json,
            ),
```

Count placeholders against values to be safe — both must be 33.

- [ ] **Step 5: Update `get_session` to JSON-decode the column**

In `storage.py`, locate `get_session` (search for `def get_session`). Around line 616 there's existing logic that JSON-decodes `grammar_issues`:

```python
if result.get("grammar_issues"):
    result["grammar_issues"] = json.loads(result["grammar_issues"])
```

Add an analogous decode for `content_feedback`. Default to `None` (not the raw JSON string) when missing:

```python
if result.get("content_feedback"):
    result["content_feedback"] = json.loads(result["content_feedback"])
else:
    result["content_feedback"] = None
```

If the existing pattern just leaves missing values as the raw column value (typically `None`), follow that same pattern — keep behavior consistent with `grammar_issues`. Look at the surrounding code and mirror it. If `grammar_issues` decode is wrapped in `if result.get(...)` only, do the same.

- [ ] **Step 6: Run the storage tests to verify they pass**

Run: `pytest tests/test_storage_content_feedback.py -v`
Expected: all 3 tests PASS.

Then run the broader storage / review-fixes test surface to confirm no regression:

Run: `pytest tests/test_review_fixes.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add storage.py tests/test_storage_content_feedback.py
git commit -m "Persist content_feedback as JSON column on sessions"
```

---

## Task 7: Wire route to save and render `content_feedback`

**Files:**
- Modify: `web/routes/practice.py` (`analyze` POST handler around line 137-238)
- Modify: `tests/web/test_routes_practice.py`

- [ ] **Step 1: Write the failing route test**

Append to `tests/web/test_routes_practice.py`:

```python
def _fake_pipeline_result_with_content():
    """Pipeline result that includes grammar fixes, suggested revision, and content critique."""
    analysis = SimpleNamespace(
        pitch=SimpleNamespace(score=8, feedback="good pitch"),
        volume=SimpleNamespace(score=7, feedback="good volume"),
        tempo=SimpleNamespace(score=9, estimated_wpm=140, feedback="good tempo"),
        rhythm=SimpleNamespace(score=6, pvi=55, feedback="ok rhythm"),
        pauses=SimpleNamespace(score=8, feedback="good pauses"),
        to_dict=lambda: {
            "duration": 5.0, "pitch_score": 8, "volume_score": 7,
            "tempo_score": 9, "rhythm_score": 6, "pause_score": 8,
            "overall_score": 7.6,
        },
    )
    coach = {
        "transcript": "I think we should probably wait",
        "tips": ["pace yourself"],
        "summary": "nice",
        "grammar_issues": [
            {"original": "he don't", "corrected": "he doesn't", "explanation": "subject/verb agreement"}
        ],
        "suggested_revision": "Let's wait until tomorrow.",
        "content_feedback": {
            "clarity": {"score": 8, "note": "easy to follow"},
            "conciseness": {"score": 5, "note": "hedge words pad the request"},
            "tone": {"score": 7, "note": "casual but fine"},
            "revision_rationale": "trims hedges and tightens the recommendation",
        },
    }
    from coach_pipeline import SessionResult
    return SessionResult(
        analysis=analysis, coach=coach,
        provider="gemini", status="ok", error=None,
    )


def test_analyze_renders_content_feedback_block_in_analyze_mode(client, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.practice.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    monkeypatch.setattr(
        "web.routes.practice.analyze_session",
        lambda *a, **k: _fake_pipeline_result_with_content(),
    )
    saved = []
    monkeypatch.setattr(
        "web.routes.practice.save_session",
        lambda *a, **k: (saved.append(k), 42)[1],
    )

    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )

    assert response.status_code == 200
    # Content block rendered
    assert "Polished version" in response.text
    assert "Let&#39;s wait until tomorrow." in response.text or "Let's wait until tomorrow." in response.text
    assert "trims hedges" in response.text
    # Critique row
    assert "Clarity" in response.text
    assert "easy to follow" in response.text
    # Grammar fix
    assert "he doesn&#39;t" in response.text or "he doesn't" in response.text
    # And the route saved the field
    assert saved and saved[0]["content_feedback"] == {
        "clarity": {"score": 8, "note": "easy to follow"},
        "conciseness": {"score": 5, "note": "hedge words pad the request"},
        "tone": {"score": 7, "note": "casual but fine"},
        "revision_rationale": "trims hedges and tightens the recommendation",
    }


def test_analyze_hides_content_block_in_practice_mode(client, tmp_path, monkeypatch):
    """Even if the LLM populated content_feedback, practice (fixed-prompt) mode hides it."""
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.practice.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    monkeypatch.setattr(
        "web.routes.practice.analyze_session",
        lambda *a, **k: _fake_pipeline_result_with_content(),
    )
    monkeypatch.setattr("web.routes.practice.save_session", lambda *a, **k: 42)

    response = client.post(
        "/practice/analyze",
        data={"mode": "practice", "expected_text": "Let's wait until tomorrow."},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )

    assert response.status_code == 200
    assert "Polished version" not in response.text
    assert "trims hedges" not in response.text
```

- [ ] **Step 2: Run the route tests to verify they fail**

Run: `pytest tests/web/test_routes_practice.py::test_analyze_renders_content_feedback_block_in_analyze_mode tests/web/test_routes_practice.py::test_analyze_hides_content_block_in_practice_mode -v`
Expected: both FAIL — route doesn't pass the new context yet; template doesn't render the block; `saved[0]["content_feedback"]` KeyErrors.

- [ ] **Step 3: Update the route to save and render the new field**

In `web/routes/practice.py` `analyze` (around line 137-238):

(a) Pass `content_feedback` to `save_session`. In the `save_session(...)` call near line 193, add the new kwarg right after `suggested_revision`:

```python
sid = save_session(
    result.analysis,
    mode=mode,
    prompt_id=prompt_id,
    recording_path=str(wav_path),
    transcript=coach.get("transcript"),
    ai_summary=coach.get("summary"),
    ai_tips=coach.get("tips"),
    grammar_issues=coach.get("grammar_issues"),
    suggested_revision=coach.get("suggested_revision"),
    content_feedback=coach.get("content_feedback"),
    confidence_score=coach.get("confidence_score"),
    confidence_feedback=coach.get("confidence_feedback"),
    filler_word_count=coach.get("filler_word_count"),
    filler_words_detail=coach.get("filler_words_detail"),
    pronunciation_issues=coach.get("pronunciation_issues"),
    fluency_score=coach.get("fluency_score"),
    fluency_feedback=coach.get("fluency_feedback"),
    coach_provider=result.provider,
    coach_status=result.status,
    coach_error=result.error,
)
```

(b) Add the new context keys to the `TemplateResponse` at the end of the function (around line 227-238):

```python
return templates.TemplateResponse(
    request,
    "partials/analysis_card.html",
    {
        "analysis": result.analysis,
        "coach": result.coach,
        "provider": result.provider,
        "error": result.error,
        "recording_name": recording_name,
        "session_id": sid,
        "mode": mode,
        "grammar_issues": (coach or {}).get("grammar_issues") or [],
        "suggested_revision": (coach or {}).get("suggested_revision"),
        "content_feedback": (coach or {}).get("content_feedback"),
    },
)
```

The `(coach or {})` guards against the failed-coach path where `result.coach is None`.

- [ ] **Step 4: Build the partial template (next task creates it; this one just wires the route)**

This step has no edit — proceed to Task 8 to build the template, then come back and run the tests.

- [ ] **Step 5: Commit (route wiring only)**

```bash
git add web/routes/practice.py tests/web/test_routes_practice.py
git commit -m "Wire content_feedback through /practice/analyze route"
```

Note: the two new route tests will still FAIL at this checkpoint because the template partial doesn't exist yet. That's expected — they pass after Task 8.

---

## Task 8: Build the `content_feedback` partial and include it from `analysis_card.html`

**Files:**
- Create: `web/templates/partials/content_feedback.html`
- Modify: `web/templates/partials/analysis_card.html`

- [ ] **Step 1: Create the partial**

Create `web/templates/partials/content_feedback.html` with:

```jinja
{# Content feedback for free-speech (analyze mode) practice.
   Rendered only when at least one of: content_feedback, grammar_issues, suggested_revision
   is populated and mode == "analyze". Each sub-block hides itself if its data is missing. #}
<div class="content-feedback">
  <h4>Content</h4>

  {% if content_feedback and (content_feedback.clarity or content_feedback.conciseness or content_feedback.tone) %}
    <table class="content-critique">
      <tbody>
        {% if content_feedback.clarity %}
          <tr>
            <th scope="row">Clarity</th>
            <td>{{ content_feedback.clarity.score }}/10</td>
            <td>{{ content_feedback.clarity.note }}</td>
          </tr>
        {% endif %}
        {% if content_feedback.conciseness %}
          <tr>
            <th scope="row">Conciseness</th>
            <td>{{ content_feedback.conciseness.score }}/10</td>
            <td>{{ content_feedback.conciseness.note }}</td>
          </tr>
        {% endif %}
        {% if content_feedback.tone %}
          <tr>
            <th scope="row">Tone</th>
            <td>{{ content_feedback.tone.score }}/10</td>
            <td>{{ content_feedback.tone.note }}</td>
          </tr>
        {% endif %}
      </tbody>
    </table>
  {% endif %}

  {% if grammar_issues %}
    <div class="grammar-fixes">
      <h5>Grammar fixes</h5>
      <ul>
        {% for issue in grammar_issues %}
          <li>
            <span class="mark-bad">{{ issue.original }}</span>
            <span class="arrow">&rarr;</span>
            <span class="mark-good">{{ issue.corrected }}</span>
            {% if issue.explanation %}
              <div class="explanation muted">{{ issue.explanation }}</div>
            {% endif %}
          </li>
        {% endfor %}
      </ul>
    </div>
  {% endif %}

  {% if suggested_revision %}
    <div class="polished-version">
      <h5>Polished version</h5>
      <p class="polished-text">&ldquo;{{ suggested_revision }}&rdquo;</p>
      {% if content_feedback and content_feedback.revision_rationale %}
        <p class="muted polished-rationale"><em>Why:</em> {{ content_feedback.revision_rationale }}</p>
      {% endif %}
    </div>
  {% endif %}
</div>
```

- [ ] **Step 2: Include the partial from `analysis_card.html`**

Edit `web/templates/partials/analysis_card.html`. Currently the file (37 lines) has:
- the results header
- the prosody metrics include
- the AI coach block (or the warning banner)
- the optional `<audio>` element
- the result-actions row

Insert the new include between the AI coach block and the audio element. The exact change is to add the `{% if ... %}{% include ... %}{% endif %}` block right after the closing `{% endif %}` of the coach block (which sits right above `{% if recording_name %}` around line 25):

```jinja
  {% if mode == "analyze" and (content_feedback or grammar_issues or suggested_revision) %}
    {% include "partials/content_feedback.html" %}
  {% endif %}

  {% if recording_name %}
    <audio controls src="/audio/{{ recording_name }}"></audio>
  {% endif %}
```

- [ ] **Step 3: Run the route tests — they should now PASS**

Run: `pytest tests/web/test_routes_practice.py -v`
Expected: all PASS, including the two new tests added in Task 7.

- [ ] **Step 4: Manual smoke-check in a browser**

In another terminal, start the dev server (use whatever launch script `main.py` defines — typically `python main.py` or `uvicorn web.app:app --port 7860`). Then in a browser:

1. Open `http://127.0.0.1:7860/practice`.
2. *Without* clicking a prompt link (so `prompt` is `None` and the textarea is shown), type a sentence like "I think we should probably maybe wait until tomorrow" into the textarea, record, and submit.
3. Wait for the results card. Confirm a "Content" block appears with critique rows, optional grammar fixes, and the "Polished version" section.
4. Click "Practice this prompt again" or navigate back, then click any prompt to go into practice mode. Record again. Confirm the Content block does *not* appear (mode=practice gates it out).

If the styles look unstyled (no spacing / no monospace alignment), that's fine for first cut — the unstyled HTML is functional. Styling can be a follow-up.

- [ ] **Step 5: Commit**

```bash
git add web/templates/partials/content_feedback.html web/templates/partials/analysis_card.html
git commit -m "Render content feedback partial on /practice analysis card"
```

---

## Task 9: Light styling for the new partial

**Files:**
- Modify: `web/static/app.css`

- [ ] **Step 1: Locate the analysis card / coach block styles**

In `web/static/app.css`, search for existing `.coach` or `.card` class rules to anchor the new styles next to them.

- [ ] **Step 2: Add minimal styles**

Append these rules (or splice them next to `.coach`):

```css
.content-feedback {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border, #eee);
}
.content-feedback h4 {
  margin: 0 0 .5rem 0;
}
.content-critique {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: .75rem;
}
.content-critique th,
.content-critique td {
  text-align: left;
  padding: .25rem .5rem;
  vertical-align: top;
}
.content-critique th {
  width: 10rem;
  color: var(--ink-2, #555);
  font-weight: 500;
}
.content-critique td:nth-child(2) {
  width: 4rem;
  color: var(--ink-2, #555);
  font-variant-numeric: tabular-nums;
}
.grammar-fixes ul {
  list-style: none;
  padding-left: 0;
  margin: .25rem 0 .75rem;
}
.grammar-fixes li {
  margin-bottom: .5rem;
}
.grammar-fixes .mark-bad {
  text-decoration: line-through;
  color: var(--apricot, #b06)
}
.grammar-fixes .mark-good {
  font-weight: 600;
}
.grammar-fixes .arrow {
  margin: 0 .35rem;
  color: var(--ink-3, #888);
}
.grammar-fixes .explanation {
  font-size: .9em;
}
.polished-version .polished-text {
  font-style: italic;
  margin: .25rem 0 .25rem 0;
}
.polished-rationale {
  font-size: .9em;
}
```

If the project's CSS variables differ (`--apricot`, `--ink-2`, etc.), fall back to literal hex — the codebase already uses some token names per `app.css`; mirror what exists.

- [ ] **Step 3: Reload the page and visually confirm**

Refresh the practice results card. Confirm the critique table is aligned and the polished-version block reads cleanly.

- [ ] **Step 4: Commit**

```bash
git add web/static/app.css
git commit -m "Style content feedback partial"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest -x`
Expected: all tests PASS. If anything fails, fix in place — do not skip.

- [ ] **Step 2: Re-run the new tests in isolation, with `-v`**

Run:

```bash
pytest tests/test_content_feedback_parser.py \
       tests/test_storage_content_feedback.py \
       tests/web/test_coach_pipeline.py \
       tests/web/test_routes_practice.py -v
```

Expected: all PASS.

- [ ] **Step 3: Confirm no migration issue against a pre-existing DB**

If there's a `data/prosody.db` already on disk from a prior session, the next `init_db()` should add the new column without error:

```bash
python -c "import storage; storage.init_db(); import sqlite3; \
  print([r[1] for r in sqlite3.connect(storage.DB_PATH).execute('PRAGMA table_info(sessions)')])"
```

Expected: the list includes `content_feedback`.

- [ ] **Step 4: Manual end-to-end smoke**

Launch the dev server, go through one analyze-mode recording with custom text, confirm the Content block renders with at least one of: critique rows, grammar fixes, or polished version + rationale. Submit one practice-mode prompt recording, confirm the Content block is absent.

- [ ] **Step 5: Final commit if any cleanups**

If you made styling or small fixes during smoke-test, commit them. Otherwise nothing to do.

---

## Done criteria

- New tests across `tests/test_content_feedback_parser.py`, `tests/test_storage_content_feedback.py`, `tests/web/test_coach_pipeline.py`, `tests/web/test_routes_practice.py` all pass.
- Existing tests still pass.
- `sessions.content_feedback` column exists; round-trips a dict.
- /practice analyze-mode response renders Content block when LLM populates it; practice-mode response hides it.
- `_normalize_coaching` always includes the `content_feedback` key (value may be `None`).
