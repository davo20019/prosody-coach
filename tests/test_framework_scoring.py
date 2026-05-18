"""Unit tests for framework_scoring."""

import pytest

from framework_scoring import (
    FrameworkScore,
    ModelAnswer,
    SlotScore,
    build_scoring_prompt,
    compute_overall,
    parse_scoring_response,
    resolve_slot_spans,
    serialize_slot_prosody,
    _build_generation_prompt,
    _build_model_answer_prompt,
    _clean_generated_prompt,
    _parse_model_answer_response,
    _safe_index,
    _safe_int,
)
from frameworks import get_framework


def _star():
    return get_framework("star")


def _make_words(words):
    """Helper: turn [(w, start, end)] into objects with .word, .start_s, .end_s.

    Avoids importing the dataclass; ducktyped objects are enough for tests
    that only exercise resolve_slot_spans / serialize.
    """
    class W:
        def __init__(self, word, s, e):
            self.word = word
            self.start_s = s
            self.end_s = e
    return [W(*w) for w in words]


class _StubTranscript:
    def __init__(self, text, tokens, words):
        self.text = text
        self.tokens = tokens
        self.words = words


def test_safe_int_parses_int_and_falls_back():
    assert _safe_int("3", default=0) == 3
    assert _safe_int("3 stars", default=0) == 3
    assert _safe_int(None, default=2) == 2
    assert _safe_int("NONE", default=5) == 5
    assert _safe_int("not a number", default=7) == 7


def test_safe_index_bounds_check():
    assert _safe_index("5", 10) == 5
    assert _safe_index("11", 10) is None   # out of range
    assert _safe_index("-1", 10) is None
    assert _safe_index("NONE", 10) is None
    assert _safe_index("", 10) is None


def test_build_scoring_prompt_numbers_tokens_and_lists_slots():
    fw = _star()
    tokens = ["Yesterday", "I", "led", "a", "project"]
    prompt = build_scoring_prompt(fw, tokens)
    # Token numbering must appear in the prompt.
    assert "[0] Yesterday" in prompt
    assert "[4] project" in prompt
    # Each slot id should appear with PRESENT/START/END/QUALITY/NOTE keys.
    for slot in fw["slots"]:
        sid = slot["id"]
        assert f"SLOT_{sid}_PRESENT" in prompt
        assert f"SLOT_{sid}_START" in prompt
        assert f"SLOT_{sid}_END" in prompt
        assert f"SLOT_{sid}_QUALITY" in prompt
        assert f"SLOT_{sid}_NOTE" in prompt
    # ESL framing must be in the prompt.
    assert "ESL" in prompt or "non-native" in prompt


def test_build_scoring_prompt_includes_quality_rubric_and_content_strictness():
    """The prompt must anchor the 0-5 QUALITY scale and instruct the model to
    judge content strictly, not just form. Without this, the LLM defaults to
    generous 4-5 scores on vague or tautological answers and the framework
    rates incoherent content as PASS."""
    fw = _star()
    prompt = build_scoring_prompt(fw, ["x"])
    # Anchored rubric: each level 0-5 must be defined.
    for level in ("0:", "1:", "2:", "3:", "4:", "5:"):
        assert level in prompt, f"QUALITY anchor missing: {level}"
    # Content vs form distinction.
    lowered = prompt.lower()
    assert "form" in lowered and "content" in lowered
    # Must name the failure modes the rubric is meant to catch.
    assert "vague" in lowered
    assert "tautological" in lowered or "tautolog" in lowered
    # Coherence check must be present.
    assert "coherence" in lowered or "make sense" in lowered


def test_parse_scoring_response_happy_path():
    fw = _star()
    raw = """\
SLOT_situation_PRESENT: yes
SLOT_situation_START: 0
SLOT_situation_END: 4
SLOT_situation_QUALITY: 4
SLOT_situation_NOTE: clear context.
SLOT_task_PRESENT: yes
SLOT_task_START: 5
SLOT_task_END: 7
SLOT_task_QUALITY: 5
SLOT_task_NOTE: explicit goal.
SLOT_action_PRESENT: partial
SLOT_action_START: 8
SLOT_action_END: 12
SLOT_action_QUALITY: 3
SLOT_action_NOTE: more concrete steps.
SLOT_result_PRESENT: no
SLOT_result_START: NONE
SLOT_result_END: NONE
SLOT_result_QUALITY: 0
SLOT_result_NOTE: missing outcome.
GRAMMAR_NOTES: "I have made" -> "I made" | "realize" -> "delivered"
CULTURAL_NOTE: under-claimed credit.
OVERALL_NOTE: structure was clear but the result is missing.
"""
    score = parse_scoring_response(raw, fw, max_index=12)
    assert score.framework_id == "star"
    assert len(score.slots) == 4
    by_id = {s.slot_id: s for s in score.slots}
    assert by_id["situation"].present == "yes"
    assert by_id["situation"].start_index == 0
    assert by_id["situation"].end_index == 4
    assert by_id["situation"].quality == 4
    assert by_id["action"].present == "partial"
    assert by_id["result"].present == "no"
    # Missing slot's span gets cleared.
    assert by_id["result"].start_index is None
    assert by_id["result"].end_index is None
    assert score.grammar_notes == ['"I have made" -> "I made"', '"realize" -> "delivered"']
    assert "under-claimed" in score.cultural_note
    assert "structure was clear" in score.overall_note


def test_parse_scoring_drops_invalid_spans():
    fw = _star()
    raw = """\
SLOT_situation_PRESENT: yes
SLOT_situation_START: 10
SLOT_situation_END: 5
SLOT_situation_QUALITY: 4
SLOT_situation_NOTE: x
SLOT_task_PRESENT: yes
SLOT_task_START: 99
SLOT_task_END: 100
SLOT_task_QUALITY: 4
SLOT_task_NOTE: x
SLOT_action_PRESENT: yes
SLOT_action_START: 0
SLOT_action_END: 2
SLOT_action_QUALITY: 4
SLOT_action_NOTE: x
SLOT_result_PRESENT: yes
SLOT_result_START: 3
SLOT_result_END: 4
SLOT_result_QUALITY: 4
SLOT_result_NOTE: x
GRAMMAR_NOTES: NONE
CULTURAL_NOTE: NONE
OVERALL_NOTE: ok
"""
    score = parse_scoring_response(raw, fw, max_index=5)
    by_id = {s.slot_id: s for s in score.slots}
    # Inverted span: dropped to None on both ends.
    assert by_id["situation"].start_index is None and by_id["situation"].end_index is None
    # Out-of-range indices: dropped to None.
    assert by_id["task"].start_index is None and by_id["task"].end_index is None
    # Valid spans preserved.
    assert by_id["action"].start_index == 0 and by_id["action"].end_index == 2
    # NONE cultural note normalized to "".
    assert score.cultural_note == ""
    assert score.grammar_notes == []


def test_compute_overall_passes_when_all_present_and_high_quality():
    fw = _star()
    slots = [
        SlotScore(slot_id=s["id"], present="yes", quality=5, note="")
        for s in fw["slots"]
    ]
    score = FrameworkScore(framework_id="star", slots=slots)
    overall, passed = compute_overall(score, fw)
    assert overall == 10.0
    assert passed is True


def test_compute_overall_fails_when_any_slot_missing():
    fw = _star()
    slots = [
        SlotScore(slot_id=s["id"], present="yes", quality=5, note="")
        for s in fw["slots"]
    ]
    # Force the first slot (situation) to missing — doesn't trigger the
    # must_include_metric deduction (which is keyed on the result slot).
    slots[0] = SlotScore(slot_id=slots[0].slot_id, present="no", quality=0, note="")
    score = FrameworkScore(framework_id="star", slots=slots)
    overall, passed = compute_overall(score, fw)
    # Three slots at 5/5 + one at 0/5 = 15/20 = 7.5 → above threshold, but
    # `passed` should still be False because not all slots are present.
    assert overall == 7.5
    assert passed is False


def test_compute_overall_applies_deduction_when_result_slot_weak():
    """STAR has must_include_metric=result. A weak Result slot triggers a 1.0
    deduction even if all slots are present."""
    fw = _star()
    slots = []
    for s in fw["slots"]:
        if s["id"] == "result":
            slots.append(SlotScore(slot_id="result", present="yes", quality=0, note=""))
        else:
            slots.append(SlotScore(slot_id=s["id"], present="yes", quality=5, note=""))
    score = FrameworkScore(framework_id="star", slots=slots)
    overall, passed = compute_overall(score, fw)
    # (5+5+5+0)/20*10 = 7.5; deduct 1.0 → 6.5.
    assert overall == 6.5
    assert passed is False


def test_compute_overall_must_include_metric_deduction():
    fw = _star()
    # Result slot has quality < 4 → 1.0 deduction.
    slots = []
    for s in fw["slots"]:
        if s["id"] == "result":
            slots.append(SlotScore(slot_id="result", present="yes", quality=2, note=""))
        else:
            slots.append(SlotScore(slot_id=s["id"], present="yes", quality=5, note=""))
    score = FrameworkScore(framework_id="star", slots=slots)
    overall, passed = compute_overall(score, fw)
    # (5+5+5+2)/20*10 = 8.5; deduct 1.0 → 7.5.
    assert overall == 7.5
    assert passed is True


def test_resolve_slot_spans_maps_indices_to_audio_time():
    fw = _star()
    words = _make_words([
        ("Yesterday", 0.0, 0.5),
        ("I",         0.5, 0.6),
        ("led",       0.6, 0.9),
        ("a",         0.9, 1.0),
        ("project",   1.0, 1.6),
        ("to",        1.6, 1.8),
        ("save",      1.8, 2.2),
        ("money.",    2.2, 2.8),
    ])
    tokens = [w.word for w in words]
    transcript = _StubTranscript(" ".join(tokens), tokens, words)
    score = FrameworkScore(
        framework_id="star",
        slots=[
            SlotScore(slot_id="situation", present="yes", quality=4, note="",
                      start_index=0, end_index=2),
            SlotScore(slot_id="task", present="yes", quality=4, note="",
                      start_index=3, end_index=4),
            SlotScore(slot_id="action", present="yes", quality=4, note="",
                      start_index=5, end_index=6),
            SlotScore(slot_id="result", present="no", quality=0, note=""),
        ],
    )
    spans = resolve_slot_spans(score, transcript)
    assert spans["situation"] == (0.0, 0.9)
    assert spans["task"] == (0.9, 1.6)
    assert spans["action"] == (1.6, 2.2)
    assert spans["result"] is None


def test_resolve_slot_spans_returns_none_when_no_words():
    fw = _star()
    transcript = _StubTranscript("yesterday I led a project", "yesterday I led a project".split(), [])
    score = FrameworkScore(
        framework_id="star",
        slots=[
            SlotScore(slot_id="situation", present="yes", quality=4, note="",
                      start_index=0, end_index=2),
        ],
    )
    spans = resolve_slot_spans(score, transcript)
    assert spans["situation"] is None


def test_serialize_slot_prosody_handles_none():
    assert serialize_slot_prosody(None) is None


def test_serialize_slot_prosody_uses_correct_field_names():
    """Guards against the analyzer.py field-name landmine (estimated_wpm,
    pvi, pause_count) flagged in code review."""
    class Stub:
        class _T:
            estimated_wpm = 138.0
        class _P:
            mean_hz = 120.0
            min_hz = 80.0
            max_hz = 240.0
        class _V:
            mean_db = 65.0
            stress_contrast_db = 8.0
        class _R:
            pvi = 55.0
            pvi_type = "vocalic"
        class _Pa:
            pause_count = 3
        tempo = _T()
        pitch = _P()
        volume = _V()
        rhythm = _R()
        pauses = _Pa()
        duration = 12.5
        overall_score = 7.8

    out = serialize_slot_prosody(Stub())
    assert out["tempo_wpm"] == 138.0
    assert out["pitch_mean_hz"] == 120.0
    assert out["volume_mean_db"] == 65.0
    assert out["rhythm_pvi"] == 55.0
    assert out["rhythm_pvi_type"] == "vocalic"
    assert out["pause_count"] == 3
    assert out["duration_s"] == 12.5
    assert out["overall"] == 7.8


# --------------------------------------------------------------------------- #
# Prompt generation
# --------------------------------------------------------------------------- #

def test_build_generation_prompt_includes_examples_and_slots():
    fw = _star()
    p = _build_generation_prompt(fw)
    assert "STAR Method" in p
    # Slot names should appear in the structure hint.
    assert "Situation" in p and "Result" in p
    # At least one curated prompt should be present as an in-context example.
    assert fw["prompts"][0]["text"] in p
    # Strict-format instruction must be present so the model doesn't
    # prepend "Here's a prompt:" boilerplate.
    assert "Output ONLY" in p or "Output ONLY the prompt itself" in p


def test_clean_generated_prompt_strips_common_preambles():
    cleaned = _clean_generated_prompt(
        'Here is a prompt: Tell me about a time you led a difficult change.'
    )
    assert cleaned.startswith("Tell me about")
    assert "Here is" not in cleaned


def test_clean_generated_prompt_strips_quotes_and_extra_lines():
    raw = '"Describe a difficult conversation you had with a teammate."\n\nThis would test the SBI structure.'
    cleaned = _clean_generated_prompt(raw)
    # Only the first non-empty line survives; surrounding quotes stripped.
    assert cleaned == 'Describe a difficult conversation you had with a teammate.'


def test_clean_generated_prompt_handles_sure_prefix():
    cleaned = _clean_generated_prompt(
        "Sure! Tell me about a project where you missed an important deadline."
    )
    assert cleaned.startswith("Tell me about")


def test_clean_generated_prompt_rejects_empty_output():
    with pytest.raises(RuntimeError):
        _clean_generated_prompt("")
    with pytest.raises(RuntimeError):
        _clean_generated_prompt("   ")


def test_clean_generated_prompt_rejects_too_short():
    with pytest.raises(RuntimeError):
        _clean_generated_prompt("Talk?")  # 5 chars; below the floor


def test_clean_generated_prompt_rejects_too_long():
    long_text = "A" * 500
    with pytest.raises(RuntimeError):
        _clean_generated_prompt(long_text)


# --------------------------------------------------------------------------- #
# Model-answer generation
# --------------------------------------------------------------------------- #

def test_build_model_answer_prompt_grounds_in_transcript_and_framework():
    fw = _star()
    transcript = "I led a project for a government client and it went well."
    prompt = "Tell me about a time you led a difficult project."
    p = _build_model_answer_prompt(fw, transcript, prompt)
    # The framework's name and the practice prompt must appear so the model
    # rewrites in the right form and topic.
    assert "STAR Method" in p
    assert prompt in p
    assert transcript in p
    # Each slot must have an explicit output line so the parser can locate it.
    for slot in fw["slots"]:
        assert f"SLOT_{slot['id']}_TEXT" in p
    # Must explicitly tell the model to stay in the learner's reachable register
    # (otherwise it drifts to native idiom and the gap feels unattainable).
    lowered = p.lower()
    assert "esl" in lowered or "non-native" in lowered


def test_parse_model_answer_response_returns_slots_in_framework_order():
    fw = _star()
    # Intentionally emit slots out of order to verify the parser reorders.
    raw = """\
SLOT_result_TEXT: The client launched on time and we cut churn by 18%.
SLOT_situation_TEXT: Our government client needed a faster permits portal.
SLOT_action_TEXT: I scoped three approaches, picked GraphQL, and led the rollout.
SLOT_task_TEXT: My job was to redesign the architecture in six weeks.
"""
    answer = _parse_model_answer_response(raw, fw)
    assert isinstance(answer, ModelAnswer)
    assert [s[0] for s in answer.slots] == ["situation", "task", "action", "result"]
    # Each entry is (slot_id, slot_name, text).
    by_id = {s[0]: s for s in answer.slots}
    assert by_id["situation"][1] == "Situation"
    assert by_id["situation"][2].startswith("Our government client")
    assert "18%" in by_id["result"][2]


def test_parse_model_answer_rejects_missing_or_empty_slot():
    fw = _star()
    # Action slot's text is whitespace-only — must raise.
    raw = """\
SLOT_situation_TEXT: A real situation.
SLOT_task_TEXT: A real task.
SLOT_action_TEXT:
SLOT_result_TEXT: A real result.
"""
    with pytest.raises(RuntimeError):
        _parse_model_answer_response(raw, fw)


def test_parse_model_answer_rejects_response_with_no_slots():
    fw = _star()
    with pytest.raises(RuntimeError):
        _parse_model_answer_response("Sorry, I cannot help with that.", fw)
