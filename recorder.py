"""Audio recording module for capturing speech from microphone."""

import asyncio
import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import sys
import io
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, AsyncGenerator

from rich.live import Live
from rich.text import Text

from config import SAMPLE_RATE, CHANNELS, RECORDINGS_DIR, REALTIME_AUDIO_CHUNK_MS


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
    """Record until user presses Enter or silence detected (VAD)."""
    import webrtcvad
    import time as time_module

    # VAD settings
    VAD_SAMPLE_RATE = 16000  # webrtcvad requires 8000, 16000, 32000, or 48000
    VAD_FRAME_MS = 20  # Frame size in ms (10, 20, or 30) - 20ms works with 1024 blocksize after resampling
    VAD_FRAME_SIZE = int(VAD_SAMPLE_RATE * VAD_FRAME_MS / 1000)  # 320 samples
    SILENCE_THRESHOLD = 2.5  # Seconds of silence before auto-stop
    MIN_SPEECH_DURATION = 0.5  # Minimum speech before allowing auto-stop

    audio_chunks = []
    recording = True
    stop_event = threading.Event()

    # VAD state
    vad = webrtcvad.Vad(2)  # Aggressiveness 0-3 (2 is balanced)
    speech_detected = False
    speech_start_time = None
    last_speech_time = None

    def callback(indata, frames, time, status):
        nonlocal speech_detected, speech_start_time, last_speech_time

        if not recording:
            return

        audio_chunks.append(indata.copy())

        # Convert to 16-bit PCM for VAD
        audio_float = indata.flatten()

        # Resample to VAD_SAMPLE_RATE using scipy
        if SAMPLE_RATE != VAD_SAMPLE_RATE:
            from scipy import signal
            num_samples = int(len(audio_float) * VAD_SAMPLE_RATE / SAMPLE_RATE)
            audio_resampled = signal.resample(audio_float, num_samples)
        else:
            audio_resampled = audio_float

        audio_16bit = (audio_resampled * 32767).astype(np.int16)

        # Check VAD on 30ms frames
        if len(audio_16bit) >= VAD_FRAME_SIZE:
            frame = audio_16bit[:VAD_FRAME_SIZE].tobytes()
            try:
                is_speech = vad.is_speech(frame, VAD_SAMPLE_RATE)
                if is_speech:
                    if not speech_detected:
                        speech_detected = True
                        speech_start_time = time_module.time()
                    last_speech_time = time_module.time()
            except Exception:
                pass  # Ignore VAD errors

    def wait_for_enter():
        """Wait for Enter key in a separate thread."""
        input()
        stop_event.set()

    def check_silence():
        """Check if we should auto-stop due to silence."""
        nonlocal recording
        while not stop_event.is_set():
            if speech_detected and last_speech_time:
                speech_duration = last_speech_time - speech_start_time if speech_start_time else 0
                silence_duration = time_module.time() - last_speech_time

                # Auto-stop if enough silence after sufficient speech
                if speech_duration >= MIN_SPEECH_DURATION and silence_duration >= SILENCE_THRESHOLD:
                    stop_event.set()
                    break
            time_module.sleep(0.1)

    # Animation frames
    anim_frames = ["⬤", "◯"]

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.float32,
        callback=callback,
        blocksize=1024
    ):
        # Start threads
        enter_thread = threading.Thread(target=wait_for_enter, daemon=True)
        enter_thread.start()

        silence_thread = threading.Thread(target=check_silence, daemon=True)
        silence_thread.start()

        # Show animated recording indicator
        frame_idx = 0
        with Live(refresh_per_second=4, transient=True) as live:
            while not stop_event.is_set():
                indicator = anim_frames[frame_idx % len(anim_frames)]
                elapsed = len(audio_chunks) * 1024 / SAMPLE_RATE

                text = Text()
                text.append(f"  {indicator} ", style="bold red")
                text.append("Recording", style="bold red")
                text.append(f"  {elapsed:.1f}s", style="dim")

                # Show speech detection status
                if speech_detected:
                    text.append("  [speaking]", style="green")
                else:
                    text.append("  [waiting...]", style="dim")

                live.update(text)
                frame_idx += 1
                stop_event.wait(0.25)

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
    Save recorded audio to a FLAC file (compressed, lossless).

    Args:
        audio_data: Audio data as numpy array
        sample_rate: Sample rate in Hz
        filename: Optional filename, defaults to timestamp

    Returns:
        Path to saved file
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.flac"

    filepath = RECORDINGS_DIR / filename

    # Save as FLAC (lossless compression, ~50-60% smaller than WAV)
    sf.write(filepath, audio_data, sample_rate, format='flac')

    return filepath


def load_audio(filepath: Path) -> Tuple[np.ndarray, int]:
    """
    Load audio from any supported format (FLAC, WAV, MP3, OGG, etc.).

    Args:
        filepath: Path to audio file

    Returns:
        Tuple of (audio_data as numpy array, sample_rate)
    """
    # soundfile handles FLAC, WAV, OGG, and more
    audio_data, sample_rate = sf.read(filepath, dtype='float32')

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


def play_tts(text: str, slow: bool = False) -> bool:
    """
    Generate and play text-to-speech audio.

    Args:
        text: Text to speak
        slow: If True, speak more slowly

    Returns:
        True if successful, False if TTS unavailable
    """
    try:
        from gtts import gTTS
        from pydub import AudioSegment
    except ImportError:
        # Try using pydub for mp3 playback, fall back to temp file
        pass

    try:
        from gtts import gTTS

        # Generate TTS audio
        tts = gTTS(text=text, lang='en', slow=slow)

        # Save to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name
            tts.save(temp_path)

        # Try to play with pydub (handles mp3)
        try:
            from pydub import AudioSegment
            from pydub.playback import play
            audio = AudioSegment.from_mp3(temp_path)
            play(audio)
        except ImportError:
            # Fallback: convert mp3 to wav and play with sounddevice
            import subprocess
            wav_path = temp_path.replace(".mp3", ".wav")
            # Use ffmpeg if available, otherwise try afplay on macOS
            try:
                subprocess.run(["ffmpeg", "-i", temp_path, "-y", wav_path],
                             capture_output=True, check=True)
                audio_data, sr = load_audio(Path(wav_path))
                play_audio(audio_data, sr)
                Path(wav_path).unlink(missing_ok=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Last resort: try afplay on macOS
                try:
                    subprocess.run(["afplay", temp_path], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    return False

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
        return True

    except Exception:
        return False


class AsyncAudioStreamer:
    """
    Async audio streamer for real-time audio processing.

    Streams audio chunks from the microphone as an async generator,
    suitable for use with Gemini Live API.
    """

    def __init__(self, chunk_ms: int = REALTIME_AUDIO_CHUNK_MS):
        """
        Initialize the async audio streamer.

        Args:
            chunk_ms: Size of each audio chunk in milliseconds
        """
        self.chunk_ms = chunk_ms
        self.chunk_samples = int(SAMPLE_RATE * chunk_ms / 1000)
        self.queue: asyncio.Queue = None
        self.stream: sd.InputStream = None
        self.running = False
        self._loop: asyncio.AbstractEventLoop = None

    def _audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice InputStream."""
        if self.running and self.queue and self._loop:
            # Convert to 16-bit PCM bytes
            audio_int16 = (indata.flatten() * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            try:
                self._loop.call_soon_threadsafe(
                    self.queue.put_nowait, audio_bytes
                )
            except asyncio.QueueFull:
                pass  # Drop frames if queue is full

    async def start(self):
        """Start the audio stream."""
        self._loop = asyncio.get_event_loop()
        self.queue = asyncio.Queue(maxsize=100)
        self.running = True

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32,
            callback=self._audio_callback,
            blocksize=self.chunk_samples,
        )
        self.stream.start()

    async def stop(self):
        """Stop the audio stream."""
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        # Signal end of stream
        if self.queue:
            await self.queue.put(None)

    async def stream_audio(self) -> AsyncGenerator[bytes, None]:
        """
        Async generator yielding audio chunks.

        Yields:
            Audio data as 16-bit PCM bytes (16kHz mono)
        """
        if not self.running:
            await self.start()

        while self.running:
            try:
                chunk = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=0.5
                )
                if chunk is None:
                    break
                yield chunk
            except asyncio.TimeoutError:
                continue

    def __del__(self):
        """Cleanup on deletion."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
