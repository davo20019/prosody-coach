from pathlib import Path
from uuid import uuid4

import pytest
import soundfile as sf
import numpy as np


@pytest.fixture
def recordings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("web.routes.audio.RECORDINGS_DIR", tmp_path)
    return tmp_path


def _write_silent_wav(path: Path) -> None:
    sf.write(path, np.zeros(16000, dtype=np.int16), 16000, subtype="PCM_16")


def test_returns_wav_for_known_uuid(client, recordings_dir):
    name = f"{uuid4().hex}.wav"
    _write_silent_wav(recordings_dir / name)
    response = client.get(f"/audio/{name}")
    assert response.status_code == 200
    assert response.headers["content-type"] in ("audio/wav", "audio/x-wav")


def test_returns_404_for_unknown_uuid(client, recordings_dir):
    response = client.get(f"/audio/{uuid4().hex}.wav")
    assert response.status_code == 404


def test_rejects_path_traversal(client, recordings_dir):
    response = client.get("/audio/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in (400, 404)
