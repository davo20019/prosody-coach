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
