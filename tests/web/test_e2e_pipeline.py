"""End-to-end: real ffmpeg transcode + real Praat analysis + mocked AI coach."""

import io
import subprocess
from pathlib import Path

import pytest


FIXTURE_WAV = Path(__file__).parent / "fixtures" / "short_silence.wav"


@pytest.fixture
def webm_blob(tmp_path):
    """Convert the WAV fixture to webm/opus (what the browser would send)."""
    out = tmp_path / "rec.webm"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(FIXTURE_WAV), "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )
    return out.read_bytes()


def test_full_pipeline_records_session(client, webm_blob, tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.practice.RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr("storage.DB_PATH", tmp_path / "p.db")

    # Force the gemini path regardless of the developer's local .env. The
    # route imports COACH_PROVIDER at module load, so we patch the imported
    # name (not the config module) — that's the symbol the route reads.
    monkeypatch.setattr("web.routes.practice.COACH_PROVIDER", "gemini")

    # Mock only the AI coach — real Praat runs. Signature must match the real
    # _run_gemini (audio, sample_rate, analysis, **kwargs).
    monkeypatch.setattr(
        "coach_pipeline._run_gemini",
        lambda audio, sr, analysis, **k: {
            "transcript": "(silence)", "tips": [], "summary": "no speech detected",
        },
    )

    captured_kwargs = []
    real_save = __import__("storage").save_session
    def wrapped_save(*a, **k):
        captured_kwargs.append(k)
        return real_save(*a, **k)
    monkeypatch.setattr("web.routes.practice.save_session", wrapped_save)

    response = client.post(
        "/practice/analyze",
        data={"mode": "analyze"},
        files={"audio": ("rec.webm", io.BytesIO(webm_blob), "audio/webm")},
    )
    assert response.status_code == 200
    assert "Component" in response.text  # analysis_card rendered
    assert captured_kwargs, "save_session was not called"
    assert captured_kwargs[0]["coach_provider"] in ("gemini", "local")
    assert captured_kwargs[0]["coach_status"] == "ok"
