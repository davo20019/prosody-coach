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


def test_analyze_advances_due_word_when_practiced_correctly(client, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.practice.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    monkeypatch.setattr(
        "web.routes.practice.analyze_session",
        lambda *a, **k: _fake_pipeline_result(),
    )
    monkeypatch.setattr("web.routes.practice.save_session", lambda *a, **k: 42)
    monkeypatch.setattr(
        "web.routes.practice.get_due_words",
        lambda limit=100: [{"word": "thought", "ipa": "θɔːt", "related_sound": "th"}],
    )
    updates = []
    monkeypatch.setattr(
        "web.routes.practice.update_word_after_practice",
        lambda word, was_correct: updates.append((word, was_correct)),
    )

    response = client.post(
        "/practice/analyze",
        data={"mode": "practice", "expected_text": "I thought about it."},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )

    assert response.status_code == 200
    assert updates == [("thought", True)]


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


def test_analyze_does_not_advance_due_words_when_coach_fails(client, tmp_path, monkeypatch):
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
    monkeypatch.setattr(
        "web.routes.practice.get_due_words",
        lambda limit=100: [{"word": "thought", "ipa": "θɔːt", "related_sound": "th"}],
    )
    updates = []
    monkeypatch.setattr(
        "web.routes.practice.update_word_after_practice",
        lambda word, was_correct: updates.append((word, was_correct)),
    )

    response = client.post(
        "/practice/analyze",
        data={"mode": "practice", "expected_text": "I thought about it."},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )

    assert response.status_code == 200
    assert updates == []


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


def test_analyze_card_links_to_followup_when_coach_ok(client, tmp_path, monkeypatch):
    """Practice POST should render the 'Try a sentence targeting this' button
    pointing at /practice/followup/<id> when the coach succeeded."""
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(
        "web.routes.practice.transcode_to_wav",
        lambda src, dst: (sf.write(dst, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16") or dst),
    )
    monkeypatch.setattr(
        "web.routes.practice.analyze_session",
        lambda *a, **k: _fake_pipeline_result(),
    )
    monkeypatch.setattr("web.routes.practice.save_session", lambda *a, **k: 17)

    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert "/practice/followup/17" in response.text
    assert "Try a sentence targeting this" in response.text


def test_analyze_card_omits_followup_when_coach_failed(client, tmp_path, monkeypatch):
    """No followup button when AI coaching failed — there's no AI weakness data
    to generate a tailored prompt from."""
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
    monkeypatch.setattr("web.routes.practice.save_session", lambda *a, **k: 9)

    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(b"\x1a\x45\xdf\xa3"), "audio/webm")},
    )
    assert response.status_code == 200
    assert "/practice/followup/9" not in response.text
    assert "Try a sentence targeting this" not in response.text


def test_followup_generates_tailored_prompt_from_session(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.practice.get_session",
        lambda sid: {
            "id": sid,
            "pitch_score": 9, "volume_score": 9, "tempo_score": 9,
            "rhythm_score": 4,  # weakest
            "pause_score": 8,
            "pronunciation_issues": [{"sound": "th", "example": "the", "ipa": "/ð/", "tip": "voiced"}],
        } if sid == 42 else None,
    )
    captured = {}
    def fake_gen(weaknesses, due_sounds=None, due_words=None):
        captured["weaknesses"] = weaknesses
        return {"id": "followup-42", "text": "The thoughtful thinker thanked them.", "key_sounds": "th"}
    monkeypatch.setattr("web.routes.practice.generate_tailored_prompt", fake_gen)

    response = client.get("/practice/followup/42")
    assert response.status_code == 200
    assert "The thoughtful thinker thanked them." in response.text
    # Synthesized weaknesses should include rhythm (lowest score) as a prosody focus
    focus_areas = captured["weaknesses"]["focus_areas"]
    prosody_areas = [f["area"] for f in focus_areas if f["type"] == "prosody"]
    assert "rhythm" in prosody_areas
    # And the pronunciation issue should be surfaced
    pron_sounds = [f["sound"] for f in focus_areas if f["type"] == "pronunciation"]
    assert "th" in pron_sounds


def test_followup_404_for_unknown_session(client, monkeypatch):
    monkeypatch.setattr("web.routes.practice.get_session", lambda sid: None)
    response = client.get("/practice/followup/999")
    assert response.status_code == 404


def test_followup_falls_back_to_random_on_generation_failure(client, monkeypatch):
    monkeypatch.setattr(
        "web.routes.practice.get_session",
        lambda sid: {
            "id": sid, "pitch_score": 5, "volume_score": 5, "tempo_score": 5,
            "rhythm_score": 5, "pause_score": 5, "pronunciation_issues": None,
        },
    )
    def boom(*a, **k):
        raise RuntimeError("no api key")
    monkeypatch.setattr("web.routes.practice.generate_tailored_prompt", boom)
    monkeypatch.setattr(
        "web.routes.practice.get_random_prompt",
        lambda *a, **k: {"id": "rand", "text": "Fallback sentence to read.", "category": "stress"},
    )
    response = client.get("/practice/followup/1")
    assert response.status_code == 200
    assert "Fallback sentence to read." in response.text
    assert "Tailored generation unavailable" in response.text
