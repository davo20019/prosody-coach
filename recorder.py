"""Audio recording module for capturing speech from microphone."""

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import threading
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from rich.live import Live
from rich.text import Text

from config import SAMPLE_RATE, CHANNELS, RECORDINGS_DIR


def record_audio(
    duration: Optional[float] = None,
    stop_on_enter: bool = True
) -> Tuple[np.ndarray, int]:
    """
    Record audio from the default microphone.

    Args:
        duration: Maximum recording duration in seconds. If None, records until Enter.
        stop_on_enter: If True, stops recording when user presses Enter.

    Returns:
        Tuple of (audio_data as numpy array, sample_rate)
    """
    if stop_on_enter and duration is None:
        return _record_until_enter()
    else:
        return _record_fixed_duration(duration or 10.0)


def _record_until_enter() -> Tuple[np.ndarray, int]:
    """Record until user presses Enter with live animation."""
    audio_chunks = []
    recording = True
    stop_event = threading.Event()

    def callback(indata, frames, time, status):
        if recording:
            audio_chunks.append(indata.copy())

    def wait_for_enter():
        """Wait for Enter key in a separate thread."""
        input()
        stop_event.set()

    # Animation frames for recording indicator
    frames = ["⬤", "◯"]

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.float32,
        callback=callback
    ):
        # Start thread to wait for Enter
        enter_thread = threading.Thread(target=wait_for_enter, daemon=True)
        enter_thread.start()

        # Show animated recording indicator
        frame_idx = 0
        with Live(refresh_per_second=2, transient=True) as live:
            while not stop_event.is_set():
                indicator = frames[frame_idx % len(frames)]
                elapsed = len(audio_chunks) * 1024 / SAMPLE_RATE  # Approximate
                text = Text()
                text.append(f"  {indicator} ", style="bold red")
                text.append("Recording", style="bold red")
                text.append(f"  {elapsed:.1f}s", style="dim")
                live.update(text)
                frame_idx += 1
                stop_event.wait(0.5)

        recording = False

    if audio_chunks:
        audio_data = np.concatenate(audio_chunks, axis=0)
        return audio_data.flatten(), SAMPLE_RATE
    else:
        return np.array([]), SAMPLE_RATE


def _record_fixed_duration(duration: float) -> Tuple[np.ndarray, int]:
    """Record for a fixed duration."""
    frames = int(duration * SAMPLE_RATE)
    audio_data = sd.rec(
        frames,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.float32
    )
    sd.wait()
    return audio_data.flatten(), SAMPLE_RATE


def save_recording(
    audio_data: np.ndarray,
    sample_rate: int,
    filename: Optional[str] = None
) -> Path:
    """
    Save recorded audio to a WAV file.

    Args:
        audio_data: Audio data as numpy array
        sample_rate: Sample rate in Hz
        filename: Optional filename, defaults to timestamp

    Returns:
        Path to saved file
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"

    filepath = RECORDINGS_DIR / filename

    # Convert to 16-bit PCM for WAV file
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wav.write(filepath, sample_rate, audio_int16)

    return filepath


def load_audio(filepath: Path) -> Tuple[np.ndarray, int]:
    """
    Load audio from a WAV file.

    Args:
        filepath: Path to WAV file

    Returns:
        Tuple of (audio_data as numpy array, sample_rate)
    """
    sample_rate, audio_data = wav.read(filepath)

    # Convert to float32 normalized to [-1, 1]
    if audio_data.dtype == np.int16:
        audio_data = audio_data.astype(np.float32) / 32767
    elif audio_data.dtype == np.int32:
        audio_data = audio_data.astype(np.float32) / 2147483647

    # Convert stereo to mono if needed
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)

    return audio_data, sample_rate


def get_duration(audio_data: np.ndarray, sample_rate: int) -> float:
    """Get duration of audio in seconds."""
    return len(audio_data) / sample_rate


def play_audio(audio_data: np.ndarray, sample_rate: int) -> None:
    """
    Play audio through the default output device.

    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate in Hz
    """
    sd.play(audio_data, sample_rate)
    sd.wait()  # Wait until playback is finished
