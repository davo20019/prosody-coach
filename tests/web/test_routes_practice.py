def test_get_practice_renders_form(client):
    response = client.get("/practice")
    assert response.status_code == 200
    body = response.text
    assert 'data-recorder' in body
    assert 'data-record' in body  # the button
    assert '/practice/analyze' in body  # the form action
    assert 'id="result-region"' in body


def test_root_redirects_to_practice(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/practice"


def test_practice_with_prompt_id_loads_prompt_text(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.practice.get_prompt_by_id",
        lambda pid: {"id": pid, "text": "The quick brown fox", "category": "stress"} if pid == "p1" else None,
    )
    response = client.get("/practice?prompt_id=p1")
    assert response.status_code == 200
    assert "The quick brown fox" in response.text


def test_practice_with_unknown_prompt_id_renders_blank(client, monkeypatch):
    monkeypatch.setattr("web.routes.practice.get_prompt_by_id", lambda pid: None)
    response = client.get("/practice?prompt_id=nope")
    assert response.status_code == 200
    assert "nope" not in response.text  # no leak of the bogus id as content


def test_practice_renders_tips_drawer(client):
    """Spec parity: prosody tips content is available on the Practice page."""
    response = client.get("/practice")
    assert response.status_code == 200
    assert "Tips for Spanish speakers" in response.text
    assert "schwa" in response.text.lower()
    assert "<details" in response.text  # collapsible


import io
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import soundfile as sf


def _fake_pipeline_result():
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
    coach = {"transcript": "hello world", "tips": ["pace yourself"], "summary": "nice"}
    from coach_pipeline import SessionResult
    return SessionResult(
        analysis=analysis, coach=coach,
        provider="gemini", status="ok", error=None,
    )


def test_analyze_returns_rendered_card(client, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.practice.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    monkeypatch.setattr(
        "web.routes.practice.analyze_session",
        lambda *a, **k: _fake_pipeline_result(),
    )
    saved = []
    monkeypatch.setattr(
        "web.routes.practice.save_session",
        lambda *a, **k: (saved.append(k), 42)[1],
    )

    fake_webm = b"\x1a\x45\xdf\xa3"  # webm magic; transcode is mocked anyway
    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(fake_webm), "audio/webm")},
    )
    assert response.status_code == 200
    assert "good pitch" in response.text
    assert "hello world" in response.text
    assert "via gemini" in response.text
    assert saved and saved[0]["coach_provider"] == "gemini"
    assert saved[0]["coach_status"] == "ok"


def test_analyze_renders_partial_when_coach_fails(client, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.practice.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    from coach_pipeline import SessionResult
    failed = SessionResult(
        analysis=_fake_pipeline_result().analysis,
        coach=None, provider="gemini",
        status="failed", error="API down",
    )
    monkeypatch.setattr("web.routes.practice.analyze_session", lambda *a, **k: failed)
    monkeypatch.setattr("web.routes.practice.save_session", lambda *a, **k: 7)

    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert "AI coaching unavailable" in response.text
    assert "API down" in response.text


def test_analyze_returns_error_banner_on_transcode_failure(client, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    from web.audio_io import TranscodeError

    def boom(src, dst):
        raise TranscodeError("ffmpeg missing")
    monkeypatch.setattr("web.routes.practice.transcode_to_wav", boom)

    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(b""), "audio/webm")},
    )
    assert response.status_code == 200
    assert "Audio could not be processed" in response.text
    assert "prosody local doctor" in response.text


def test_analyze_returns_error_banner_when_praat_fails(client, tmp_path, monkeypatch):
    """Praat (analyze_prosody) failure must render an error banner, not 500."""
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.practice.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    def boom(*a, **k):
        raise RuntimeError("Sound is too short for analysis")
    monkeypatch.setattr("web.routes.practice.analyze_session", boom)

    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert "Audio analysis failed" in response.text
    assert "Sound is too short" in response.text
