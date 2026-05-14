from types import SimpleNamespace

import numpy as np
import pytest


@pytest.fixture
def fake_audio():
    sr = 16000
    return np.zeros(sr, dtype=np.float32), sr


def _patch_analyzer(monkeypatch):
    fake = SimpleNamespace(
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
    monkeypatch.setattr("coach_pipeline.analyze_prosody", lambda *a, **k: fake)
    return fake


def test_gemini_provider_returns_session_result(monkeypatch, fake_audio):
    audio, sr = fake_audio
    fake_analysis = _patch_analyzer(monkeypatch)
    monkeypatch.setattr(
        "coach_pipeline._run_gemini",
        lambda audio, sr, analysis, **k: {"transcript": "hello", "tips": ["pace"], "summary": "ok"},
    )
    import coach_pipeline
    result = coach_pipeline.analyze_session(
        audio, sr, expected_text=None, mode="analyze",
        provider="gemini", audio_path=None,
    )
    assert result.analysis is fake_analysis
    assert result.coach["transcript"] == "hello"
    assert result.provider == "gemini"
    assert result.status == "ok"
    assert result.error is None


def test_local_provider_dispatches_to_local_path(monkeypatch, fake_audio):
    audio, sr = fake_audio
    _patch_analyzer(monkeypatch)
    monkeypatch.setattr(
        "coach_pipeline._run_local",
        lambda audio, sr, analysis, **k: {"transcript": "world", "tips": [], "summary": "ok"},
    )
    import coach_pipeline
    result = coach_pipeline.analyze_session(
        audio, sr, expected_text=None, mode="analyze",
        provider="local", audio_path=None,
    )
    assert result.coach["transcript"] == "world"
    assert result.provider == "local"
    assert result.status == "ok"


def test_coach_failure_returns_partial_result(monkeypatch, fake_audio):
    audio, sr = fake_audio
    _patch_analyzer(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("API down")
    monkeypatch.setattr("coach_pipeline._run_gemini", boom)

    import coach_pipeline
    result = coach_pipeline.analyze_session(
        audio, sr, expected_text=None, mode="analyze",
        provider="gemini", audio_path=None,
    )
    assert result.analysis is not None
    assert result.coach is None
    assert result.status == "failed"
    assert "API down" in result.error


def test_unknown_provider_raises(fake_audio, monkeypatch):
    audio, sr = fake_audio
    _patch_analyzer(monkeypatch)
    import coach_pipeline
    with pytest.raises(ValueError):
        coach_pipeline.analyze_session(
            audio, sr, expected_text=None, mode="analyze",
            provider="bogus", audio_path=None,
        )


# --------------------------------------------------------------------------- #
# Framework session model-answer integration
# --------------------------------------------------------------------------- #

def _patch_framework_pipeline(monkeypatch, *, score_value=8.5):
    """Stub the parts of analyze_framework_session below model_answer.

    Keeps the test focused on whether model-answer failures are swallowed.
    """
    _patch_analyzer(monkeypatch)
    transcript = SimpleNamespace(text="I led a project.", tokens=["I", "led"], words=[])
    monkeypatch.setattr(
        "coach_pipeline._get_transcript_for_framework",
        lambda *a, **k: transcript,
    )
    monkeypatch.setattr(
        "framework_scoring.score_framework",
        lambda framework, transcript, provider: SimpleNamespace(
            slots=[], grammar_notes=[], cultural_note="", overall_note="",
        ),
    )
    monkeypatch.setattr(
        "framework_scoring.compute_overall",
        lambda structure, framework: (score_value, True),
    )
    return transcript


def test_framework_session_attaches_model_answer_on_success(monkeypatch, fake_audio):
    audio, sr = fake_audio
    _patch_framework_pipeline(monkeypatch)
    from framework_scoring import ModelAnswer
    expected = ModelAnswer(slots=[("situation", "Situation", "rewritten text")])
    monkeypatch.setattr(
        "framework_scoring.generate_model_answer",
        lambda *a, **k: expected,
    )

    import coach_pipeline
    result = coach_pipeline.analyze_framework_session(
        audio, sr,
        framework={"id": "star", "name": "STAR", "slots": []},
        prompt={"id": "star_1", "text": "Tell me about a time…"},
        provider="local", audio_path=None,
    )
    assert result.status == "ok"
    assert result.model_answer is expected


def test_framework_session_swallows_model_answer_failure(monkeypatch, fake_audio):
    """A model-answer generation failure must NOT invalidate the scoring
    result the learner just earned. The result still returns status='ok' with
    model_answer=None."""
    audio, sr = fake_audio
    _patch_framework_pipeline(monkeypatch)

    def _boom(*a, **k):
        raise RuntimeError("LLM unreachable")
    monkeypatch.setattr("framework_scoring.generate_model_answer", _boom)

    import coach_pipeline
    result = coach_pipeline.analyze_framework_session(
        audio, sr,
        framework={"id": "star", "name": "STAR", "slots": []},
        prompt={"id": "star_1", "text": "Tell me about a time…"},
        provider="local", audio_path=None,
    )
    assert result.status == "ok"
    assert result.overall_score == 8.5
    assert result.model_answer is None


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
