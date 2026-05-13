import subprocess
from pathlib import Path

import pytest
import soundfile as sf


def _make_silence_webm(path: Path) -> None:
    """Create a 1s silent webm/opus file with ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
            "-t", "1", "-c:a", "libopus", str(path),
        ],
        check=True, capture_output=True,
    )


def test_transcode_to_wav_produces_16k_mono(tmp_path):
    src = tmp_path / "in.webm"
    _make_silence_webm(src)

    from web.audio_io import transcode_to_wav
    dst = transcode_to_wav(src, tmp_path / "out.wav")

    assert dst.exists()
    data, sr = sf.read(dst)
    assert sr == 16000
    assert data.ndim == 1  # mono
    assert len(data) > 0


def test_transcode_writes_atomically_via_tmp_file(tmp_path):
    src = tmp_path / "in.webm"
    _make_silence_webm(src)
    from web.audio_io import transcode_to_wav
    dst = transcode_to_wav(src, tmp_path / "out.wav")
    assert not (tmp_path / "out.wav.tmp").exists()
    assert dst.exists()


def test_transcode_raises_on_invalid_input(tmp_path):
    bad = tmp_path / "bogus.webm"
    bad.write_bytes(b"not actually webm")
    from web.audio_io import transcode_to_wav, TranscodeError
    with pytest.raises(TranscodeError):
        transcode_to_wav(bad, tmp_path / "out.wav")
