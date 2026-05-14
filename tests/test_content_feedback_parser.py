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
