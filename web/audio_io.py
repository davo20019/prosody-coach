"""Audio I/O helpers for the web layer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class TranscodeError(RuntimeError):
    """Raised when ffmpeg fails to convert browser audio to WAV."""


def transcode_to_wav(src: Path, dst: Path, *, sample_rate: int = 16000) -> Path:
    """Transcode an arbitrary audio file (typically webm/opus) to mono 16-bit WAV.

    Writes atomically: ffmpeg outputs to dst.with_suffix('.tmp'), then renames.
    Raises TranscodeError on ffmpeg failure or invalid input.
    """
    src = Path(src)
    dst = Path(dst)
    tmp = dst.with_name(dst.name + ".tmp")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(src),
                "-ac", "1",                # mono
                "-ar", str(sample_rate),   # 16 kHz
                "-sample_fmt", "s16",      # 16-bit PCM
                "-f", "wav",               # force container — tmp filename ends in .tmp, ffmpeg can't infer
                str(tmp),
            ],
            check=True, capture_output=True,
        )
    except FileNotFoundError as exc:
        raise TranscodeError("ffmpeg binary not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        if tmp.exists():
            tmp.unlink()
        raise TranscodeError(
            f"ffmpeg failed (exit {exc.returncode}): {exc.stderr.decode(errors='replace')[:500]}"
        ) from exc

    shutil.move(str(tmp), str(dst))
    return dst
