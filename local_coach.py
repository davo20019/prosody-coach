"""Local AI coaching provider using whisper.cpp and llama.cpp."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import soundfile as sf

from analyzer import ProsodyAnalysis
from coach import CoachingResult, parse_coaching_response
from config import (
    LOCAL_LLM_BASE_URL,
    LOCAL_LLM_MODEL,
    LOCAL_LLM_TIMEOUT,
    LOCAL_WHISPER_BIN,
    LOCAL_WHISPER_MODEL,
    LOCAL_WHISPER_SERVER_URL,
)


@dataclass
class LocalCoachConfig:
    """Runtime configuration for fully local AI coaching."""

    whisper_bin: str = LOCAL_WHISPER_BIN
    whisper_model: str = LOCAL_WHISPER_MODEL
    whisper_server_url: str = LOCAL_WHISPER_SERVER_URL
    llm_base_url: str = LOCAL_LLM_BASE_URL
    llm_model: str = LOCAL_LLM_MODEL
    llm_timeout: float = LOCAL_LLM_TIMEOUT

    @classmethod
    def from_env(cls) -> "LocalCoachConfig":
        """Load local provider settings from current environment variables."""
        return cls(
            whisper_bin=os.environ.get("WHISPER_CPP_BIN", LOCAL_WHISPER_BIN),
            whisper_model=os.environ.get("WHISPER_MODEL", LOCAL_WHISPER_MODEL),
            whisper_server_url=os.environ.get("LOCAL_WHISPER_SERVER_URL", LOCAL_WHISPER_SERVER_URL),
            llm_base_url=os.environ.get("LOCAL_LLM_BASE_URL", LOCAL_LLM_BASE_URL),
            llm_model=os.environ.get("LOCAL_LLM_MODEL", LOCAL_LLM_MODEL),
            llm_timeout=float(os.environ.get("LOCAL_LLM_TIMEOUT", str(LOCAL_LLM_TIMEOUT))),
        )


@dataclass
class LocalSetupCheck:
    """A single local setup diagnostic check."""

    key: str
    label: str
    ok: bool
    detail: str
    fix: str


@dataclass(frozen=True)
class WordTimestamp:
    """A single word with its audio span."""

    word: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Transcript:
    """Transcription result.

    `tokens` is always populated and drives the scoring prompt's index space.
    `words` carries audio-aligned timestamps when the backend can emit them;
    an empty list is a first-class state meaning "per-slot prosody unavailable."

    Invariant: when `words` is non-empty, `tokens == [w.word for w in words]`.
    """

    text: str
    tokens: list[str]
    words: list[WordTimestamp]


def is_whisper_server_configured(config: Optional["LocalCoachConfig"] = None) -> bool:
    """True iff LOCAL_WHISPER_SERVER_URL is set."""
    cfg = config or LocalCoachConfig.from_env()
    return bool(cfg.whisper_server_url)


def is_whisper_cli_configured(config: Optional["LocalCoachConfig"] = None) -> bool:
    """True iff a Whisper model file exists AND the binary is on PATH or at an absolute path.

    The default `LOCAL_WHISPER_BIN = "whisper-cli"` is a bare command name that
    will exist as a string even when nothing is installed, so this performs an
    explicit existence check.
    """
    cfg = config or LocalCoachConfig.from_env()
    if not cfg.whisper_model:
        return False
    model_path = Path(os.path.expanduser(cfg.whisper_model))
    if not model_path.exists():
        return False
    if shutil.which(cfg.whisper_bin) is not None:
        return True
    return Path(cfg.whisper_bin).exists()


class WhisperCppTranscriber:
    """Transcribe audio with the whisper.cpp command-line binary."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ):
        self.config = config or LocalCoachConfig.from_env()
        self.runner = runner

    def transcribe(self, audio_path: Path) -> str:
        """Run whisper.cpp and return cleaned transcript text."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not self.config.whisper_model:
            raise ValueError(
                "WHISPER_MODEL is not set. Run `prosody local setup` for setup instructions."
            )

        model_path = Path(os.path.expanduser(self.config.whisper_model))
        if not model_path.exists():
            raise FileNotFoundError(f"Whisper model not found: {model_path}")

        with tempfile.TemporaryDirectory(prefix="prosody-whisper-") as temp_dir:
            output_base = Path(temp_dir) / "transcript"
            command = [
                self.config.whisper_bin,
                "-m",
                str(model_path),
                "-f",
                str(audio_path),
                "-otxt",
                "-of",
                str(output_base),
                "--no-timestamps",
            ]

            try:
                completed = self.runner(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"whisper.cpp binary not found: {self.config.whisper_bin}"
                ) from exc
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or exc.stdout or "").strip()
                raise RuntimeError(f"whisper.cpp transcription failed: {stderr}") from exc

            transcript_path = output_base.with_suffix(".txt")
            if transcript_path.exists():
                transcript = transcript_path.read_text(encoding="utf-8", errors="replace")
            else:
                transcript = getattr(completed, "stdout", "") or ""

        transcript = _clean_whisper_text(transcript)
        if not transcript:
            raise RuntimeError("whisper.cpp returned an empty transcript.")
        return transcript

    def transcribe_with_timestamps(self, audio_path: Path) -> Transcript:
        """Transcribe and return a Transcript.

        whisper.cpp's CLI does not emit reliable word-level timestamps
        (`-oj` is segment-level, `-ojf` is subword tokens), so this path
        always returns `words=[]`. Per-slot prosody requires `whisper-server`.
        """
        text = self.transcribe(audio_path)
        tokens = text.split()
        return Transcript(text=text, tokens=tokens, words=[])


class WhisperServerTranscriber:
    """Transcribe audio via whisper.cpp HTTP server (keeps model resident)."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        opener: Callable[..., object] = urllib.request.urlopen,
    ):
        self.config = config or LocalCoachConfig.from_env()
        if not self.config.whisper_server_url:
            raise ValueError(
                "LOCAL_WHISPER_SERVER_URL is not set. Start `whisper-server` and set the URL."
            )
        self.opener = opener

    def transcribe(self, audio_path: Path) -> str:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        url = self.config.whisper_server_url.rstrip("/") + "/inference"
        boundary = f"----prosody{uuid.uuid4().hex}"
        body = _encode_multipart_audio(audio_path, boundary)
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.config.llm_timeout) as response:
                payload = response.read()
        except (urllib.error.URLError, OSError) as exc:
            hint = _format_whisper_server_hint(self.config.whisper_server_url, self.config)
            raise RuntimeError(f"whisper-server not reachable at {url}: {exc}{hint}") from exc

        raw = payload.decode("utf-8", errors="replace").strip()
        if raw.startswith("{"):
            try:
                raw = json.loads(raw).get("text", "")
            except json.JSONDecodeError:
                pass
        transcript = _clean_whisper_text(raw)
        if not transcript:
            raise RuntimeError("whisper-server returned an empty transcript.")
        return transcript

    def transcribe_with_timestamps(self, audio_path: Path) -> Transcript:
        """Transcribe and return a Transcript with word-level timestamps if available.

        Requests `response_format=verbose_json` from whisper-server. When the
        running build emits `segments[].words[]` (or top-level `words[]`),
        tokens are derived from those words so `tokens[i] == words[i].word`
        and indices align. Otherwise returns `words=[]` and `tokens=text.split()`.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        url = self.config.whisper_server_url.rstrip("/") + "/inference"
        boundary = f"----prosody{uuid.uuid4().hex}"
        body = _encode_multipart_audio(audio_path, boundary, response_format="verbose_json")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.config.llm_timeout) as response:
                payload = response.read()
        except (urllib.error.URLError, OSError) as exc:
            hint = _format_whisper_server_hint(self.config.whisper_server_url, self.config)
            raise RuntimeError(f"whisper-server not reachable at {url}: {exc}{hint}") from exc

        raw = payload.decode("utf-8", errors="replace").strip()
        if not raw.startswith("{"):
            # Server returned plain text; no timestamps available.
            text = _clean_whisper_text(raw)
            if not text:
                raise RuntimeError("whisper-server returned an empty transcript.")
            return Transcript(text=text, tokens=text.split(), words=[])

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"whisper-server returned malformed JSON: {exc}") from exc

        text = _clean_whisper_text(data.get("text", ""))
        if not text:
            raise RuntimeError("whisper-server returned an empty transcript.")

        words = _extract_words_from_verbose_json(data)
        if words:
            tokens = [w.word for w in words]
        else:
            tokens = text.split()
        return Transcript(text=text, tokens=tokens, words=words)


def _extract_words_from_verbose_json(data: dict) -> list[WordTimestamp]:
    """Pull word-level timestamps out of a whisper-server verbose_json payload.

    Handles two shapes:
      - top-level `words: [{word, start, end}, ...]`
      - per-segment `segments: [{..., words: [...]}, ...]`

    Returns an empty list when no word-level data is present (older
    whisper-server builds emit segment-level info only).
    """
    out: list[WordTimestamp] = []

    top_words = data.get("words")
    if isinstance(top_words, list) and top_words:
        for w in top_words:
            parsed = _parse_word_entry(w)
            if parsed is not None:
                out.append(parsed)
        return out

    segments = data.get("segments")
    if isinstance(segments, list):
        for seg in segments:
            seg_words = seg.get("words")
            if isinstance(seg_words, list):
                for w in seg_words:
                    parsed = _parse_word_entry(w)
                    if parsed is not None:
                        out.append(parsed)
    return out


def _parse_word_entry(entry: dict) -> Optional[WordTimestamp]:
    """Normalize a single word entry from whisper-server JSON."""
    if not isinstance(entry, dict):
        return None
    word = (entry.get("word") or entry.get("text") or "").strip()
    if not word:
        return None
    start = entry.get("start")
    end = entry.get("end")
    if start is None or end is None:
        return None
    try:
        return WordTimestamp(word=word, start_s=float(start), end_s=float(end))
    except (TypeError, ValueError):
        return None


def _encode_multipart_audio(
    audio_path: Path,
    boundary: str,
    response_format: str = "text",
) -> bytes:
    mime = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    crlf = b"\r\n"
    parts = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"'.encode(),
        f"Content-Type: {mime}".encode(),
        b"",
        audio_path.read_bytes(),
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="response_format"',
        b"",
        response_format.encode(),
        f"--{boundary}--".encode(),
        b"",
    ]
    return crlf.join(parts)


class LocalLlmClient:
    """OpenAI-compatible chat client for a local llama.cpp server."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        opener: Callable[..., object] = urllib.request.urlopen,
    ):
        self.config = config or LocalCoachConfig.from_env()
        self.opener = opener

    def complete(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        chat_template_kwargs: Optional[dict] = None,
    ) -> str:
        """Send a chat completion request to the local LLM server.

        `chat_template_kwargs` is forwarded verbatim. For Gemma 4 reasoning
        variants (e.g. 26B-A4B) pass `{"enable_thinking": False}` — otherwise
        the model spends its entire token budget thinking and returns an empty
        `content`. Non-reasoning models ignore the kwarg.
        """
        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if chat_template_kwargs:
            payload["chat_template_kwargs"] = chat_template_kwargs
        request = urllib.request.Request(
            _chat_completions_url(self.config.llm_base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with self.opener(request, timeout=self.config.llm_timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            hint = _format_local_llm_hint(self.config.llm_base_url, opener=self.opener)
            raise RuntimeError(
                f"Local LLM server is not reachable at {self.config.llm_base_url}: {exc}{hint}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Local LLM server returned invalid JSON.") from exc

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected local LLM response: {data}") from exc


# --------------------------------------------------------------------------- #
# Local LLM endpoint auto-detection
# --------------------------------------------------------------------------- #

CANDIDATE_LOCAL_LLM_URLS: tuple[str, ...] = (
    "http://127.0.0.1:11434/v1",   # Ollama
    "http://127.0.0.1:8080/v1",    # llama-server / LM Studio default
    "http://127.0.0.1:8090/v1",    # llama-server (alt)
    "http://127.0.0.1:1234/v1",    # LM Studio default
    "http://127.0.0.1:5001/v1",    # koboldcpp
)


@dataclass
class LocalLlmEndpointProbe:
    """Result of probing one candidate OpenAI-compatible local LLM URL."""
    base_url: str
    reachable: bool       # /v1/models returned a 2xx
    has_models: bool      # response.data is a non-empty list of models
    models: list[str]
    error: Optional[str]  # short human-readable reason when not usable


def _probe_local_llm_endpoint(
    url: str,
    *,
    timeout: float,
    opener: Callable[..., object],
) -> LocalLlmEndpointProbe:
    """Probe one /v1/models endpoint and classify what we found."""
    models_url = url.rstrip("/") + "/models"
    try:
        with opener(urllib.request.Request(models_url), timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return LocalLlmEndpointProbe(
            base_url=url, reachable=False, has_models=False, models=[],
            error=f"unreachable ({reason})",
        )
    except Exception as exc:  # network stack edge cases (timeouts, OS errors)
        return LocalLlmEndpointProbe(
            base_url=url, reachable=False, has_models=False, models=[],
            error=f"unreachable ({exc})",
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return LocalLlmEndpointProbe(
            base_url=url, reachable=True, has_models=False, models=[],
            error="reachable but not OpenAI-compatible (non-JSON response)",
        )

    models: list[str] = []
    if isinstance(data, dict):
        items = data.get("data")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("id"):
                    models.append(str(item["id"]))

    if not models:
        return LocalLlmEndpointProbe(
            base_url=url, reachable=True, has_models=False, models=[],
            error="reachable but no models loaded",
        )

    return LocalLlmEndpointProbe(
        base_url=url, reachable=True, has_models=True, models=models, error=None,
    )


def detect_local_llm_url(
    candidates: Optional[list[str]] = None,
    *,
    timeout: float = 0.5,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> tuple[Optional[str], list[LocalLlmEndpointProbe]]:
    """Probe candidate URLs and return the first usable one.

    "Usable" means: reachable AND at least one model is loaded. Returns
    (best_url, all_probes). best_url is None when nothing usable was found —
    callers can still inspect `all_probes` to surface diagnostics.
    """
    urls = list(candidates) if candidates is not None else list(CANDIDATE_LOCAL_LLM_URLS)
    probes: list[LocalLlmEndpointProbe] = []
    best: Optional[str] = None
    for url in urls:
        probe = _probe_local_llm_endpoint(url, timeout=timeout, opener=opener)
        probes.append(probe)
        if best is None and probe.has_models:
            best = url
    return best, probes


# --------------------------------------------------------------------------- #
# whisper-server diagnostics
# --------------------------------------------------------------------------- #

def _probe_tcp(host: str, port: int, *, timeout: float = 0.3) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_host_port(url: str) -> Optional[tuple[str, int]]:
    """Pull (host, port) out of a URL like http://127.0.0.1:9000 — None on failure."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return None
        return host, port
    except (ValueError, AttributeError):
        return None


def _format_whisper_server_hint(
    configured_url: str,
    config: "LocalCoachConfig",
) -> str:
    """Multi-line hint for whisper-server failures.

    Tells the user: is the port even listening, and what their fallback options
    are (whisper-cli if configured, or how to restart the server). Never raises.
    """
    try:
        lines = ["", ""]
        host_port = _parse_host_port(configured_url)
        if host_port:
            host, port = host_port
            listening = _probe_tcp(host, port, timeout=0.3)
            if listening:
                lines.append(
                    f"TCP port {port} is open, so whisper-server accepted the "
                    "connection but dropped it before responding. The server "
                    "process likely crashed mid-request (OOM is common with "
                    "the medium model on long audio). Restart it and try a "
                    "shorter clip, or switch to a smaller model (base.en/small.en)."
                )
            else:
                lines.append(
                    f"Nothing is listening on {host}:{port}. whisper-server is "
                    "not running."
                )

        # Concrete next steps based on the user's existing config.
        if config.whisper_bin and config.whisper_model:
            lines.append("")
            lines.append(
                "You have whisper-cli configured. To fall back to it (no "
                "word-level timestamps, per-slot delivery will be unavailable):"
            )
            lines.append("  unset LOCAL_WHISPER_SERVER_URL  # then restart the web app")
        if config.whisper_model:
            lines.append("")
            lines.append("Or restart whisper-server:")
            lines.append(
                f"  whisper-server -m {config.whisper_model} --port "
                f"{host_port[1] if host_port else 9000}"
            )
        return "\n".join(lines)
    except Exception:
        return ""


def _format_local_llm_hint(
    configured_url: str,
    *,
    opener: Callable[..., object],
) -> str:
    """Format a multi-line hint string for the connection-refused error.

    Returns "" when nothing useful was found so the original error stands alone.
    Never raises — diagnostics must not mask the original failure.
    """
    try:
        candidates = [u for u in CANDIDATE_LOCAL_LLM_URLS if u != configured_url.rstrip("/")]
        best, probes = detect_local_llm_url(
            candidates, timeout=0.5, opener=opener,
        )
    except Exception:
        return ""

    lines = ["", "", "Probed other common OpenAI-compatible local LLM ports:"]
    for p in probes:
        if p.has_models:
            lines.append(f"  - {p.base_url}: reachable, models loaded: {', '.join(p.models[:3])}")
        elif p.error:
            lines.append(f"  - {p.base_url}: {p.error}")

    if best:
        # Pick the first model from the best probe so the env-var hint is concrete.
        best_probe = next(p for p in probes if p.base_url == best)
        model = best_probe.models[0] if best_probe.models else "<model>"
        lines.append("")
        lines.append(
            f"To use it, set LOCAL_LLM_BASE_URL={best} "
            f"and LOCAL_LLM_MODEL={model}, then restart."
        )
    return "\n".join(lines)


class LocalCoachProvider:
    """End-to-end local coaching: Whisper transcript + metrics + local LLM."""

    def __init__(
        self,
        config: Optional[LocalCoachConfig] = None,
        transcriber=None,
        llm_client: Optional[LocalLlmClient] = None,
    ):
        self.config = config or LocalCoachConfig.from_env()
        if transcriber is not None:
            self.transcriber = transcriber
        elif self.config.whisper_server_url:
            self.transcriber = WhisperServerTranscriber(self.config)
        else:
            self.transcriber = WhisperCppTranscriber(self.config)
        self.llm_client = llm_client or LocalLlmClient(self.config)

    def analyze(
        self,
        audio_path: Optional[Path],
        audio_data: Optional[np.ndarray],
        sample_rate: int,
        prosody: ProsodyAnalysis,
        expected_text: Optional[str] = None,
    ) -> CoachingResult:
        """Analyze a recording with the local provider."""
        transient_path = None
        if audio_path is None:
            if audio_data is None:
                raise ValueError("audio_data is required when audio_path is not provided.")
            transient_path = _write_temp_audio(audio_data, sample_rate)
            audio_path = transient_path
        else:
            audio_path = Path(audio_path)

        try:
            transcript = self.transcriber.transcribe(audio_path)
            prompt = build_local_coaching_prompt(
                prosody=prosody,
                transcript=transcript,
                expected_text=expected_text,
            )
            response_text = self.llm_client.complete(prompt)
            result = parse_coaching_response(response_text)
            if _transcript_is_missing(result.transcript):
                result.transcript = transcript
            return result
        finally:
            if transient_path is not None:
                transient_path.unlink(missing_ok=True)


def analyze_with_local_coach(
    audio_data: np.ndarray,
    sample_rate: int,
    prosody: ProsodyAnalysis,
    audio_path: Optional[Path] = None,
    expected_text: Optional[str] = None,
) -> CoachingResult:
    """Convenience wrapper for local coaching."""
    return LocalCoachProvider().analyze(
        audio_path=audio_path,
        audio_data=audio_data,
        sample_rate=sample_rate,
        prosody=prosody,
        expected_text=expected_text,
    )


def build_local_coaching_prompt(
    prosody: ProsodyAnalysis,
    transcript: str,
    expected_text: Optional[str] = None,
) -> str:
    """Build a coaching prompt for a text-only local LLM."""
    practice_block = ""
    task = (
        "Use the local ASR transcript and measured prosody metrics to coach the speaker."
    )
    transcript_instruction = (
        "Use the LOCAL ASR TRANSCRIPT as the source of what was said. "
        "Do not invent words that are not in the transcript."
    )

    if expected_text:
        task = (
            "The user was asked to read the expected text aloud. Compare the local "
            "ASR transcript with that expected text and coach the speaker."
        )
        practice_block = f"""
EXPECTED TEXT:
"{expected_text}"
"""
        transcript_instruction = (
            "Use the LOCAL ASR TRANSCRIPT as what the user actually said. "
            "Compare it to EXPECTED TEXT for skipped, added, or misread words."
        )

    return f"""You are an English speech coach helping a Spanish speaker improve their English communication.

TASK: {task}

LOCAL ASR TRANSCRIPT:
"{transcript}"
{practice_block}
{transcript_instruction}

PROSODY ANALYSIS RESULTS (already measured locally):
- Pitch: {prosody.pitch.score}/10 - {prosody.pitch.feedback}
- Volume: {prosody.volume.score}/10 - {prosody.volume.feedback}
- Tempo: {prosody.tempo.score}/10 - Speed: {prosody.tempo.estimated_wpm:.0f} WPM. {prosody.tempo.feedback}
- Rhythm: {prosody.rhythm.score}/10 - PVI: {prosody.rhythm.pvi:.0f}. {prosody.rhythm.feedback}
- Pauses: {prosody.pauses.score}/10 - {prosody.pauses.feedback}

You cannot listen to the audio directly. For vocal quality, confidence, fluency, rhythm, and pronunciation, combine the transcript with the measured prosody metrics. Be explicit when feedback is based on metrics rather than direct hearing.

Please provide your response in this EXACT format:

TRANSCRIPT:
[Repeat the local ASR transcript, lightly correcting only obvious transcription punctuation]

GRAMMAR_ISSUES:
[List each grammar or pronunciation issue on a new line in this format:]
["original text" -> "corrected text" | explanation]
[If this is reading practice, compare transcript to expected text here]
[If no issues, write: None]

SUGGESTED_REVISION:
[Write a polished version of what was said, or the correct expected text for reading practice]

COACHING_TIPS:
[List 3-5 specific, actionable tips based on:]
[1. The lowest prosody score area]
[2. Transcript grammar or word choice]
[3. Spanish-speaker patterns such as rhythm, reductions, word-final consonants, v/b, or th]
[4. Where to slow down, stress key words, or pause]

VOCAL_CONFIDENCE:
[Rate likely confidence from 1-10 using transcript and metrics]
[Format: SCORE | explanation]

FILLER_WORDS:
[Count filler words in the transcript: um, uh, er, like, you know, so, basically, I mean, kind of, sort of]
[Format: COUNT | list each filler word with its count]
[If no filler words, write: 0 | None detected]

PRONUNCIATION_ISSUES:
[List likely pronunciation sounds to practice only when transcript or expected text supports it]
[Format each as: SOUND | example word | tip for improvement]
[If pronunciation cannot be inferred or is clear, write: None - pronunciation was clear]

FLUENCY:
[Rate fluency from 1-10 using tempo, pauses, and transcript]
[Format: SCORE | explanation]

AI_PROSODY:
[Metrics-informed prosody assessment. Do not claim direct audio listening.]
[Format each line as: CATEGORY: SCORE/10 | observation]
- PITCH: [Score 1-10] | [Use measured pitch score and feedback]
- VOLUME: [Score 1-10] | [Use measured volume score and feedback]
- TEMPO: [Score 1-10] | [Use measured WPM and tempo feedback]
- RHYTHM: [Score 1-10] | [Use measured rhythm score and PVI]
- PAUSES: [Score 1-10] | [Use measured pause score and feedback]
- NATURALNESS: [Score 1-10] | [Overall estimate from transcript plus metrics]

OVERALL:
[One paragraph summary of strengths and the #1 thing to focus on improving]
"""


def generate_local_tailored_prompt(
    weaknesses: dict,
    due_sounds: Optional[list[dict]] = None,
    due_words: Optional[list[dict]] = None,
    llm_client: Optional[LocalLlmClient] = None,
) -> dict:
    """Generate tailored practice material with the local text LLM."""
    focus_areas = weaknesses.get("focus_areas", [])
    difficulty = weaknesses.get("difficulty", "intermediate")
    recurring_sounds = weaknesses.get("recurring_sounds", [])

    focus_descriptions = []
    target_words = []
    target_sounds = []

    if due_words:
        for word_data in due_words[:5]:
            word = word_data.get("word", "")
            ipa = word_data.get("ipa", "")
            if word:
                target_words.append({"word": word, "ipa": ipa})
        if target_words:
            words = ", ".join(word["word"] for word in target_words)
            focus_descriptions.append(f"MUST INCLUDE WORDS: {words}")

    if due_sounds:
        for sound_data in due_sounds[:3]:
            sound = sound_data.get("sound", "")
            ipa = sound_data.get("ipa", "")
            if sound:
                target_sounds.append({"sound": sound, "ipa": ipa})
        if target_sounds:
            sounds = ", ".join(sound["sound"] for sound in target_sounds)
            focus_descriptions.append(f"PRIORITY SOUNDS: {sounds}")

    prosody_focuses = [f["area"] for f in focus_areas if f.get("type") == "prosody"]
    if prosody_focuses:
        focus_descriptions.append(f"Prosody: {', '.join(prosody_focuses)}")

    pron_sounds = [f["sound"] for f in focus_areas if f.get("type") == "pronunciation"]
    if not pron_sounds and recurring_sounds:
        pron_sounds = [sound[0] for sound in recurring_sounds[:3]]

    existing_sounds = {sound["sound"] for sound in target_sounds}
    for sound in pron_sounds:
        if sound and sound not in existing_sounds:
            target_sounds.append({"sound": sound, "ipa": ""})

    if pron_sounds:
        focus_descriptions.append(f"Sounds: {', '.join(pron_sounds)}")
    if any(f.get("type") == "confidence" for f in focus_areas):
        focus_descriptions.append("Build confidence with clear declarative sentences")
    if any(f.get("type") == "fluency" for f in focus_areas):
        focus_descriptions.append("Improve fluency with connected speech")
    if any(f.get("type") == "filler_words" for f in focus_areas):
        focus_descriptions.append("Reduce fillers with direct statements")

    focus_text = "\n".join(f"- {item}" for item in focus_descriptions) or "- General practice"
    prompt = f"""You are an English pronunciation coach creating practice material for a Spanish speaker.

Generate a short practice text tailored to the learner.

DIFFICULTY LEVEL: {difficulty}

FOCUS AREAS:
{focus_text}

REQUIREMENTS:
1. Write 2-3 natural, meaningful sentences.
2. Include target words and sounds if listed.
3. Include natural pause points if rhythm or pauses are a focus.
4. Avoid tongue twisters and artificial lists.

Respond in this exact format:

TEXT:
The practice sentences go here.

KEY_SOUNDS:
word1 /IPA1/, word2 /IPA2/, word3 /IPA3/
"""

    client = llm_client or LocalLlmClient()
    response_text = client.complete(prompt, temperature=0.7, max_tokens=2048)
    text, key_sounds = _parse_tailored_prompt_response(response_text)

    return {
        "text": text,
        "key_sounds": key_sounds,
        "focus_areas": [f["description"] for f in focus_areas if "description" in f],
        "difficulty": difficulty,
        "id": f"tailored_{difficulty}",
        "target_sounds": target_sounds,
        "target_words": target_words,
    }


def diagnose_local_setup(
    config: Optional[LocalCoachConfig] = None,
    which: Callable[[str], Optional[str]] = shutil.which,
    llm_checker: Optional[Callable[[LocalCoachConfig], tuple[bool, str]]] = None,
) -> list[LocalSetupCheck]:
    """Return local AI setup diagnostics."""
    config = config or LocalCoachConfig.from_env()
    llm_checker = llm_checker or check_llama_server
    checks = []

    binary = os.path.expanduser(config.whisper_bin)
    if os.sep in binary:
        binary_path = Path(binary)
        binary_ok = binary_path.exists() and os.access(binary_path, os.X_OK)
        binary_detail = str(binary_path) if binary_ok else f"{binary_path} is not executable or missing"
    else:
        found = which(binary)
        binary_ok = found is not None
        binary_detail = found or f"{binary} is not on PATH"

    checks.append(
        LocalSetupCheck(
            key="whisper_binary",
            label="whisper.cpp binary",
            ok=binary_ok,
            detail=binary_detail,
            fix="Install with `brew install whisper-cpp` or set WHISPER_CPP_BIN.",
        )
    )

    if config.whisper_model:
        model_path = Path(os.path.expanduser(config.whisper_model))
        model_ok = model_path.exists()
        model_detail = str(model_path) if model_ok else f"{model_path} does not exist"
    else:
        model_ok = False
        model_detail = "WHISPER_MODEL is not set"

    checks.append(
        LocalSetupCheck(
            key="whisper_model",
            label="Whisper model",
            ok=model_ok,
            detail=model_detail,
            fix="Download a whisper.cpp GGML model and set WHISPER_MODEL.",
        )
    )

    llm_ok, llm_detail = llm_checker(config)
    checks.append(
        LocalSetupCheck(
            key="llama_server",
            label="llama.cpp server",
            ok=llm_ok,
            detail=llm_detail,
            fix="Start `llama-server` with a GGUF model, then set LOCAL_LLM_BASE_URL.",
        )
    )

    if config.whisper_server_url:
        ws_ok, ws_detail = check_whisper_server(config)
        checks.append(
            LocalSetupCheck(
                key="whisper_server",
                label="whisper.cpp server",
                ok=ws_ok,
                detail=ws_detail,
                fix="Start `whisper-server -m <model> --host 127.0.0.1 --port 9000`.",
            )
        )

    return checks


def check_whisper_server(config: LocalCoachConfig) -> tuple[bool, str]:
    """Check whether the whisper.cpp HTTP server is reachable."""
    base = config.whisper_server_url.rstrip("/")
    request = urllib.request.Request(base + "/", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            getattr(response, "status", 200)
        return True, f"reachable at {base}"
    except urllib.error.HTTPError:
        return True, f"reachable at {base}"
    except Exception as exc:
        return False, str(exc)


def check_llama_server(config: LocalCoachConfig) -> tuple[bool, str]:
    """Check whether the local OpenAI-compatible server is reachable."""
    url = _models_url(config.llm_base_url)
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            status = getattr(response, "status", 200)
            if status < 400:
                return True, f"reachable at {url}"
            return False, f"{url} returned HTTP {status}"
    except Exception as exc:
        return False, str(exc)


def _clean_whisper_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^\[[^\]]+\]\s*", "", line).strip()
        if line:
            lines.append(line)
    return " ".join(lines).strip()


def _write_temp_audio(audio_data: np.ndarray, sample_rate: int) -> Path:
    temp_file = tempfile.NamedTemporaryFile(
        prefix="prosody-local-",
        suffix=".flac",
        delete=False,
    )
    temp_path = Path(temp_file.name)
    temp_file.close()
    sf.write(temp_path, audio_data, sample_rate, format="flac")
    return temp_path


def _transcript_is_missing(transcript: str) -> bool:
    normalized = (transcript or "").strip().lower()
    return normalized in {"", "same as above", "[same as above]", "[transcript]"}


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1/chat/completions") or base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base.rsplit("/chat/completions", 1)[0]
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return f"{base}/models"


def _parse_tailored_prompt_response(response_text: str) -> tuple[str, str]:
    text_lines = []
    key_lines = []
    section = None

    for line in response_text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("TEXT:"):
            section = "text"
            content = stripped[5:].strip()
            if content:
                text_lines.append(content)
        elif upper.startswith("KEY_SOUNDS:") or upper.startswith("KEY SOUNDS:"):
            section = "keys"
            content = re.sub(r"^KEY[_ ]SOUNDS:\s*", "", stripped, flags=re.IGNORECASE)
            if content:
                key_lines.append(content)
        elif stripped and section == "text" and not stripped.startswith("["):
            text_lines.append(stripped)
        elif stripped and section == "keys" and not stripped.startswith("["):
            key_lines.append(stripped)

    text = " ".join(text_lines).strip() or response_text.strip().strip("\"'")
    key_sounds = ", ".join(key_lines).strip()

    for header in ("TEXT:", "KEY_SOUNDS:", "KEY SOUNDS:"):
        text = re.sub(re.escape(header), "", text, flags=re.IGNORECASE).strip()

    if text and text[-1] not in ".!?":
        last_end = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if last_end > len(text) // 2:
            text = text[: last_end + 1]

    return text, key_sounds
